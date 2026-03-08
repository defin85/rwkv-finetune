#!/usr/bin/env python3
"""Build 1C-Expert-v4 plain-text train dataset with release gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import build_canonical_row, load_canonical_rows, validate_canonical_row


METHOD_PATTERN = re.compile(
    r"(?ims)^[ \t]*(?P<kind>Процедура|Функция)\s+"
    r"(?P<name>[A-Za-zА-Яа-я_][A-Za-zА-Яа-я0-9_]*)\s*\([^)]*\)"
    r"(?P<body>.*?)^[ \t]*Конец(?P<end>Процедуры|Функции)\s*;?",
)
RAW_JSON_PATTERN = re.compile(r'^\s*\{.*"(instruction|output|text)"\s*:', re.IGNORECASE | re.DOTALL)
USER_ASSISTANT_PATTERN = re.compile(
    r"^\s*User:\s*(?P<user>.*?)\s*Assistant:\s*(?P<assistant>.*?)\s*$",
    re.DOTALL,
)

EOT_TOKEN = "<|endoftext|>"
SEGMENT_ORDER = ("onec_bsl", "coding_general", "ru_identity")


@dataclass
class OneCMethod:
    name: str
    kind: str
    body: str
    module_path: str
    module_type: str


@dataclass
class PreparedSample:
    segment: str
    source: str
    text: str
    metadata: dict[str, Any]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build 1C-Expert-v4 train text with ratio/format/volume gates."
    )
    parser.add_argument(
        "--profile",
        default="configs/dataset/1c-expert-v4.profile.json",
        help="Path to 1C-Expert-v4 profile JSON.",
    )
    parser.add_argument("--bsl-root", required=True, help="Directory with .bsl source files.")
    parser.add_argument(
        "--coding-jsonl",
        required=True,
        help="JSONL with coding samples resolvable to canonical rows with valid RU prompt and provenance metadata.",
    )
    parser.add_argument(
        "--ru-jsonl",
        required=True,
        help="JSONL with RU identity/chat samples resolvable to canonical rows with valid provenance metadata.",
    )
    parser.add_argument(
        "--bsl-source",
        required=True,
        help="Source id used for canonical onec_bsl rows generated from --bsl-root.",
    )
    parser.add_argument(
        "--bsl-license",
        required=True,
        help="License label used for canonical onec_bsl rows generated from --bsl-root.",
    )
    parser.add_argument(
        "--bsl-origin-ref",
        required=True,
        help="Base origin reference used for canonical onec_bsl rows generated from --bsl-root.",
    )
    parser.add_argument(
        "--bsl-contour",
        required=True,
        help="Contour label used for canonical onec_bsl rows generated from --bsl-root.",
    )
    parser.add_argument("--output-text", required=True, help="Output train text path.")
    parser.add_argument("--report-output", required=True, help="Output release report JSON path.")
    parser.add_argument("--seed", type=int, default=20260304, help="Deterministic shuffle seed.")
    parser.add_argument(
        "--hard-min-mb",
        type=int,
        default=None,
        help="Override hard minimum output size in MB (testing/debug only).",
    )
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def infer_module_type(path: Path) -> str:
    lower = str(path).lower()
    if "manager" in lower:
        return "manager"
    if "object" in lower:
        return "object"
    if "common" in lower:
        return "common"
    return "unknown"


def extract_methods_from_text(source: str) -> list[OneCMethod]:
    methods: list[OneCMethod] = []
    for match in METHOD_PATTERN.finditer(source):
        kind = match.group("kind")
        end = match.group("end")
        if kind == "Процедура" and end != "Процедуры":
            continue
        if kind == "Функция" and end != "Функции":
            continue
        full_body = (kind + " " + source[match.start("name") : match.end()]).strip()
        methods.append(
            OneCMethod(
                name=match.group("name"),
                kind=kind,
                body=full_body,
                module_path="",
                module_type="unknown",
            )
        )
    return methods


def collect_onec_methods(root: Path) -> list[OneCMethod]:
    methods: list[OneCMethod] = []
    for path in sorted(root.rglob("*.bsl")):
        extracted = extract_methods_from_text(path.read_text(encoding="utf-8", errors="ignore"))
        module_type = infer_module_type(path)
        for row in extracted:
            methods.append(
                OneCMethod(
                    name=row.name,
                    kind=row.kind,
                    body=row.body,
                    module_path=str(path),
                    module_type=module_type,
                )
            )
    return methods


def format_sample(instruction: str, response: str) -> str:
    inst = " ".join(instruction.strip().split())
    resp = response.strip()
    return f"Instruction: {inst}\n\nResponse: {resp}\n{EOT_TOKEN}\n"


def build_source_allowlist(profile: dict[str, Any]) -> dict[str, set[str]]:
    allowlist: dict[str, set[str]] = {}
    for item in profile.get("source_allowlist", []):
        if not isinstance(item, dict):
            continue
        source = str(item.get("dataset_id", "")).strip()
        segment = str(item.get("segment", "")).strip()
        if source and segment:
            allowlist.setdefault(segment, set()).add(source)
    return allowlist


def require_non_allowlisted_source_rationale(
    row: dict[str, Any],
    *,
    allowed_sources: set[str],
    path: Path,
    index: int,
) -> str | None:
    metadata = row["metadata"]
    source = str(metadata.get("source", "")).strip()
    if source in allowed_sources:
        return None

    quality_rationale = metadata.get("quality_rationale")
    if isinstance(quality_rationale, str) and quality_rationale.strip():
        return None

    return f"{path}:{index}: non_allowlisted_source_missing_quality_rationale:{source}"


def onec_method_to_canonical_row(
    method: OneCMethod,
    bsl_root: Path,
    *,
    source: str,
    license_name: str,
    origin_ref: str,
    contour: str,
) -> dict[str, Any]:
    suffix = "процедуру" if method.kind == "Процедура" else "функцию"
    module_relpath = Path(method.module_path).resolve().relative_to(bsl_root.resolve()).as_posix()
    return build_canonical_row(
        user_prompt=f"Напиши {suffix} для {method.name} в 1С.",
        assistant_response=method.body,
        metadata={
            "source": source,
            "license": license_name,
            "origin_ref": f"{origin_ref}#{module_relpath}",
            "origin_base_ref": origin_ref,
            "origin_relpath": module_relpath,
            "contour": contour,
            "segment": "onec_bsl",
            "split": "train",
            "module_type": method.module_type,
            "method_name": method.name,
            "category": "code_generation",
        },
    )


def parse_instruction_output(payload: dict[str, Any]) -> tuple[str, str]:
    if isinstance(payload.get("instruction"), str) and isinstance(payload.get("output"), str):
        return payload["instruction"], payload["output"]
    if isinstance(payload.get("instruction"), str) and isinstance(payload.get("response"), str):
        return payload["instruction"], payload["response"]
    if isinstance(payload.get("input"), str) and isinstance(payload.get("output"), str):
        return payload["input"], payload["output"]
    text = payload.get("text")
    if isinstance(text, str):
        if "Instruction:" in text and "Response:" in text and text.strip().endswith(EOT_TOKEN):
            return text, ""
        match = USER_ASSISTANT_PATTERN.match(text)
        if match:
            return match.group("user"), match.group("assistant")
    raise ValueError("Unsupported sample format: expected instruction/output or text")


def load_segment_samples(
    path: Path,
    *,
    expected_segment: str,
    allowed_sources: set[str],
) -> list[PreparedSample]:
    rows = load_canonical_rows(path)
    failures: list[str] = []
    samples: list[PreparedSample] = []
    for index, row in enumerate(rows, start=1):
        reasons = validate_canonical_row(row)
        if reasons:
            failures.append(f"{path}:{index}: {','.join(reasons)}")
            continue
        source_reason = require_non_allowlisted_source_rationale(
            row,
            allowed_sources=allowed_sources,
            path=path,
            index=index,
        )
        if source_reason is not None:
            failures.append(source_reason)
            continue
        samples.append(
            PreparedSample(
                segment=expected_segment,
                source=str(row["metadata"]["source"]),
                text=format_sample(row["user_prompt"], row["assistant_response"]),
                metadata=dict(row["metadata"]),
            )
        )
    if failures:
        raise ValueError("\n".join(failures))
    return samples


def load_onec_samples(
    methods: list[OneCMethod],
    bsl_root: Path,
    *,
    source: str,
    license_name: str,
    origin_ref: str,
    contour: str,
) -> list[str]:
    failures: list[str] = []
    samples: list[PreparedSample] = []
    for method in methods:
        row = onec_method_to_canonical_row(
            method,
            bsl_root,
            source=source,
            license_name=license_name,
            origin_ref=origin_ref,
            contour=contour,
        )
        reasons = validate_canonical_row(row)
        if reasons:
            failures.append(f"{method.module_path}:{method.name}: {','.join(reasons)}")
            continue
        samples.append(
            PreparedSample(
                segment="onec_bsl",
                source=str(row["metadata"]["source"]),
                text=format_sample(row["user_prompt"], row["assistant_response"]),
                metadata=dict(row["metadata"]),
            )
        )
    if failures:
        raise ValueError("\n".join(failures))
    return samples


def validate_profile(profile: dict[str, Any]) -> None:
    required_top = {"profile_id", "volume", "mix", "release_gates", "source_allowlist"}
    missing = sorted(required_top - set(profile))
    if missing:
        raise ValueError(f"Profile is missing required keys: {', '.join(missing)}")
    mix = profile["mix"]
    for key in SEGMENT_ORDER:
        if key not in mix:
            raise ValueError(f"Profile mix key is missing: {key}")


def pick_counts(available: dict[str, int], mix: dict[str, Any]) -> dict[str, int]:
    ratios = {key: float(mix[key]) for key in SEGMENT_ORDER}
    for key, ratio in ratios.items():
        if ratio <= 0:
            raise ValueError(f"Mix ratio must be > 0 for segment '{key}'")
        if available[key] <= 0:
            raise ValueError(f"No samples available for segment '{key}'")
    total = min(int(available[key] / ratios[key]) for key in SEGMENT_ORDER)
    if total <= 0:
        raise ValueError("Unable to allocate release set: not enough source samples for mix")

    raw = {key: total * ratios[key] for key in SEGMENT_ORDER}
    counts = {key: int(raw[key]) for key in SEGMENT_ORDER}
    remainder = total - sum(counts.values())
    if remainder > 0:
        order = sorted(SEGMENT_ORDER, key=lambda key: raw[key] - counts[key], reverse=True)
        for key in order:
            if remainder == 0:
                break
            counts[key] += 1
            remainder -= 1
    return counts


def interleave_segments(
    segment_samples: dict[str, list[PreparedSample]],
    rng: random.Random,
) -> list[PreparedSample]:
    buckets = {name: list(rows) for name, rows in segment_samples.items()}
    for rows in buckets.values():
        rng.shuffle(rows)

    mixed: list[PreparedSample] = []
    while any(buckets.values()):
        active = [name for name in SEGMENT_ORDER if buckets[name]]
        rng.shuffle(active)
        for name in active:
            mixed.append(buckets[name].pop())
    return mixed


def validate_sample_format(rows: list[str]) -> dict[str, int]:
    invalid_missing_eot = 0
    invalid_missing_headers = 0
    raw_json_objects = 0
    for row in rows:
        text = row.strip()
        if RAW_JSON_PATTERN.match(text):
            raw_json_objects += 1
        if not text.endswith(EOT_TOKEN):
            invalid_missing_eot += 1
        if "Instruction:" not in text or "Response:" not in text:
            invalid_missing_headers += 1
    return {
        "invalid_missing_eot": invalid_missing_eot,
        "invalid_missing_headers": invalid_missing_headers,
        "raw_json_objects": raw_json_objects,
    }


def validate_mix(counts: dict[str, int], mix: dict[str, Any]) -> list[str]:
    total = sum(counts.values())
    tolerance = float(mix["tolerance_pp"]) / 100.0
    reasons: list[str] = []
    for key in SEGMENT_ORDER:
        expected = float(mix[key])
        actual = counts[key] / total if total else 0.0
        if abs(actual - expected) > tolerance:
            reasons.append(
                f"mix[{key}]={actual:.4f} out of range around expected={expected:.4f} tolerance={tolerance:.4f}"
            )
    return reasons


def calculate_actual_mix(counts: dict[str, int]) -> dict[str, float]:
    total = sum(counts.values())
    if total == 0:
        return {key: 0.0 for key in SEGMENT_ORDER}
    return {key: round(counts[key] / total, 6) for key in SEGMENT_ORDER}


def build_shuffle_report(samples: list[PreparedSample], seed: int) -> dict[str, Any]:
    segment_order = [sample.segment for sample in samples]
    preview = segment_order[: min(16, len(segment_order))]
    switches = sum(
        1 for previous, current in zip(segment_order, segment_order[1:]) if previous != current
    )
    digest = hashlib.sha256("\n".join(segment_order).encode("utf-8")).hexdigest()
    return {
        "strategy": "segment_interleave_shuffle",
        "seed": seed,
        "segment_order_preview": preview,
        "segment_switches": switches,
        "segment_order_sha256": digest,
    }


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    profile_path = Path(args.profile).resolve()
    bsl_root = Path(args.bsl_root).resolve()
    coding_jsonl = Path(args.coding_jsonl).resolve()
    ru_jsonl = Path(args.ru_jsonl).resolve()
    output_text = Path(args.output_text).resolve()
    report_path = Path(args.report_output).resolve()

    profile = read_json(profile_path)
    validate_profile(profile)
    source_allowlist = build_source_allowlist(profile)

    methods = collect_onec_methods(bsl_root)
    onec_samples = load_onec_samples(
        methods,
        bsl_root,
        source=args.bsl_source,
        license_name=args.bsl_license,
        origin_ref=args.bsl_origin_ref,
        contour=args.bsl_contour,
    )
    coding_samples = load_segment_samples(
        coding_jsonl,
        expected_segment="coding_general",
        allowed_sources=source_allowlist.get("coding_general", set()),
    )
    ru_samples = load_segment_samples(
        ru_jsonl,
        expected_segment="ru_identity",
        allowed_sources=source_allowlist.get("ru_identity", set()),
    )
    available = {
        "onec_bsl": len(onec_samples),
        "coding_general": len(coding_samples),
        "ru_identity": len(ru_samples),
    }

    rng = random.Random(args.seed)
    counts = pick_counts(available, profile["mix"])
    selected = {
        "onec_bsl": rng.sample(onec_samples, counts["onec_bsl"]),
        "coding_general": rng.sample(coding_samples, counts["coding_general"]),
        "ru_identity": rng.sample(ru_samples, counts["ru_identity"]),
    }
    mixed = interleave_segments(selected, rng)

    output_text.parent.mkdir(parents=True, exist_ok=True)
    output_text.write_text("".join(sample.text for sample in mixed), encoding="utf-8")

    format_stats = validate_sample_format([sample.text for sample in mixed])
    mix_reasons = validate_mix(counts, profile["mix"])
    actual_mix = calculate_actual_mix(counts)
    module_type_counts = {
        "common": sum(1 for row in methods if row.module_type == "common"),
        "manager": sum(1 for row in methods if row.module_type == "manager"),
        "object": sum(1 for row in methods if row.module_type == "object"),
    }
    shuffle_report = build_shuffle_report(mixed, args.seed)

    reasons: list[str] = []
    for key, value in module_type_counts.items():
        if value == 0:
            reasons.append(f"module_coverage_missing:{key}")
    if format_stats["raw_json_objects"] > 0:
        reasons.append(f"raw_json_objects={format_stats['raw_json_objects']}")
    if format_stats["invalid_missing_eot"] > 0:
        reasons.append(f"invalid_missing_eot={format_stats['invalid_missing_eot']}")
    if format_stats["invalid_missing_headers"] > 0:
        reasons.append(f"invalid_missing_headers={format_stats['invalid_missing_headers']}")
    reasons.extend(mix_reasons)

    hard_min_mb = (
        int(args.hard_min_mb)
        if args.hard_min_mb is not None
        else int(profile["volume"]["hard_min_mb"])
    )
    output_size_mb = output_text.stat().st_size / (1024 * 1024)
    if output_size_mb < hard_min_mb:
        reasons.append(f"output_size_mb={output_size_mb:.4f} < hard_min_mb={hard_min_mb}")

    report = {
        "profile_id": profile["profile_id"],
        "profile_path": str(profile_path),
        "seed": args.seed,
        "inputs": {
            "bsl_root": str(bsl_root),
            "coding_jsonl": str(coding_jsonl),
            "ru_jsonl": str(ru_jsonl),
        },
        "counts": {
            "available": available,
            "selected": counts,
            "actual_mix": actual_mix,
            "module_type_coverage": module_type_counts,
        },
        "shuffle": shuffle_report,
        "gates": {
            "format": format_stats,
            "mix_tolerance_pp": profile["mix"]["tolerance_pp"],
            "hard_min_mb": hard_min_mb,
            "output_size_mb": round(output_size_mb, 6),
        },
        "quality_status": "PASS" if not reasons else "FAIL",
        "quality_reasons": reasons or ["quality gates passed"],
    }
    write_report(report_path, report)

    print(f"output: {output_text}")
    print(f"rows: {len(mixed)}")
    print(f"quality_status: {report['quality_status']}")
    print(f"report: {report_path}")
    return 0 if report["quality_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
