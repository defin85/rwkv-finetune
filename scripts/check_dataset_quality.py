#!/usr/bin/env python3
"""Validate chat-formatted JSONL dataset quality for RWKV fine-tuning."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


USER_ASSISTANT_PATTERN = re.compile(
    r"^\s*User:\s*(?P<user>.*?)\s*Assistant:\s*(?P<assistant>.*?)\s*$",
    re.DOTALL,
)
QWEN_KEYWORD_PATTERN = re.compile(r"\bqwen\b", re.IGNORECASE)
NEGATIVE_PATTERN = re.compile(r"\b(нет|не\s+qwen|not|no)\b", re.IGNORECASE)
TRANSCRIPT_MARKER_PATTERN = re.compile(r"\b(User|Assistant)\s*:", re.IGNORECASE)
IDENTITY_BRAND_PATTERNS = (
    re.compile(r"\bchatgpt\b", re.IGNORECASE),
    re.compile(r"\bopenai\b", re.IGNORECASE),
    re.compile(r"\bgpt(?:-[0-9]+(?:\.[0-9]+)?)?\b", re.IGNORECASE),
)
IDENTITY_KEYWORDS = [
    "кто ты",
    "модель",
    "model",
    "представься",
    "назови",
    "идентифиц",
    "идентифика",
    "qwen",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check dataset quality and write manifest.")
    parser.add_argument("--input", required=True, help="Input JSONL dataset path.")
    parser.add_argument("--output", required=True, help="Output manifest path.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return non-zero exit code when quality_status is FAIL.",
    )
    parser.add_argument("--min-rows", type=int, default=200)
    parser.add_argument("--min-unique-ratio", type=float, default=0.95)
    parser.add_argument("--min-user-assistant-ratio", type=float, default=0.99)
    parser.add_argument("--min-identity-ratio", type=float, default=0.25)
    parser.add_argument("--max-top1-share", type=float, default=0.05)
    parser.add_argument("--max-qwen-negative-rows", type=int, default=0)
    parser.add_argument("--max-identity-brand-leak-rows", type=int, default=0)
    parser.add_argument("--max-transcript-leak-rows", type=int, default=0)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(path: Path) -> list[str]:
    rows: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at line {line_number}: {exc.msg}") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
                raise ValueError(f"Invalid row schema at line {line_number}: expected object with 'text' string")
            rows.append(payload["text"])
    return rows


def evaluate(rows: list[str], args: argparse.Namespace) -> dict[str, Any]:
    row_count = len(rows)
    unique_count = len(set(rows))
    unique_ratio = unique_count / row_count if row_count else 0.0

    format_ok = 0
    invalid_format_rows = 0
    identity_rows = 0
    qwen_negative_rows = 0
    assistant_missing_rwkv_rows = 0
    identity_brand_leak_rows = 0
    transcript_leak_rows = 0
    assistant_lengths: list[int] = []
    top_counter = Counter(rows)

    for row in rows:
        match = USER_ASSISTANT_PATTERN.match(row)
        if not match:
            invalid_format_rows += 1
            continue

        format_ok += 1
        user = " ".join(match.group("user").strip().split())
        assistant = " ".join(match.group("assistant").strip().split())
        assistant_lengths.append(len(assistant))
        if TRANSCRIPT_MARKER_PATTERN.search(assistant):
            transcript_leak_rows += 1

        is_identity = any(keyword in user.lower() for keyword in IDENTITY_KEYWORDS)
        if is_identity:
            identity_rows += 1
            if "RWKV-7" not in assistant:
                assistant_missing_rwkv_rows += 1
            if QWEN_KEYWORD_PATTERN.search(user) and NEGATIVE_PATTERN.search(assistant):
                qwen_negative_rows += 1
            if any(pattern.search(assistant) for pattern in IDENTITY_BRAND_PATTERNS):
                identity_brand_leak_rows += 1

    user_assistant_ratio = format_ok / row_count if row_count else 0.0
    identity_ratio = identity_rows / row_count if row_count else 0.0
    top1_share = (top_counter.most_common(1)[0][1] / row_count) if row_count else 0.0

    reasons: list[str] = []
    if row_count < args.min_rows:
        reasons.append(f"rows_total={row_count} < min_rows={args.min_rows}")
    if unique_ratio < args.min_unique_ratio:
        reasons.append(
            f"unique_ratio={unique_ratio:.4f} < min_unique_ratio={args.min_unique_ratio:.4f}"
        )
    if user_assistant_ratio < args.min_user_assistant_ratio:
        reasons.append(
            "user_assistant_ratio="
            f"{user_assistant_ratio:.4f} < min_user_assistant_ratio={args.min_user_assistant_ratio:.4f}"
        )
    if identity_ratio < args.min_identity_ratio:
        reasons.append(
            f"identity_ratio={identity_ratio:.4f} < min_identity_ratio={args.min_identity_ratio:.4f}"
        )
    if top1_share > args.max_top1_share:
        reasons.append(f"top1_share={top1_share:.4f} > max_top1_share={args.max_top1_share:.4f}")
    if qwen_negative_rows > args.max_qwen_negative_rows:
        reasons.append(
            "qwen_negative_rows="
            f"{qwen_negative_rows} > max_qwen_negative_rows={args.max_qwen_negative_rows}"
        )
    if identity_brand_leak_rows > args.max_identity_brand_leak_rows:
        reasons.append(
            "identity_brand_leak_rows="
            f"{identity_brand_leak_rows} > max_identity_brand_leak_rows={args.max_identity_brand_leak_rows}"
        )
    if transcript_leak_rows > args.max_transcript_leak_rows:
        reasons.append(
            "transcript_leak_rows="
            f"{transcript_leak_rows} > max_transcript_leak_rows={args.max_transcript_leak_rows}"
        )
    if assistant_missing_rwkv_rows > 0:
        reasons.append(f"identity_rows_missing_rwkv={assistant_missing_rwkv_rows}")

    quality_status = "PASS" if not reasons else "FAIL"
    return {
        "quality_status": quality_status,
        "quality_reasons": reasons or ["quality gates passed"],
        "metrics": {
            "rows_total": row_count,
            "rows_unique": unique_count,
            "unique_ratio": round(unique_ratio, 6),
            "user_assistant_rows": format_ok,
            "invalid_format_rows": invalid_format_rows,
            "user_assistant_ratio": round(user_assistant_ratio, 6),
            "identity_rows": identity_rows,
            "identity_ratio": round(identity_ratio, 6),
            "identity_rows_missing_rwkv": assistant_missing_rwkv_rows,
            "qwen_negative_rows": qwen_negative_rows,
            "identity_brand_leak_rows": identity_brand_leak_rows,
            "transcript_leak_rows": transcript_leak_rows,
            "top1_share": round(top1_share, 6),
            "assistant_length_avg": round(sum(assistant_lengths) / len(assistant_lengths), 2)
            if assistant_lengths
            else 0.0,
            "assistant_length_max": max(assistant_lengths) if assistant_lengths else 0,
        },
    }


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Input dataset not found: {input_path}")

    rows = load_rows(input_path)
    report = evaluate(rows, args)
    manifest = {
        "dataset_path": str(input_path),
        "dataset_sha256": sha256_file(input_path),
        **report,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"dataset: {input_path}")
    print(f"rows: {manifest['metrics']['rows_total']}")
    print(f"quality_status: {manifest['quality_status']}")
    print(f"manifest: {output_path}")

    if args.strict and manifest["quality_status"] != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
