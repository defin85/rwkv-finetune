#!/usr/bin/env python3
"""Shared dataset lifecycle helpers for canonical sample rows and release manifests."""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TASK_CATEGORIES = (
    "code_generation",
    "refactoring",
    "onec_query",
    "explanation_review",
)
DEFAULT_REPO_METADATA_KEYS = (
    "source_family_id",
    "repo_id",
    "canonical_repo_root",
    "origin_ref",
)
DEFAULT_TIME_METADATA_KEYS = (
    "commit_timestamp",
    "source_timestamp",
    "created_at",
)
DEFAULT_EVAL_SPLIT_CATEGORIES = {
    "eval_generation": "code_generation",
    "eval_refactoring": "refactoring",
}
STAGE_DIRS = {
    "raw": "data/raw",
    "interim": "data/interim",
    "curated": "data/curated",
}
CATEGORY_BASELINE = {
    "code_generation": 0.35,
    "refactoring": 0.35,
    "onec_query": 0.15,
    "explanation_review": 0.15,
}
VERSION_RE = re.compile(r"^v[0-9]+(?:\.[0-9]+)*$")
CHAT_TEXT_RE = re.compile(
    r"^\s*User:\s*(?P<user>.*?)\s*Assistant:\s*(?P<assistant>.*?)\s*$",
    re.DOTALL,
)
CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d()\-\s]{9,}\d)")
PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
TOKEN_RE = re.compile(r"\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*\S+", re.IGNORECASE)
PROC_RE = re.compile(r"(?im)^\s*Процедура\b")
END_PROC_RE = re.compile(r"(?im)^\s*КонецПроцедуры\b")
FUNC_RE = re.compile(r"(?im)^\s*Функция\b")
END_FUNC_RE = re.compile(r"(?im)^\s*КонецФункции\b")


def now_iso8601() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_near(value: str) -> str:
    return " ".join(value.split()).lower()


def normalize_user_prompt(value: str) -> str:
    return " ".join(value.strip().split())


def render_chat_text(user_prompt: str, assistant_response: str) -> str:
    user = normalize_user_prompt(user_prompt)
    assistant = assistant_response.strip()
    return f"User: {user}\nAssistant: {assistant}"


def parse_chat_text(text: str) -> tuple[str, str]:
    match = CHAT_TEXT_RE.match(text)
    if not match:
        raise ValueError("Unsupported text sample: expected 'User:'/'Assistant:' chat transcript")
    return normalize_user_prompt(match.group("user")), match.group("assistant").strip()


def validate_dataset_version(dataset_version: str) -> None:
    if not VERSION_RE.match(dataset_version):
        raise ValueError(f"Invalid dataset version: {dataset_version}")


def is_russian_text(text: str) -> bool:
    cyrillic = len(CYRILLIC_RE.findall(text))
    latin = len(LATIN_RE.findall(text))
    total_letters = cyrillic + latin
    if cyrillic == 0:
        return False
    if latin == 0:
        return True
    return (cyrillic / total_letters) >= 0.25


def infer_task_category(row: dict[str, Any]) -> str:
    metadata = row.get("metadata", {})
    category = metadata.get("category")
    if category in TASK_CATEGORIES:
        return str(category)

    user = str(row.get("user_prompt", "")).lower()
    assistant = str(row.get("assistant_response", "")).lower()
    text = f"{user}\n{assistant}"

    if any(token in text for token in ("рефактор", "перепиши", "обнови", "улучши", "оптимизируй", "smell")):
        return "refactoring"
    if any(token in text for token in ("объясни", "почему", "что делает", "ревью", "review", "разбери", "обзор")):
        return "explanation_review"
    if (
        any(token in text for token in ("1с", "запрос", "скд", "документ", "регистр", "справочник", "bsl"))
        and any(token in user for token in ("как", "что", "почему", "зачем", "?"))
    ):
        return "onec_query"
    return "code_generation"


def build_canonical_row(
    user_prompt: str,
    assistant_response: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_metadata = dict(metadata or {})
    row = {
        "user_prompt": normalize_user_prompt(user_prompt),
        "assistant_response": assistant_response.strip(),
        "metadata": row_metadata,
    }
    if row_metadata.get("category") not in TASK_CATEGORIES:
        row_metadata["category"] = infer_task_category(row)
    row["text"] = render_chat_text(row["user_prompt"], row["assistant_response"])
    return row


def canonical_row_exact_hash(row: dict[str, Any]) -> str:
    return sha256_text(f"{row['user_prompt']}\n{row['assistant_response']}")


def canonical_row_near_hash(row: dict[str, Any]) -> str:
    return sha256_text(normalize_near(row["assistant_response"]))


def validate_canonical_row(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if not isinstance(row.get("user_prompt"), str) or not row["user_prompt"].strip():
        reasons.append("missing_user_prompt")
    if not isinstance(row.get("assistant_response"), str) or not row["assistant_response"].strip():
        reasons.append("missing_assistant_response")
    metadata = row.get("metadata")
    if not isinstance(metadata, dict):
        reasons.append("missing_metadata")
        return reasons
    for field in ("source", "license", "origin_ref", "contour", "segment", "split"):
        value = metadata.get(field)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"missing_metadata.{field}")
    if not is_russian_text(str(row.get("user_prompt", ""))):
        reasons.append("user_prompt_not_russian")
    return reasons


def parse_canonical_or_legacy_row(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Expected JSON object row")

    metadata = dict(payload.get("metadata") or {})
    if "user_prompt" in payload and "assistant_response" in payload:
        return build_canonical_row(
            str(payload["user_prompt"]),
            str(payload["assistant_response"]),
            metadata,
        )

    if isinstance(payload.get("instruction"), str) and isinstance(payload.get("output"), str):
        return build_canonical_row(payload["instruction"], payload["output"], metadata)
    if isinstance(payload.get("instruction"), str) and isinstance(payload.get("response"), str):
        return build_canonical_row(payload["instruction"], payload["response"], metadata)
    if isinstance(payload.get("input"), str) and isinstance(payload.get("output"), str):
        return build_canonical_row(payload["input"], payload["output"], metadata)
    if isinstance(payload.get("text"), str):
        user_prompt, assistant_response = parse_chat_text(payload["text"])
        return build_canonical_row(user_prompt, assistant_response, metadata)
    raise ValueError("Unsupported row schema")


def load_canonical_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            try:
                rows.append(parse_canonical_or_legacy_row(payload))
            except ValueError as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    return rows


def write_canonical_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(build_canonical_row(row["user_prompt"], row["assistant_response"], row["metadata"]), ensure_ascii=False) + "\n")


def category_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {category: 0 for category in TASK_CATEGORIES}
    for row in rows:
        counts[infer_task_category(row)] += 1
    return counts


def validate_category_balance(
    counts: dict[str, int],
    baseline: dict[str, float] | None = None,
    tolerance_pp: int = 5,
) -> list[str]:
    baseline = baseline or CATEGORY_BASELINE
    total = sum(counts.values())
    if total == 0:
        return ["category_balance_total=0"]

    reasons: list[str] = []
    tolerance = tolerance_pp / 100.0
    for category, expected in baseline.items():
        actual = counts.get(category, 0) / total
        if abs(actual - expected) > tolerance:
            reasons.append(
                f"category_balance[{category}]={actual:.4f} expected={expected:.4f} tolerance={tolerance:.4f}"
            )
    generation = counts.get("code_generation", 0) / total
    refactoring = counts.get("refactoring", 0) / total
    if abs(generation - refactoring) > tolerance:
        reasons.append(
            f"category_balance_parity[generation_vs_refactoring]={abs(generation - refactoring):.4f} tolerance={tolerance:.4f}"
        )
    return reasons


def has_secret_or_pii(row: dict[str, Any]) -> bool:
    text = f"{row['user_prompt']}\n{row['assistant_response']}"
    return any(pattern.search(text) for pattern in (EMAIL_RE, PHONE_RE, PRIVATE_KEY_RE, TOKEN_RE))


def bsl_diagnostics(row: dict[str, Any]) -> list[str]:
    segment = str(row.get("metadata", {}).get("segment", ""))
    text = str(row.get("assistant_response", ""))
    if segment != "onec_bsl" and not any(token in text for token in ("Процедура", "Функция", "КонецПроцедуры", "КонецФункции")):
        return []
    reasons: list[str] = []
    if len(PROC_RE.findall(text)) != len(END_PROC_RE.findall(text)):
        reasons.append("bsl_unbalanced_procedures")
    if len(FUNC_RE.findall(text)) != len(END_FUNC_RE.findall(text)):
        reasons.append("bsl_unbalanced_functions")
    return reasons


def duplicate_stats(rows: list[dict[str, Any]]) -> dict[str, int]:
    exact_hashes = [canonical_row_exact_hash(row) for row in rows]
    near_hashes = [canonical_row_near_hash(row) for row in rows]
    return {
        "exact_duplicates": len(exact_hashes) - len(set(exact_hashes)),
        "near_duplicates": len(near_hashes) - len(set(near_hashes)),
    }


def cross_split_leakage(train_rows: list[dict[str, Any]], holdout_rows: list[dict[str, Any]]) -> dict[str, int]:
    train_exact = {canonical_row_exact_hash(row) for row in train_rows}
    train_near = {canonical_row_near_hash(row) for row in train_rows}
    holdout_exact = {canonical_row_exact_hash(row) for row in holdout_rows}
    holdout_near = {canonical_row_near_hash(row) for row in holdout_rows}
    return {
        "exact_overlap": len(train_exact & holdout_exact),
        "near_overlap": len(train_near & holdout_near),
    }


def row_metadata_value(row: dict[str, Any], key: str) -> Any:
    metadata = row.get("metadata", {})
    if isinstance(metadata, dict) and key in metadata:
        return metadata.get(key)
    return row.get(key)


def resolve_row_boundary_value(
    row: dict[str, Any],
    keys: tuple[str, ...],
    boundary_name: str,
) -> tuple[str, Any]:
    for key in keys:
        value = row_metadata_value(row, key)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return key, value
    origin_ref = str(row.get("metadata", {}).get("origin_ref", "unknown"))
    raise ValueError(f"missing_{boundary_name}_metadata[{','.join(keys)}] origin_ref={origin_ref}")


def parse_temporal_value(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("boolean value is not a valid timestamp")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("empty timestamp")
        if stripped.isdigit():
            return int(stripped)
        normalized = stripped.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    raise ValueError(f"unsupported timestamp type: {type(value).__name__}")


def clone_row_for_split(row: dict[str, Any], split_name: str) -> dict[str, Any]:
    metadata = dict(row.get("metadata", {}))
    metadata["split"] = split_name
    return build_canonical_row(row["user_prompt"], row["assistant_response"], metadata)


def split_rows_by_repo_time(
    rows: list[dict[str, Any]],
    repo_keys: tuple[str, ...] = DEFAULT_REPO_METADATA_KEYS,
    time_keys: tuple[str, ...] = DEFAULT_TIME_METADATA_KEYS,
    eval_split_categories: dict[str, str] | None = None,
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    eval_split_categories = eval_split_categories or dict(DEFAULT_EVAL_SPLIT_CATEGORIES)
    if not eval_split_categories:
        raise ValueError("eval_split_categories must not be empty")

    resolved_repo_keys: Counter[str] = Counter()
    resolved_time_keys: Counter[str] = Counter()
    grouped: dict[str, list[dict[str, Any]]] = {}

    for row in rows:
        normalized = build_canonical_row(row["user_prompt"], row["assistant_response"], row["metadata"])
        repo_key, repo_value = resolve_row_boundary_value(normalized, repo_keys, "repo")
        time_key, time_value = resolve_row_boundary_value(normalized, time_keys, "time")
        try:
            timestamp = parse_temporal_value(time_value)
        except ValueError as exc:
            raise ValueError(f"invalid_time_metadata[{time_key}]={time_value!r}") from exc

        resolved_repo_keys[repo_key] += 1
        resolved_time_keys[time_key] += 1
        grouped.setdefault(str(repo_value), []).append(
            {
                "row": normalized,
                "repo_boundary": str(repo_value),
                "timestamp": timestamp,
                "category": infer_task_category(normalized),
                "exact_hash": canonical_row_exact_hash(normalized),
                "near_hash": canonical_row_near_hash(normalized),
            }
        )

    buckets: dict[str, list[dict[str, Any]]] = {"train": []}
    for split_name in eval_split_categories:
        buckets[split_name] = []

    for repo_boundary in sorted(grouped):
        entries = sorted(
            grouped[repo_boundary],
            key=lambda item: (item["timestamp"], item["exact_hash"], item["row"]["user_prompt"]),
        )
        selected_exact_hashes: set[str] = set()
        for split_name, expected_category in eval_split_categories.items():
            candidate = next(
                (
                    item
                    for item in reversed(entries)
                    if item["category"] == expected_category and item["exact_hash"] not in selected_exact_hashes
                ),
                None,
            )
            if candidate is None:
                continue
            selected_exact_hashes.add(candidate["exact_hash"])
            buckets[split_name].append(clone_row_for_split(candidate["row"], split_name))

        for item in entries:
            if item["exact_hash"] in selected_exact_hashes:
                continue
            buckets["train"].append(clone_row_for_split(item["row"], "train"))

    missing_eval_splits = [split_name for split_name, split_rows in buckets.items() if split_name != "train" and not split_rows]
    if missing_eval_splits:
        raise ValueError(f"missing_eval_split_rows={','.join(sorted(missing_eval_splits))}")

    holdout_rows = [row for split_name, split_rows in buckets.items() if split_name != "train" for row in split_rows]
    holdout_exact = {canonical_row_exact_hash(row) for row in holdout_rows}
    holdout_near = {canonical_row_near_hash(row) for row in holdout_rows}
    removed_exact = 0
    removed_near = 0
    filtered_train: list[dict[str, Any]] = []
    for row in buckets["train"]:
        exact_hash = canonical_row_exact_hash(row)
        near_hash = canonical_row_near_hash(row)
        if exact_hash in holdout_exact:
            removed_exact += 1
            continue
        if near_hash in holdout_near:
            removed_near += 1
            continue
        filtered_train.append(row)
    buckets["train"] = filtered_train

    def sort_release_rows(split_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return sorted(
            split_rows,
            key=lambda row: (
                parse_temporal_value(resolve_row_boundary_value(row, time_keys, "time")[1]),
                canonical_row_exact_hash(row),
            ),
        )

    buckets["train"] = sort_release_rows(buckets["train"])
    for split_name in eval_split_categories:
        buckets[split_name] = sort_release_rows(buckets[split_name])

    combined_eval: list[dict[str, Any]] = []
    for split_name in eval_split_categories:
        combined_eval.extend(clone_row_for_split(row, "eval") for row in buckets[split_name])
    buckets["eval"] = sort_release_rows(combined_eval)

    split_time_ranges: dict[str, dict[str, int]] = {}
    for split_name, split_rows in buckets.items():
        if not split_rows:
            continue
        timestamps = [parse_temporal_value(resolve_row_boundary_value(row, time_keys, "time")[1]) for row in split_rows]
        split_time_ranges[split_name] = {
            "oldest_timestamp": min(timestamps),
            "newest_timestamp": max(timestamps),
        }

    report = {
        "strategy": "repo_temporal_boundary",
        "repo_boundaries_total": len(grouped),
        "repo_row_counts": {repo_boundary: len(grouped[repo_boundary]) for repo_boundary in sorted(grouped)},
        "resolved_repo_keys": dict(sorted(resolved_repo_keys.items())),
        "resolved_time_keys": dict(sorted(resolved_time_keys.items())),
        "eval_split_categories": dict(eval_split_categories),
        "removed_from_train": {
            "exact_duplicates": removed_exact,
            "near_duplicates": removed_near,
        },
        "split_rows": {split_name: len(split_rows) for split_name, split_rows in buckets.items()},
        "split_time_ranges": split_time_ranges,
    }
    return buckets, report


def build_source_summary(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    all_rows = [row for rows in rows_by_split.values() for row in rows]
    contours = Counter(str(row["metadata"].get("contour", "unknown")) for row in all_rows)
    segments = Counter(str(row["metadata"].get("segment", "unknown")) for row in all_rows)
    sources = Counter(str(row["metadata"].get("source", "unknown")) for row in all_rows)
    categories = Counter(infer_task_category(row) for row in all_rows)
    return {
        "rows_total": len(all_rows),
        "contours": dict(sorted(contours.items())),
        "segments": dict(sorted(segments.items())),
        "sources": dict(sorted(sources.items())),
        "categories": dict(sorted(categories.items())),
    }


def build_license_summary(rows_by_split: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    licenses = Counter(
        str(row["metadata"].get("license", "unknown")) for rows in rows_by_split.values() for row in rows
    )
    return {
        "licenses": dict(sorted(licenses.items())),
        "missing_license_rows": sum(1 for key, value in licenses.items() if key == "unknown" for _ in range(value)),
    }


def build_release_manifest(
    dataset_name: str,
    dataset_version: str,
    created_by: str,
    rows_by_split: dict[str, list[dict[str, Any]]],
    split_artifacts: dict[str, dict[str, Any]] | None = None,
    sampling_policy: dict[str, Any] | None = None,
    split_policy: dict[str, Any] | None = None,
    dedup_policy: dict[str, Any] | None = None,
    enforce_balance: bool = False,
    required_eval_categories: tuple[str, ...] = (),
    eval_split_categories: dict[str, str] | None = None,
) -> dict[str, Any]:
    validate_dataset_version(dataset_version)
    split_artifacts = split_artifacts or {}
    eval_split_categories = eval_split_categories or {}
    normalized: dict[str, list[dict[str, Any]]] = {}
    for split_name, rows in rows_by_split.items():
        normalized[split_name] = []
        for row in rows:
            normalized_row = build_canonical_row(row["user_prompt"], row["assistant_response"], row["metadata"])
            normalized_row["metadata"]["split"] = split_name
            normalized[split_name].append(normalized_row)

    reasons: list[str] = []
    quality_counts = {
        "invalid_schema_rows": 0,
        "invalid_ru_prompt_rows": 0,
        "secret_or_pii_rows": 0,
        "invalid_bsl_rows": 0,
        "split_leakage_exact": 0,
        "split_leakage_near": 0,
        "invalid_eval_split_rows": 0,
    }
    duplicate_summary: dict[str, dict[str, int]] = {}

    for split_name, rows in normalized.items():
        duplicate_summary[split_name] = duplicate_stats(rows)
        if duplicate_summary[split_name]["exact_duplicates"] > 0:
            reasons.append(
                f"{split_name}_exact_duplicates={duplicate_summary[split_name]['exact_duplicates']}"
            )
        if duplicate_summary[split_name]["near_duplicates"] > 0:
            reasons.append(
                f"{split_name}_near_duplicates={duplicate_summary[split_name]['near_duplicates']}"
            )
        for row in rows:
            row_reasons = validate_canonical_row(row)
            if row_reasons:
                quality_counts["invalid_schema_rows"] += 1
                if "user_prompt_not_russian" in row_reasons:
                    quality_counts["invalid_ru_prompt_rows"] += 1
            if has_secret_or_pii(row):
                quality_counts["secret_or_pii_rows"] += 1
            if bsl_diagnostics(row):
                quality_counts["invalid_bsl_rows"] += 1

    if quality_counts["invalid_schema_rows"] > 0:
        reasons.append(f"invalid_schema_rows={quality_counts['invalid_schema_rows']}")
    if quality_counts["secret_or_pii_rows"] > 0:
        reasons.append(f"secret_or_pii_rows={quality_counts['secret_or_pii_rows']}")
    if quality_counts["invalid_bsl_rows"] > 0:
        reasons.append(f"invalid_bsl_rows={quality_counts['invalid_bsl_rows']}")

    for split_name, expected_category in eval_split_categories.items():
        split_rows = normalized.get(split_name, [])
        if not split_rows:
            reasons.append(f"missing_eval_split[{split_name}]")
            continue
        actual_categories = {infer_task_category(row) for row in split_rows}
        if actual_categories != {expected_category}:
            quality_counts["invalid_eval_split_rows"] += len(split_rows)
            categories_joined = ",".join(sorted(actual_categories)) if actual_categories else "none"
            reasons.append(
                f"invalid_eval_split_category[{split_name}]={categories_joined} expected={expected_category}"
            )

    train_rows = normalized.get("train", [])
    holdout_rows = [row for split_name, rows in normalized.items() if split_name != "train" for row in rows]
    if train_rows and holdout_rows:
        leakage = cross_split_leakage(train_rows, holdout_rows)
        quality_counts["split_leakage_exact"] = leakage["exact_overlap"]
        quality_counts["split_leakage_near"] = leakage["near_overlap"]
        if leakage["exact_overlap"] > 0:
            reasons.append(f"split_leakage_exact={leakage['exact_overlap']}")
        if leakage["near_overlap"] > 0:
            reasons.append(f"split_leakage_near={leakage['near_overlap']}")

    train_categories = category_distribution(train_rows)
    if enforce_balance and train_rows:
        reasons.extend(validate_category_balance(train_categories))

    eval_category_rows = list(normalized.get("eval", []))
    for split_name in eval_split_categories:
        eval_category_rows.extend(normalized.get(split_name, []))
    if required_eval_categories and eval_category_rows:
        eval_categories = category_distribution(eval_category_rows)
        missing = [category for category in required_eval_categories if eval_categories.get(category, 0) == 0]
        if missing:
            reasons.append(f"missing_eval_categories={','.join(missing)}")

    manifest_splits: dict[str, Any] = {}
    for split_name, rows in normalized.items():
        artifact = split_artifacts.get(split_name, {})
        manifest_splits[split_name] = {
            "rows_total": len(rows),
            "categories": category_distribution(rows),
            "artifact": artifact,
        }

    manifest = {
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "created_at": now_iso8601(),
        "created_by": created_by,
        "storage_layout": STAGE_DIRS,
        "canonical_sample_contract": {
            "required_top_level_fields": ["user_prompt", "assistant_response", "metadata"],
            "required_metadata_fields": ["source", "license", "origin_ref", "contour", "segment", "split"],
            "compatibility_text_field": "text",
        },
        "source_summary": build_source_summary(normalized),
        "license_summary": build_license_summary(normalized),
        "sampling_policy": sampling_policy
        or {
            "ru_user_prompt_only": True,
            "task_categories": list(TASK_CATEGORIES),
            "category_baseline": CATEGORY_BASELINE,
        },
        "dedup_policy": dedup_policy
        or {
            "exact_hash_basis": "sha256(user_prompt + assistant_response)",
            "near_hash_basis": "sha256(normalized assistant_response)",
            "duplicate_summary": duplicate_summary,
        },
        "split_policy": split_policy
        or {
            "strategy": "explicit_splits",
            "required_eval_categories": list(required_eval_categories),
            "eval_split_categories": dict(eval_split_categories),
        },
        "quality_gates": {
            **quality_counts,
            "train_category_distribution": train_categories,
        },
        "splits": manifest_splits,
        "quality_status": "PASS" if not reasons else "FAIL",
        "quality_reasons": reasons or ["quality gates passed"],
    }
    return manifest
