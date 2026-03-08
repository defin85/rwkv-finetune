#!/usr/bin/env python3
"""Lightweight BSL structural diagnostics for dataset quality gates."""

from __future__ import annotations

import re
from typing import Any


PROCEDURE_START_RE = re.compile(r"^\s*Процедура\b", re.IGNORECASE)
FUNCTION_START_RE = re.compile(r"^\s*Функция\b", re.IGNORECASE)
PROCEDURE_END_RE = re.compile(r"^\s*КонецПроцедуры\b", re.IGNORECASE)
FUNCTION_END_RE = re.compile(r"^\s*КонецФункции\b", re.IGNORECASE)
IF_START_RE = re.compile(r"^\s*Если\b.*\bТогда\b", re.IGNORECASE)
IF_END_RE = re.compile(r"^\s*КонецЕсли\b", re.IGNORECASE)
LOOP_START_RE = re.compile(r"^\s*(?:Для(?:\s+Каждого)?\b.*\bЦикл\b|Пока\b.*\bЦикл\b)", re.IGNORECASE)
LOOP_END_RE = re.compile(r"^\s*КонецЦикла\b", re.IGNORECASE)
TRY_START_RE = re.compile(r"^\s*Попытка\b", re.IGNORECASE)
TRY_END_RE = re.compile(r"^\s*КонецПопытки\b", re.IGNORECASE)
EXCEPTION_RE = re.compile(r"^\s*Исключение\b", re.IGNORECASE)
CASE_START_RE = re.compile(r"^\s*Выбор\b", re.IGNORECASE)
CASE_END_RE = re.compile(r"^\s*КонецВыбора\b", re.IGNORECASE)

ROUTINE_END_NAMES = {
    "procedure": "КонецПроцедуры",
    "function": "КонецФункции",
}
BLOCK_END_NAMES = {
    "if": "КонецЕсли",
    "loop": "КонецЦикла",
    "try": "КонецПопытки",
    "case": "КонецВыбора",
}


def _strip_bsl_line(line: str) -> str:
    chars: list[str] = []
    index = 0
    in_string = False
    while index < len(line):
        char = line[index]
        if in_string:
            if char == '"':
                if index + 1 < len(line) and line[index + 1] == '"':
                    index += 2
                    continue
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "/" and index + 1 < len(line) and line[index + 1] == "/":
            break
        chars.append(char)
        index += 1
    return "".join(chars).strip()


def _routine_start(stripped: str) -> str | None:
    if PROCEDURE_START_RE.match(stripped):
        return "procedure"
    if FUNCTION_START_RE.match(stripped):
        return "function"
    return None


def _routine_end(stripped: str) -> str | None:
    if PROCEDURE_END_RE.match(stripped):
        return "procedure"
    if FUNCTION_END_RE.match(stripped):
        return "function"
    return None


def _block_start(stripped: str) -> str | None:
    if IF_START_RE.match(stripped):
        return "if"
    if LOOP_START_RE.match(stripped):
        return "loop"
    if TRY_START_RE.match(stripped):
        return "try"
    if CASE_START_RE.match(stripped):
        return "case"
    return None


def _block_end(stripped: str) -> str | None:
    if IF_END_RE.match(stripped):
        return "if"
    if LOOP_END_RE.match(stripped):
        return "loop"
    if TRY_END_RE.match(stripped):
        return "try"
    if CASE_END_RE.match(stripped):
        return "case"
    return None


def _pop_unclosed_frames(stack: list[dict[str, Any]], reasons: list[str], frame_index: int) -> None:
    for frame in reversed(stack[frame_index + 1 :]):
        reasons.append(f"bsl_unclosed_{frame['kind']}[line={frame['line']}]")
    del stack[frame_index + 1 :]


def diagnose_bsl_text(text: str) -> list[str]:
    reasons: list[str] = []
    stack: list[dict[str, Any]] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = _strip_bsl_line(line)
        if not stripped:
            continue

        routine_start = _routine_start(stripped)
        if routine_start is not None:
            if any(frame["frame_type"] == "routine" for frame in stack):
                reasons.append(f"bsl_nested_routine[line={line_number}]")
            stack.append({"frame_type": "routine", "kind": routine_start, "line": line_number})
            continue

        routine_end = _routine_end(stripped)
        if routine_end is not None:
            routine_indexes = [index for index, frame in enumerate(stack) if frame["frame_type"] == "routine"]
            if not routine_indexes:
                reasons.append(f"bsl_orphan_routine_end[line={line_number}]={ROUTINE_END_NAMES[routine_end]}")
                continue
            routine_index = routine_indexes[-1]
            _pop_unclosed_frames(stack, reasons, routine_index)
            routine_frame = stack[routine_index]
            if routine_frame["kind"] != routine_end:
                expected = ROUTINE_END_NAMES[routine_frame["kind"]]
                actual = ROUTINE_END_NAMES[routine_end]
                reasons.append(
                    f"bsl_mismatched_routine_end[line={line_number}]={actual} expected={expected}"
                )
            stack.pop()
            continue

        block_start = _block_start(stripped)
        if block_start is not None:
            stack.append({"frame_type": "block", "kind": block_start, "line": line_number})
            continue

        if EXCEPTION_RE.match(stripped):
            if not stack:
                reasons.append(f"bsl_orphan_exception_branch[line={line_number}]")
                continue
            top = stack[-1]
            if top["kind"] != "try":
                reasons.append(f"bsl_misplaced_exception_branch[line={line_number}]")
                continue
            if top.get("exception_seen"):
                reasons.append(f"bsl_duplicate_exception_branch[line={line_number}]")
                continue
            top["exception_seen"] = True
            continue

        block_end = _block_end(stripped)
        if block_end is None:
            continue
        block_indexes = [
            index
            for index, frame in enumerate(stack)
            if frame["frame_type"] == "block" and frame["kind"] == block_end
        ]
        if not block_indexes:
            reasons.append(f"bsl_orphan_{block_end}_end[line={line_number}]")
            continue
        block_index = block_indexes[-1]
        _pop_unclosed_frames(stack, reasons, block_index)
        stack.pop()

    for frame in reversed(stack):
        reasons.append(f"bsl_unclosed_{frame['kind']}[line={frame['line']}]")
    return reasons
