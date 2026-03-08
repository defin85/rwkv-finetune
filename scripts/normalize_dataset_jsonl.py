#!/usr/bin/env python3
"""Normalize legacy or canonical JSONL rows into the shared canonical sample contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import build_canonical_row, load_canonical_rows, validate_canonical_row


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Normalize JSONL rows into canonical dataset contract.")
    parser.add_argument("--input", required=True, help="Input JSONL path.")
    parser.add_argument("--output", required=True, help="Output canonical JSONL path.")
    parser.add_argument("--contour", required=True, choices=["core", "extended"])
    parser.add_argument("--segment", required=True, help="Segment id written to sample metadata.")
    parser.add_argument("--source", required=True, help="Source id written to sample metadata.")
    parser.add_argument("--license", required=True, help="License label written to sample metadata.")
    parser.add_argument("--origin-ref", required=True, help="Origin reference written to sample metadata.")
    parser.add_argument("--split", required=True, choices=["train", "dev", "eval"])
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    rows = load_canonical_rows(input_path)

    normalized: list[dict[str, object]] = []
    failures: list[str] = []
    for index, row in enumerate(rows, start=1):
        metadata = dict(row["metadata"])
        metadata.setdefault("contour", args.contour)
        metadata.setdefault("segment", args.segment)
        metadata.setdefault("source", args.source)
        metadata.setdefault("license", args.license)
        metadata.setdefault("origin_ref", args.origin_ref)
        metadata["split"] = args.split
        normalized_row = build_canonical_row(row["user_prompt"], row["assistant_response"], metadata)
        reasons = validate_canonical_row(normalized_row)
        if reasons:
            failures.append(f"row {index}: {','.join(reasons)}")
            continue
        normalized.append(normalized_row)

    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in normalized:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"rows: {len(normalized)}")
    print(f"output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
