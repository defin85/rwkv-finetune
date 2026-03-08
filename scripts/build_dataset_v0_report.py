#!/usr/bin/env python3
"""Build a v0 dataset report from manifest and evaluation summary artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from eval_summary_contract import validate_eval_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a markdown/json v0 report from dataset manifest and eval summary."
    )
    parser.add_argument("--manifest", required=True, help="Path to release manifest JSON.")
    parser.add_argument("--eval-summary", required=True, help="Path to evaluation summary JSON.")
    parser.add_argument("--output-md", required=True, help="Path to output markdown report.")
    parser.add_argument("--output-json", required=True, help="Path to output machine-readable JSON summary.")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def build_summary(manifest: dict[str, Any], eval_summary: dict[str, Any]) -> dict[str, Any]:
    hard_cases = eval_summary.get("hard_cases")
    if not isinstance(hard_cases, list):
        hard_cases = []
    by_category = Counter(str(item.get("category", "unknown")) for item in hard_cases)
    return {
        "dataset": {
            "name": manifest.get("dataset_name", "unknown"),
            "version": manifest.get("dataset_version", "unknown"),
            "quality_status": manifest.get("quality_status", "unknown"),
            "rows_total": manifest.get("source_summary", {}).get("rows_total", 0),
            "splits": {
                split_name: split_payload.get("rows_total", 0)
                for split_name, split_payload in sorted((manifest.get("splits") or {}).items())
            },
            "contours": manifest.get("source_summary", {}).get("contours", {}),
            "segments": manifest.get("source_summary", {}).get("segments", {}),
            "categories": manifest.get("source_summary", {}).get("categories", {}),
        },
        "quality": {
            "quality_reasons": manifest.get("quality_reasons", []),
            "gates": manifest.get("quality_gates", {}),
        },
        "evaluation": {
            "overall_verdict": eval_summary.get("overall_verdict", "UNKNOWN"),
            "domain_eval": eval_summary.get("domain_eval", {}),
            "retention_eval": eval_summary.get("retention_eval", {}),
        },
        "backlog": {
            "hard_cases_total": len(hard_cases),
            "hard_cases_by_category": dict(sorted(by_category.items())),
            "hard_cases": hard_cases,
        },
    }


def build_markdown(summary: dict[str, Any]) -> str:
    dataset = summary["dataset"]
    quality = summary["quality"]
    evaluation = summary["evaluation"]
    backlog = summary["backlog"]

    lines = [
        "# Dataset v0 Report",
        "",
        f"- Dataset: `{dataset['name']}`",
        f"- Version: `{dataset['version']}`",
        f"- Quality status: `{dataset['quality_status']}`",
        f"- Rows total: `{dataset['rows_total']}`",
        "",
        "## Composition",
        "",
        f"- Splits: `{json.dumps(dataset['splits'], ensure_ascii=False, sort_keys=True)}`",
        f"- Contours: `{json.dumps(dataset['contours'], ensure_ascii=False, sort_keys=True)}`",
        f"- Segments: `{json.dumps(dataset['segments'], ensure_ascii=False, sort_keys=True)}`",
        f"- Categories: `{json.dumps(dataset['categories'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Quality Gates",
        "",
        f"- Quality reasons: `{json.dumps(quality['quality_reasons'], ensure_ascii=False)}`",
        f"- Gate metrics: `{json.dumps(quality['gates'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Evaluation",
        "",
        f"- Overall verdict: `{evaluation['overall_verdict']}`",
        f"- Domain eval: `{json.dumps(evaluation['domain_eval'], ensure_ascii=False, sort_keys=True)}`",
        f"- Retention eval: `{json.dumps(evaluation['retention_eval'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Backlog Hard-Cases",
        "",
        f"- Hard cases total: `{backlog['hard_cases_total']}`",
        f"- Hard cases by category: `{json.dumps(backlog['hard_cases_by_category'], ensure_ascii=False, sort_keys=True)}`",
    ]
    for item in backlog["hard_cases"]:
        lines.append(
            f"- [{item.get('category', 'unknown')}] {item.get('failure_mode', 'unspecified')}: "
            f"{item.get('prompt', 'n/a')} -> {item.get('action', 'n/a')}"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    manifest = read_json(Path(args.manifest).resolve())
    eval_summary = validate_eval_summary(read_json(Path(args.eval_summary).resolve()))
    summary = build_summary(manifest, eval_summary)

    output_md = Path(args.output_md).resolve()
    output_json = Path(args.output_json).resolve()
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown(summary), encoding="utf-8")
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"markdown: {output_md}")
    print(f"json: {output_json}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc
