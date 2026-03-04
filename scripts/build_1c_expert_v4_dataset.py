#!/usr/bin/env python3
"""Build 1C-Expert-v4 plain-text train dataset with release gates."""

from __future__ import annotations

import argparse
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
        help="JSONL with coding samples (instruction/output or text).",
    )
    parser.add_argument(
        "--ru-jsonl",
        required=True,
        help="JSONL with RU identity/chat samples (instruction/output or text).",
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


def onec_method_to_sample(method: OneCMethod) -> str:
    suffix = "процедуру" if method.kind == "Процедура" else "функцию"
    instruction = f"Напиши {suffix} для {method.name} в 1С."
    return format_sample(instruction, method.body)


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


def load_segment_samples(path: Path) -> list[str]:
    samples: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number} expected JSON object")
            instruction, response = parse_instruction_output(payload)
            if response:
                samples.append(format_sample(instruction, response))
            else:
                samples.append(instruction.strip() + "\n")
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


def interleave_segments(segment_samples: dict[str, list[str]], rng: random.Random) -> list[str]:
    buckets = {name: list(rows) for name, rows in segment_samples.items()}
    for rows in buckets.values():
        rng.shuffle(rows)

    mixed: list[str] = []
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

    methods = collect_onec_methods(bsl_root)
    onec_samples = [onec_method_to_sample(row) for row in methods]
    coding_samples = load_segment_samples(coding_jsonl)
    ru_samples = load_segment_samples(ru_jsonl)
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
    output_text.write_text("".join(mixed), encoding="utf-8")

    format_stats = validate_sample_format(mixed)
    mix_reasons = validate_mix(counts, profile["mix"])
    module_type_counts = {
        "common": sum(1 for row in methods if row.module_type == "common"),
        "manager": sum(1 for row in methods if row.module_type == "manager"),
        "object": sum(1 for row in methods if row.module_type == "object"),
    }

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
            "module_type_coverage": module_type_counts,
        },
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
