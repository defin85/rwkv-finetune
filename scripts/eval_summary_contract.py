#!/usr/bin/env python3
"""Shared machine-readable contract for adapter evaluation summaries."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


VALID_VERDICTS = {"PASS", "FAIL"}
HARD_CASE_REQUIRED_FIELDS = ("suite", "category", "prompt", "failure_mode", "action")
VALID_SUITES = {"domain_eval", "retention_eval"}


def now_iso8601_z() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json_file(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _normalize_verdict(value: Any, field_name: str) -> str:
    verdict = str(value).upper()
    if verdict not in VALID_VERDICTS:
        raise ValueError(f"{field_name}.invalid_verdict={value!r}")
    return verdict


def _normalize_non_negative_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name}.expected_int")
    if value < 0:
        raise ValueError(f"{field_name}.negative")
    return value


def _normalize_optional_score(value: Any, field_name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name}.expected_number")
    return float(value)


def normalize_category_summaries(payload: Any, suite_name: str) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict) or not payload:
        raise ValueError(f"{suite_name}.missing_categories")

    normalized: dict[str, dict[str, Any]] = {}
    for category_name, category_payload in sorted(payload.items()):
        if not isinstance(category_name, str) or not category_name.strip():
            raise ValueError(f"{suite_name}.invalid_category_name")
        if not isinstance(category_payload, dict):
            raise ValueError(f"{suite_name}.categories[{category_name}].expected_object")
        normalized_payload = {
            "verdict": _normalize_verdict(
                category_payload.get("verdict", "FAIL"),
                f"{suite_name}.categories[{category_name}]",
            ),
            "samples_total": _normalize_non_negative_int(
                category_payload.get("samples_total", 0),
                f"{suite_name}.categories[{category_name}].samples_total",
            ),
            "failures_total": _normalize_non_negative_int(
                category_payload.get("failures_total", 0),
                f"{suite_name}.categories[{category_name}].failures_total",
            ),
        }
        score = _normalize_optional_score(
            category_payload.get("score"),
            f"{suite_name}.categories[{category_name}].score",
        )
        if score is not None:
            normalized_payload["score"] = score
        normalized[category_name.strip()] = normalized_payload
    return normalized


def derive_verdict_from_categories(payload: Any, suite_name: str) -> str:
    categories = normalize_category_summaries(payload, suite_name)
    verdicts = {item["verdict"] for item in categories.values()}
    return "PASS" if verdicts == {"PASS"} else "FAIL"


def normalize_eval_section(section_name: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{section_name}.expected_object")
    normalized = {
        "verdict": _normalize_verdict(payload.get("verdict", "FAIL"), section_name),
        "categories": normalize_category_summaries(payload.get("categories"), section_name),
    }
    score = _normalize_optional_score(payload.get("score"), f"{section_name}.score")
    if score is not None:
        normalized["score"] = score
    return normalized


def normalize_hard_cases(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise ValueError("hard_cases.expected_list")

    normalized: list[dict[str, str]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"hard_cases[{index}].expected_object")
        normalized_item: dict[str, str] = {}
        for field_name in HARD_CASE_REQUIRED_FIELDS:
            value = item.get(field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"hard_cases[{index}].missing_{field_name}")
            normalized_item[field_name] = value.strip()
        if normalized_item["suite"] not in VALID_SUITES:
            raise ValueError(f"hard_cases[{index}].invalid_suite={normalized_item['suite']!r}")
        normalized.append(normalized_item)
    return normalized


def overall_verdict(domain_verdict: str, retention_verdict: str) -> str:
    return "PASS" if domain_verdict == "PASS" and retention_verdict == "PASS" else "FAIL"


def build_eval_summary(
    run_name: str,
    domain_verdict: str | None,
    retention_verdict: str | None,
    domain_categories: dict[str, Any],
    retention_categories: dict[str, Any],
    hard_cases: list[dict[str, Any]],
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_domain_verdict = domain_verdict or derive_verdict_from_categories(
        domain_categories,
        "domain_eval",
    )
    normalized_retention_verdict = retention_verdict or derive_verdict_from_categories(
        retention_categories,
        "retention_eval",
    )
    normalized_domain = normalize_eval_section(
        "domain_eval",
        {"verdict": normalized_domain_verdict, "categories": domain_categories},
    )
    normalized_retention = normalize_eval_section(
        "retention_eval",
        {"verdict": normalized_retention_verdict, "categories": retention_categories},
    )
    return {
        "schema_version": 1,
        "run_name": run_name,
        "created_at": created_at or now_iso8601_z(),
        "domain_eval": normalized_domain,
        "retention_eval": normalized_retention,
        "overall_verdict": overall_verdict(normalized_domain["verdict"], normalized_retention["verdict"]),
        "hard_cases": normalize_hard_cases(hard_cases),
    }


def validate_eval_summary(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("eval_summary.expected_object")
    normalized = {
        "schema_version": int(payload.get("schema_version", 1)),
        "run_name": str(payload.get("run_name", "unknown")),
        "created_at": str(payload.get("created_at", "unknown")),
        "domain_eval": normalize_eval_section("domain_eval", payload.get("domain_eval")),
        "retention_eval": normalize_eval_section("retention_eval", payload.get("retention_eval")),
        "hard_cases": normalize_hard_cases(payload.get("hard_cases")),
    }
    expected_overall = overall_verdict(
        normalized["domain_eval"]["verdict"],
        normalized["retention_eval"]["verdict"],
    )
    actual_overall = _normalize_verdict(payload.get("overall_verdict", expected_overall), "overall_verdict")
    if actual_overall != expected_overall:
        raise ValueError(f"overall_verdict.mismatch={actual_overall} expected={expected_overall}")
    normalized["overall_verdict"] = actual_overall
    return normalized
