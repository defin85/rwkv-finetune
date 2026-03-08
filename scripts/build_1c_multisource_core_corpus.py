#!/usr/bin/env python3
"""Build a merged canonical 1C core corpus from local config/syntax/kb sources."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import (
    build_canonical_row,
    build_release_manifest,
    canonical_row_exact_hash,
    canonical_row_near_hash,
    sha256_file,
    validate_canonical_row,
    write_canonical_rows,
)


METHOD_PATTERN = re.compile(
    r"(?ims)^[ \t]*(?P<kind>Процедура|Функция)\s+"
    r"(?P<name>[A-Za-zА-Яа-я_][A-Za-zА-Яа-я0-9_]*)\s*\([^)]*\)"
    r"(?P<body>.*?)^[ \t]*Конец(?P<end>Процедуры|Функции)\s*;?",
)
REQUIRED_SOURCES = ("config_export", "syntax_helper_export", "kb1c_snapshot")
INVALID_PROVENANCE_VALUES = {"unknown"}


class MultiSourceError(RuntimeError):
    def __init__(self, reason: str, details: str | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.details = details or ""


@dataclass(frozen=True)
class OneCMethod:
    name: str
    kind: str
    body: str
    module_path: str
    module_type: str


@dataclass(frozen=True)
class SourceConfig:
    source_type: str
    path: Path
    source: str
    license_name: str
    origin_ref: str
    contour: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build merged canonical 1C core corpus from local multisource inputs.")
    parser.add_argument("--assembly-manifest", required=True, help="Path to multisource assembly manifest JSON.")
    parser.add_argument("--output-jsonl", required=True, help="Output path for merged canonical JSONL.")
    parser.add_argument("--report-output", required=True, help="Output path for release report JSON.")
    parser.add_argument("--hard-min-mb", type=int, default=300, help="Minimum merged core corpus size in MB.")
    parser.add_argument("--target-max-mb", type=int, default=1024, help="Maximum merged core corpus size in MB.")
    parser.add_argument("--dataset-version", default=None, help="Override dataset version from manifest.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MultiSourceError("invalid_manifest_schema", f"Expected JSON object in {path}")
    return payload


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise MultiSourceError("invalid_source_row", f"{path}:{line_number}: expected JSON object")
            rows.append(payload)
    return rows


def ensure_valid_source_field(source_type: str, field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MultiSourceError(f"missing_source_manifest[{source_type}].{field}")
    normalized = value.strip()
    if field in {"source", "license", "origin_ref"} and normalized.lower() in INVALID_PROVENANCE_VALUES:
        raise MultiSourceError(f"invalid_source_manifest[{source_type}].{field}")
    return normalized


def validate_kb_origin_ref(origin_ref: str) -> None:
    parsed = urlparse(origin_ref)
    if parsed.scheme not in {"http", "https"} or parsed.netloc != "kb.1ci.com":
        raise MultiSourceError("invalid_kb_origin_ref", origin_ref)


def parse_source_config(source_type: str, payload: Any) -> SourceConfig:
    if not isinstance(payload, dict):
        raise MultiSourceError(f"invalid_source_manifest[{source_type}]")
    path = Path(ensure_valid_source_field(source_type, "path", payload.get("path"))).resolve()
    source = ensure_valid_source_field(source_type, "source", payload.get("source"))
    license_name = ensure_valid_source_field(source_type, "license", payload.get("license"))
    origin_ref = ensure_valid_source_field(source_type, "origin_ref", payload.get("origin_ref"))
    contour = ensure_valid_source_field(source_type, "contour", payload.get("contour"))
    if contour != "core":
        raise MultiSourceError(f"invalid_source_manifest[{source_type}].contour", contour)
    if source_type == "config_export":
        if not path.is_dir():
            raise MultiSourceError("missing_source_path", f"{source_type}:{path}")
    else:
        if path.suffix.lower() != ".jsonl":
            raise MultiSourceError(f"unsupported_source_format[{source_type}]", str(path))
        if not path.is_file():
            raise MultiSourceError("missing_source_path", f"{source_type}:{path}")
    if source_type == "kb1c_snapshot":
        validate_kb_origin_ref(origin_ref)
    return SourceConfig(
        source_type=source_type,
        path=path,
        source=source,
        license_name=license_name,
        origin_ref=origin_ref,
        contour=contour,
    )


def validate_manifest(path: Path, dataset_version_override: str | None) -> tuple[dict[str, Any], dict[str, SourceConfig]]:
    manifest = read_json(path)
    dataset_name = manifest.get("dataset_name")
    if not isinstance(dataset_name, str) or not dataset_name.strip():
        raise MultiSourceError("missing_dataset_name")
    dataset_version = dataset_version_override or manifest.get("dataset_version")
    if not isinstance(dataset_version, str) or not dataset_version.strip():
        raise MultiSourceError("missing_dataset_version")
    sources_payload = manifest.get("sources")
    if not isinstance(sources_payload, dict):
        raise MultiSourceError("missing_sources")
    sources: dict[str, SourceConfig] = {}
    for source_type in REQUIRED_SOURCES:
        if source_type not in sources_payload:
            raise MultiSourceError(f"missing_required_source[{source_type}]")
        sources[source_type] = parse_source_config(source_type, sources_payload[source_type])
    return {
        "dataset_name": dataset_name.strip(),
        "dataset_version": dataset_version.strip(),
    }, sources


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
        methods.append(
            OneCMethod(
                name=match.group("name"),
                kind=kind,
                body=(kind + " " + source[match.start("name") : match.end()]).strip(),
                module_path="",
                module_type="unknown",
            )
        )
    return methods


def collect_config_methods(root: Path) -> list[OneCMethod]:
    methods: list[OneCMethod] = []
    for path in sorted(root.rglob("*.bsl")):
        module_type = infer_module_type(path)
        for extracted in extract_methods_from_text(path.read_text(encoding="utf-8", errors="ignore")):
            methods.append(
                OneCMethod(
                    name=extracted.name,
                    kind=extracted.kind,
                    body=extracted.body,
                    module_path=str(path),
                    module_type=module_type,
                )
            )
    return methods


def ensure_row_valid(row: dict[str, Any], *, source_type: str, label: str) -> dict[str, Any]:
    reasons = validate_canonical_row(row)
    if reasons:
        raise MultiSourceError("invalid_source_row", f"{source_type}:{label}:{','.join(reasons)}")
    return row


def config_rows(config: SourceConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    root = config.path.resolve()
    for method in collect_config_methods(root):
        relpath = Path(method.module_path).resolve().relative_to(root).as_posix()
        suffix = "процедуру" if method.kind == "Процедура" else "функцию"
        row = build_canonical_row(
            user_prompt=f"Напиши {suffix} для {method.name} в 1С.",
            assistant_response=method.body,
            metadata={
                "source": config.source,
                "license": config.license_name,
                "origin_ref": f"{config.origin_ref}#{relpath}",
                "origin_base_ref": config.origin_ref,
                "origin_relpath": relpath,
                "contour": config.contour,
                "segment": "onec_bsl",
                "split": "train",
                "source_type": config.source_type,
                "sample_class": "config_method",
                "module_type": method.module_type,
                "method_name": method.name,
                "category": "code_generation",
            },
        )
        rows.append(ensure_row_valid(row, source_type=config.source_type, label=relpath))
    return rows


def syntax_rows(config: SourceConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, payload in enumerate(read_jsonl(config.path), start=1):
        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        syntax = str(payload.get("syntax", "")).strip()
        example = str(payload.get("example", "")).strip()
        if not title:
            raise MultiSourceError("invalid_source_row", f"{config.source_type}:{config.path}:{index}:missing_title")
        response_parts = []
        if description:
            response_parts.append(f"Описание:\n{description}")
        if syntax:
            response_parts.append(f"Синтаксис:\n{syntax}")
        if example:
            response_parts.append(f"Пример:\n{example}")
        if not response_parts:
            raise MultiSourceError("invalid_source_row", f"{config.source_type}:{config.path}:{index}:empty_entry")
        origin_ref = str(payload.get("origin_ref", "")).strip() or f"{config.origin_ref}#{index}"
        row = build_canonical_row(
            user_prompt=f"Объясни синтаксис 1С для «{title}».",
            assistant_response="\n\n".join(response_parts),
            metadata={
                "source": config.source,
                "license": config.license_name,
                "origin_ref": origin_ref,
                "origin_base_ref": config.origin_ref,
                "contour": config.contour,
                "segment": "onec_bsl",
                "split": "train",
                "source_type": config.source_type,
                "sample_class": "syntax_helper_entry",
                "entry_title": title,
                "category": "explanation_review",
            },
        )
        rows.append(ensure_row_valid(row, source_type=config.source_type, label=f"row-{index}"))
    return rows


def kb_rows(config: SourceConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, payload in enumerate(read_jsonl(config.path), start=1):
        title = str(payload.get("title", "")).strip()
        content = str(payload.get("content", "")).strip()
        origin_ref = str(payload.get("origin_ref", "")).strip()
        if not title or not content or not origin_ref:
            raise MultiSourceError("invalid_source_row", f"{config.source_type}:{config.path}:{index}:missing_title_content_or_origin_ref")
        validate_kb_origin_ref(origin_ref)
        row = build_canonical_row(
            user_prompt=f"Объясни материал 1С по теме «{title}».",
            assistant_response=content,
            metadata={
                "source": config.source,
                "license": config.license_name,
                "origin_ref": origin_ref,
                "origin_base_ref": config.origin_ref,
                "contour": config.contour,
                "segment": "onec_bsl",
                "split": "train",
                "source_type": config.source_type,
                "sample_class": "kb1c_page",
                "page_title": title,
                "category": "explanation_review",
            },
        )
        rows.append(ensure_row_valid(row, source_type=config.source_type, label=f"row-{index}"))
    return rows


def dedup_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, int]]:
    exact_seen: set[str] = set()
    exact_deduped: list[dict[str, Any]] = []
    removed_exact = 0
    for row in rows:
        exact_hash = canonical_row_exact_hash(row)
        if exact_hash in exact_seen:
            removed_exact += 1
            continue
        exact_seen.add(exact_hash)
        exact_deduped.append(row)

    near_seen: set[str] = set()
    near_deduped: list[dict[str, Any]] = []
    removed_near = 0
    for row in exact_deduped:
        near_hash = canonical_row_near_hash(row)
        if near_hash in near_seen:
            removed_near += 1
            continue
        near_seen.add(near_hash)
        near_deduped.append(row)

    return near_deduped, {"removed_exact": removed_exact, "removed_near": removed_near}


def size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def failure_report(
    args: argparse.Namespace,
    *,
    manifest_path: Path,
    reason: str,
    details: str = "",
) -> dict[str, Any]:
    return {
        "assembly_manifest": str(manifest_path),
        "quality_status": "FAIL",
        "quality_reasons": [reason],
        "error_details": details,
        "counts": {
            "input_rows": {source_type: 0 for source_type in REQUIRED_SOURCES},
            "source_type_contribution": {source_type: 0 for source_type in REQUIRED_SOURCES},
            "duplicates_removed": {"exact": 0, "near": 0},
        },
        "gates": {
            "hard_min_mb": args.hard_min_mb,
            "target_max_mb": args.target_max_mb,
            "output_size_mb": 0.0,
            "deficit_to_hard_min_mb": float(args.hard_min_mb),
            "excess_over_target_max_mb": 0.0,
        },
    }


def main() -> int:
    args = parse_args()
    manifest_path = Path(args.assembly_manifest).resolve()
    output_jsonl = Path(args.output_jsonl).resolve()
    report_output = Path(args.report_output).resolve()

    try:
        manifest_meta, sources = validate_manifest(manifest_path, args.dataset_version)
        rows_by_source = {
            "config_export": config_rows(sources["config_export"]),
            "syntax_helper_export": syntax_rows(sources["syntax_helper_export"]),
            "kb1c_snapshot": kb_rows(sources["kb1c_snapshot"]),
        }
        input_rows = [row for source_rows in rows_by_source.values() for row in source_rows]
        merged_rows, dedup_stats = dedup_rows(input_rows)

        write_canonical_rows(output_jsonl, merged_rows)
        output_size_mb = size_mb(output_jsonl)
        reasons: list[str] = []
        if output_size_mb < args.hard_min_mb:
            reasons.append(f"output_size_mb={output_size_mb:.4f} < hard_min_mb={args.hard_min_mb}")
        if output_size_mb > args.target_max_mb:
            reasons.append(f"output_size_mb={output_size_mb:.4f} > target_max_mb={args.target_max_mb}")

        source_type_contribution = {source_type: 0 for source_type in REQUIRED_SOURCES}
        for row in merged_rows:
            source_type = str(row["metadata"].get("source_type", "")).strip()
            if source_type in source_type_contribution:
                source_type_contribution[source_type] += 1

        lifecycle_manifest = build_release_manifest(
            dataset_name=manifest_meta["dataset_name"],
            dataset_version=manifest_meta["dataset_version"],
            created_by="scripts/build_1c_multisource_core_corpus.py",
            rows_by_split={"train": merged_rows},
            split_artifacts={
                "train": {
                    "path": str(output_jsonl),
                    "sha256": sha256_file(output_jsonl),
                    "rows_total": len(merged_rows),
                }
            },
            enforce_balance=False,
            required_eval_categories=(),
            sampling_policy={
                "ru_user_prompt_only": True,
                "task_categories": ["code_generation", "refactoring", "onec_query", "explanation_review"],
                "source_types": list(REQUIRED_SOURCES),
            },
            split_policy={
                "strategy": "multisource_core_pre_mix",
                "required_eval_categories": [],
            },
            dedup_policy={
                "exact_hash_basis": "sha256(user_prompt + assistant_response)",
                "near_hash_basis": "sha256(normalized assistant_response)",
                "duplicate_summary": {"train": {"exact_duplicates": 0, "near_duplicates": 0}},
            },
        )
        combined_reasons = list(reasons)
        if lifecycle_manifest["quality_status"] != "PASS":
            combined_reasons.extend(
                reason for reason in lifecycle_manifest["quality_reasons"] if reason not in combined_reasons
            )
        report = {
            **lifecycle_manifest,
            "assembly_manifest": str(manifest_path),
            "counts": {
                "input_rows": {source_type: len(rows) for source_type, rows in rows_by_source.items()},
                "source_type_contribution": source_type_contribution,
                "duplicates_removed": {
                    "exact": dedup_stats["removed_exact"],
                    "near": dedup_stats["removed_near"],
                },
            },
            "gates": {
                "hard_min_mb": args.hard_min_mb,
                "target_max_mb": args.target_max_mb,
                "output_size_mb": round(output_size_mb, 6),
                "deficit_to_hard_min_mb": round(max(0.0, args.hard_min_mb - output_size_mb), 6),
                "excess_over_target_max_mb": round(max(0.0, output_size_mb - args.target_max_mb), 6),
            },
            "quality_status": "PASS" if not combined_reasons else "FAIL",
            "quality_reasons": combined_reasons or ["quality gates passed"],
        }
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"rows: {len(merged_rows)}")
        print(f"quality_status: {report['quality_status']}")
        print(f"report: {report_output}")
        return 0 if report["quality_status"] == "PASS" else 1
    except MultiSourceError as exc:
        report = failure_report(args, manifest_path=manifest_path, reason=exc.reason, details=exc.details)
        report_output.parent.mkdir(parents=True, exist_ok=True)
        report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("quality_status: FAIL")
        print(f"report: {report_output}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
