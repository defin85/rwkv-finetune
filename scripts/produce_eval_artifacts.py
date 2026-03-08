#!/usr/bin/env python3
"""Produce category-level evaluation artifacts and hard-cases from runtime eval suites."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dataset_lifecycle import infer_task_category, load_canonical_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Produce domain/retention category artifacts and hard-cases from eval JSONL suites."
    )
    parser.add_argument("--run-name", required=True, help="Run name under runs/<run-name>.")
    parser.add_argument(
        "--run-dir",
        default="",
        help="Optional explicit run directory. Defaults to repository runs/<run-name>.",
    )
    parser.add_argument("--model", required=True, help="Checkpoint path used for inference.")
    parser.add_argument("--domain-eval-jsonl", required=True, help="Path to domain eval JSONL.")
    parser.add_argument("--retention-eval-jsonl", required=True, help="Path to retention eval JSONL.")
    parser.add_argument("--domain-output", required=True, help="Path to domain category summary JSON.")
    parser.add_argument("--retention-output", required=True, help="Path to retention category summary JSON.")
    parser.add_argument("--hard-cases-output", required=True, help="Path to hard-cases JSON.")
    parser.add_argument(
        "--inference-script",
        default=str(SCRIPT_DIR / "infer_albatross.py"),
        help="Inference script used to produce a completion for one prompt.",
    )
    parser.add_argument("--tokens", type=int, default=128, help="Max generated tokens per eval sample.")
    return parser.parse_args()


def read_inference_completion(inference_script: Path, model_path: Path, prompt: str, tokens: int) -> str:
    with tempfile.NamedTemporaryFile(prefix="eval-infer-", suffix=".json", delete=False) as handle:
        output_json = Path(handle.name)
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(inference_script),
                "--model",
                str(model_path),
                "--prompt",
                prompt,
                "--tokens",
                str(tokens),
                "--output-json",
                str(output_json),
            ],
            check=False,
            text=True,
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"inference_failed script={inference_script} stdout={result.stdout} stderr={result.stderr}"
            )
        payload = json.loads(output_json.read_text(encoding="utf-8"))
        samples = payload.get("samples")
        if not isinstance(samples, list) or not samples:
            raise ValueError("inference_output_missing_samples")
        completion = samples[0].get("completion")
        if not isinstance(completion, str):
            raise ValueError("inference_output_missing_completion")
        return completion.strip()
    finally:
        output_json.unlink(missing_ok=True)


def normalize_answer(text: str) -> str:
    return " ".join(text.lower().split())


def match_prediction(expected: str, predicted: str) -> bool:
    return normalize_answer(expected) == normalize_answer(predicted)


def resolve_category(row: dict[str, Any], suite_name: str) -> str:
    metadata = row.get("metadata", {})
    if isinstance(metadata, dict):
        eval_category = metadata.get("eval_category")
        if isinstance(eval_category, str) and eval_category.strip():
            return eval_category.strip()
        category = metadata.get("category")
        if isinstance(category, str) and category.strip() and suite_name == "domain_eval":
            return category.strip()
    if suite_name == "retention_eval":
        return "ru_general"
    return infer_task_category(row)


def build_default_action(suite_name: str, category: str) -> str:
    if suite_name == "domain_eval":
        return f"add more corrective samples for {category} in domain dataset"
    return f"expand retention coverage for {category} and replay buffer"


def failure_mode_for_completion(predicted: str) -> str:
    if not predicted.strip():
        return "empty_response"
    return "prediction_mismatch"


def evaluate_suite(
    suite_name: str,
    path: Path,
    inference_script: Path,
    model_path: Path,
    tokens: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, str]]]:
    rows = load_canonical_rows(path)
    category_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"samples_total": 0, "failures_total": 0}
    )
    hard_cases: list[dict[str, str]] = []

    for row in rows:
        prompt = f"User: {row['user_prompt']}\nAssistant:"
        predicted = read_inference_completion(inference_script, model_path, prompt, tokens)
        category = resolve_category(row, suite_name)
        bucket = category_totals[category]
        bucket["samples_total"] += 1
        if not match_prediction(row["assistant_response"], predicted):
            bucket["failures_total"] += 1
            hard_cases.append(
                {
                    "suite": suite_name,
                    "category": category,
                    "prompt": row["user_prompt"],
                    "failure_mode": failure_mode_for_completion(predicted),
                    "action": build_default_action(suite_name, category),
                }
            )

    normalized: dict[str, dict[str, Any]] = {}
    for category, totals in sorted(category_totals.items()):
        samples_total = int(totals["samples_total"])
        failures_total = int(totals["failures_total"])
        score = 0.0 if samples_total == 0 else (samples_total - failures_total) / samples_total
        normalized[category] = {
            "verdict": "PASS" if failures_total == 0 else "FAIL",
            "score": round(score, 6),
            "samples_total": samples_total,
            "failures_total": failures_total,
        }
    return normalized, hard_cases


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    run_dir = (
        Path(args.run_dir).resolve()
        if args.run_dir
        else Path(__file__).resolve().parents[1] / "runs" / args.run_name
    )
    if not run_dir.is_dir():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    model_path = Path(args.model).resolve()
    if not model_path.is_file():
        raise FileNotFoundError(f"Model checkpoint not found: {model_path}")

    inference_script = Path(args.inference_script).resolve()
    if not inference_script.is_file():
        raise FileNotFoundError(f"Inference script not found: {inference_script}")

    domain_output = Path(args.domain_output).resolve()
    retention_output = Path(args.retention_output).resolve()
    hard_cases_output = Path(args.hard_cases_output).resolve()

    domain_categories, domain_hard_cases = evaluate_suite(
        "domain_eval",
        Path(args.domain_eval_jsonl).resolve(),
        inference_script,
        model_path,
        args.tokens,
    )
    retention_categories, retention_hard_cases = evaluate_suite(
        "retention_eval",
        Path(args.retention_eval_jsonl).resolve(),
        inference_script,
        model_path,
        args.tokens,
    )
    hard_cases = [*domain_hard_cases, *retention_hard_cases]

    write_json(domain_output, domain_categories)
    write_json(retention_output, retention_categories)
    write_json(hard_cases_output, hard_cases)

    print(f"domain_categories: {domain_output}")
    print(f"retention_categories: {retention_output}")
    print(f"hard_cases: {hard_cases_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
