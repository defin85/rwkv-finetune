#!/usr/bin/env python3
"""Build deterministic repo/time dataset splits from canonical rows."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import (
    DEFAULT_EVAL_SPLIT_CATEGORIES,
    DEFAULT_REPO_METADATA_KEYS,
    DEFAULT_TIME_METADATA_KEYS,
    build_release_manifest,
    load_canonical_rows,
    sha256_file,
    split_rows_by_repo_time,
    write_canonical_rows,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Split canonical dataset rows into train and dedicated eval buckets using repo/time boundaries."
    )
    parser.add_argument("--input", required=True, help="Path to canonical JSONL input.")
    parser.add_argument("--train-output", required=True, help="Path to output train JSONL.")
    parser.add_argument("--eval-output", required=True, help="Path to output combined eval JSONL.")
    parser.add_argument(
        "--eval-generation-output",
        required=True,
        help="Path to output dedicated code-generation eval JSONL.",
    )
    parser.add_argument(
        "--eval-refactoring-output",
        required=True,
        help="Path to output dedicated refactoring eval JSONL.",
    )
    parser.add_argument("--manifest-output", required=True, help="Path to output manifest JSON.")
    parser.add_argument("--dataset-name", required=True, help="Dataset name.")
    parser.add_argument("--dataset-version", default="v0", help="Dataset version label.")
    parser.add_argument("--created-by", default="scripts/split_dataset_release.py")
    parser.add_argument(
        "--created-at",
        help="Optional release timestamp override. Defaults to deterministic source-derived policy.",
    )
    parser.add_argument(
        "--repo-key",
        action="append",
        default=None,
        help="Metadata key candidate used to resolve repository boundaries. Repeat for precedence order.",
    )
    parser.add_argument(
        "--time-key",
        action="append",
        default=None,
        help="Metadata key candidate used to resolve temporal ordering. Repeat for precedence order.",
    )
    parser.add_argument("--enforce-balance", action="store_true", help="Enable train category balance gate.")
    return parser.parse_args()


def artifact_summary(path: Path, rows_total: int) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "rows_total": rows_total,
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    train_output = Path(args.train_output).resolve()
    eval_output = Path(args.eval_output).resolve()
    eval_generation_output = Path(args.eval_generation_output).resolve()
    eval_refactoring_output = Path(args.eval_refactoring_output).resolve()
    manifest_output = Path(args.manifest_output).resolve()
    repo_keys = tuple(args.repo_key or DEFAULT_REPO_METADATA_KEYS)
    time_keys = tuple(args.time_key or DEFAULT_TIME_METADATA_KEYS)

    try:
        rows = load_canonical_rows(input_path)
        rows_by_split, split_report = split_rows_by_repo_time(
            rows,
            repo_keys=repo_keys,
            time_keys=time_keys,
            eval_split_categories=dict(DEFAULT_EVAL_SPLIT_CATEGORIES),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    manifest_rows = {
        "train": rows_by_split["train"],
        "eval_generation": rows_by_split["eval_generation"],
        "eval_refactoring": rows_by_split["eval_refactoring"],
    }
    write_canonical_rows(train_output, manifest_rows["train"])
    write_canonical_rows(eval_generation_output, manifest_rows["eval_generation"])
    write_canonical_rows(eval_refactoring_output, manifest_rows["eval_refactoring"])
    write_canonical_rows(eval_output, rows_by_split["eval"])

    manifest = build_release_manifest(
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
        created_by=args.created_by,
        rows_by_split=manifest_rows,
        created_at=args.created_at,
        split_artifacts={
            "train": artifact_summary(train_output, len(manifest_rows["train"])),
            "eval_generation": artifact_summary(eval_generation_output, len(manifest_rows["eval_generation"])),
            "eval_refactoring": artifact_summary(eval_refactoring_output, len(manifest_rows["eval_refactoring"])),
        },
        split_policy={
            "strategy": "repo_temporal_boundary",
            "repo_keys": list(repo_keys),
            "time_keys": list(time_keys),
            "resolved_repo_keys": split_report["resolved_repo_keys"],
            "resolved_time_keys": split_report["resolved_time_keys"],
            "repo_boundaries_total": split_report["repo_boundaries_total"],
            "repo_row_counts": split_report["repo_row_counts"],
            "eval_split_categories": dict(DEFAULT_EVAL_SPLIT_CATEGORIES),
            "split_time_ranges": split_report["split_time_ranges"],
            "combined_eval_artifact": artifact_summary(eval_output, len(rows_by_split["eval"])),
        },
        dedup_policy={
            "exact_hash_basis": "sha256(user_prompt + assistant_response)",
            "near_hash_basis": "sha256(normalized assistant_response)",
            "removed_from_train": split_report["removed_from_train"],
        },
        enforce_balance=args.enforce_balance,
        required_eval_categories=("code_generation", "refactoring"),
        eval_split_categories=dict(DEFAULT_EVAL_SPLIT_CATEGORIES),
    )

    manifest_output.parent.mkdir(parents=True, exist_ok=True)
    manifest_output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"dataset_name: {manifest['dataset_name']}")
    print(f"dataset_version: {manifest['dataset_version']}")
    print(f"quality_status: {manifest['quality_status']}")
    print(f"manifest: {manifest_output}")
    return 0 if manifest["quality_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
