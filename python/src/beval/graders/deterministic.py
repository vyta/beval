"""Deterministic built-in graders.

These graders evaluate Subject properties using deterministic logic
with no external dependencies. See SPEC §4.5 and GUIDE.md §1.
"""

from __future__ import annotations

import re
from typing import Any

from beval.graders import grader
from beval.types import EvalContext, Grade, GraderLayer, Subject

# Matches numbers with comma thousands separators (e.g. "1,000" or "32,548.45").
_COMMA_NUMBER_RE = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?")

# Matches any decimal number (e.g. "104.90", "1.00", "3.0").
_DECIMAL_RE = re.compile(r"\d+\.\d+")

# Matches any number (integer or decimal, with optional comma separators).
_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _strip_thousands_commas(text: str) -> str:
    """Remove thousands-separator commas from numbers in *text*."""
    return _COMMA_NUMBER_RE.sub(lambda m: m.group().replace(",", ""), text)


def _normalize_trailing_zeros(text: str) -> str:
    """Strip trailing zeros from decimals: 104.90 → 104.9, 1.00 → 1."""
    return _DECIMAL_RE.sub(
        lambda m: m.group().rstrip("0").rstrip("."), text
    )


def _normalize_numbers(text: str) -> str:
    """Normalize number formatting: strip commas and trailing zeros."""
    return _normalize_trailing_zeros(_strip_thousands_commas(text))


def _decimal_places(s: str) -> int:
    """Return the number of decimal places in a numeric string."""
    if "." in s:
        return len(s.rsplit(".", 1)[1])
    return 0


def _rounding_match(keyword: str, text: str) -> bool:
    """Check if *keyword* matches any number in *text* after rounding.

    Rounding is checked in both directions:
    - keyword rounded to output precision (e.g. kw ``1.577`` matches ``1.58``)
    - output rounded to keyword precision (e.g. kw ``9786`` matches ``9786.07``)

    At most 2 decimal places may be rounded away in either direction.
    """
    try:
        kw_val = float(keyword.replace(",", ""))
    except ValueError:
        return False
    kw_dp = _decimal_places(keyword.replace(",", ""))
    for m in _NUMBER_RE.finditer(text):
        token = m.group().replace(",", "")
        try:
            out_val = float(token)
        except ValueError:
            continue
        out_dp = _decimal_places(token)
        dp_diff = abs(kw_dp - out_dp)
        # Only allow rounding away at most 2 decimal places.
        if dp_diff > 2:
            continue
        # Round the more-precise value to the less-precise one's scale.
        if out_dp <= kw_dp and round(kw_val, out_dp) == out_val:
            return True
        if kw_dp <= out_dp and round(out_val, kw_dp) == kw_val:
            return True
    return False


@grader(
    "completion time should be under",
    layer=GraderLayer.DETERMINISTIC,
    metric="latency",
)
def _completion_time_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on response completion time."""
    if args:
        threshold = float(args[0])
    else:
        # Parse threshold from criterion string: "completion time should be under 120"
        import re as _re

        m = _re.search(r"[\d.]+", criterion)
        threshold = float(m.group()) if m else 30.0
    elapsed = subject.completion_time
    passed = elapsed <= threshold
    score = max(0.0, 1.0 - (elapsed / threshold)) if threshold > 0 else 0.0
    return Grade(
        criterion=criterion,
        score=score,
        metric="latency",
        passed=passed,
        detail=f"{elapsed:.1f}s of {threshold:.1f}s threshold",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should contain", layer=GraderLayer.DETERMINISTIC)
def _response_contains_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on keyword/phrase presence in output."""
    keyword = args[0].lower() if args else ""
    answer = subject.answer.lower()
    found = keyword in answer
    if not found:
        # Retry with normalized number formatting (commas, trailing zeros).
        found = _normalize_numbers(keyword) in _normalize_numbers(answer)
    if not found:
        # Retry with rounding: keyword 1.577 matches output 1.58.
        found = _rounding_match(keyword, answer)
    return Grade(
        criterion=criterion,
        score=1.0 if found else 0.0,
        metric="quality",
        passed=found,
        detail=f"'{keyword}' {'found' if found else 'not found'} in output",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should not contain", layer=GraderLayer.DETERMINISTIC)
def _response_not_contains_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on keyword/phrase absence in output."""
    keyword = args[0].lower() if args else ""
    answer = subject.answer.lower()
    absent = keyword not in answer
    if absent:
        # Also check with normalized number formatting (commas, trailing zeros).
        absent = _normalize_numbers(keyword) not in _normalize_numbers(answer)
    if absent:
        # Also check with rounding awareness.
        absent = not _rounding_match(keyword, answer)
    return Grade(
        criterion=criterion,
        score=1.0 if absent else 0.0,
        metric="quality",
        passed=absent,
        detail=f"'{keyword}' {'absent' if absent else 'found'} in output",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response length should be", layer=GraderLayer.DETERMINISTIC)
@grader("conversation length should be", layer=GraderLayer.DETERMINISTIC)
def _response_length_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on response length."""
    min_len = int(args[0]) if len(args) > 0 else 0
    max_len = int(args[1]) if len(args) > 1 else 10000
    length = len(subject.answer)
    in_range = min_len <= length <= max_len
    if in_range:
        score = 1.0
    elif length < min_len:
        score = max(0.0, length / min_len) if min_len > 0 else 0.0
    else:
        score = max(0.0, 1.0 - ((length - max_len) / max_len)) if max_len > 0 else 0.0
    return Grade(
        criterion=criterion,
        score=score,
        metric="quality",
        passed=in_range,
        detail=f"length {length} chars (range {min_len}-{max_len})",
        layer=GraderLayer.DETERMINISTIC,
    )


@grader("response should match", layer=GraderLayer.DETERMINISTIC)
def _response_matches_grader(
    criterion: str, args: list[Any], subject: Subject, context: EvalContext
) -> Grade:
    """Grade based on regex pattern match."""
    pattern = args[0] if args else ""
    matched = bool(re.search(pattern, subject.answer))
    return Grade(
        criterion=criterion,
        score=1.0 if matched else 0.0,
        metric="quality",
        passed=matched,
        detail=f"pattern '{pattern}' {'matched' if matched else 'not matched'}",
        layer=GraderLayer.DETERMINISTIC,
    )
