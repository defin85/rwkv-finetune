#!/usr/bin/env python3
"""Validate canonical dataset release splits and write a release manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import build_release_manifest, load_canonical_rows, sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate canonical dataset release splits.")
    parser.add_argument("--train", required=True, help="Path to canonical train JSONL.")
    parser.add_argument("--manifest-output", required=True, help="Output manifest path.")
    parser.add_argument("--dataset-name", required=True, help="Dataset name.")
    parser.add_argument("--dataset-version", default="v0", help="Dataset version (for example v0 or v1.2).")
    parser.add_argument("--dev", help="Path to canonical dev JSONL.")
    parser.add_argument("--eval", help="Path to canonical eval JSONL.")
    parser.add_argument("--created-by", default="scripts/validate_dataset_release.py")
    parser.add_argument("--enforce-balance", action="store_true", help="Enable baseline category balance gate.")
    parser.add_argument(
        "--require-eval-category",
        action="append",
        default=[],
        help="Category that MUST exist in eval split. Repeat option for multiple categories.",
    )
    return parser.parse_args()


def artifact_summary(path: Path, rows_total: int) -> dict[str, object]:
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "rows_total": rows_total,
    }


def main() -> int:
    args = parse_args()
    manifest_output = Path(args.manifest_output).resolve()
    rows_by_split = {"train": load_canonical_rows(Path(args.train).resolve())}
    split_artifacts = {
        "train": artifact_summary(Path(args.train).resolve(), len(rows_by_split["train"])),
    }

    if args.dev:
        dev_path = Path(args.dev).resolve()
        rows_by_split["dev"] = load_canonical_rows(dev_path)
        split_artifacts["dev"] = artifact_summary(dev_path, len(rows_by_split["dev"]))
    if args.eval:
        eval_path = Path(args.eval).resolve()
        rows_by_split["eval"] = load_canonical_rows(eval_path)
        split_artifacts["eval"] = artifact_summary(eval_path, len(rows_by_split["eval"]))

    manifest = build_release_manifest(
        dataset_name=args.dataset_name,
        dataset_version=args.dataset_version,
        created_by=args.created_by,
        rows_by_split=rows_by_split,
        split_artifacts=split_artifacts,
        enforce_balance=args.enforce_balance,
        required_eval_categories=tuple(args.require_eval_category),
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
