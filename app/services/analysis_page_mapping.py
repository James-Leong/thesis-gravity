from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


FULLWIDTH_TRANSLATION = str.maketrans(
    {
        "０": "0",
        "１": "1",
        "２": "2",
        "３": "3",
        "４": "4",
        "５": "5",
        "６": "6",
        "７": "7",
        "８": "8",
        "９": "9",
        "Ⅰ": "I",
        "Ⅱ": "II",
        "Ⅲ": "III",
        "Ⅳ": "IV",
        "Ⅴ": "V",
        "Ⅵ": "VI",
        "Ⅶ": "VII",
        "Ⅷ": "VIII",
        "Ⅸ": "IX",
        "Ⅹ": "X",
        "Ｉ": "I",
        "Ｖ": "V",
        "Ｘ": "X",
        "Ｌ": "L",
        "Ｃ": "C",
        "Ｄ": "D",
        "Ｍ": "M",
    }
)

ROMAN_PATTERN = re.compile(r"^[IVXLCDM]+$")
ARABIC_PATTERN = re.compile(r"^\d{1,4}$")
ARABIC_WITH_PAGE_PATTERN = re.compile(r"^第?\s*(\d{1,4})\s*页?$")


@dataclass(frozen=True)
class PageLabelCandidate:
    kind: Literal["roman", "arabic"]
    label: str
    sequence_value: int


def map_document_page_labels(pages: list[object]) -> dict[int, PageLabelCandidate]:
    explicit_candidates: dict[int, PageLabelCandidate] = {}
    for page in pages:
        candidate = extract_page_label_candidate(getattr(page, "text", ""))
        if candidate is not None:
            explicit_candidates[getattr(page, "number")] = candidate

    resolved = dict(explicit_candidates)
    for kind in ("roman", "arabic"):
        anchors = sorted(
            (
                pdf_page,
                candidate.sequence_value,
            )
            for pdf_page, candidate in explicit_candidates.items()
            if candidate.kind == kind
        )
        if not anchors:
            continue

        for (left_pdf, left_value), (right_pdf, right_value) in zip(anchors, anchors[1:]):
            page_delta = right_pdf - left_pdf
            value_delta = right_value - left_value
            if page_delta <= 0 or page_delta != value_delta:
                continue
            for step in range(1, page_delta):
                pdf_page = left_pdf + step
                sequence_value = left_value + step
                if pdf_page in resolved:
                    continue
                label = _format_label(kind, sequence_value)
                if label is None:
                    continue
                resolved[pdf_page] = PageLabelCandidate(
                    kind=kind,
                    label=label,
                    sequence_value=sequence_value,
                )

        first_pdf, first_value = anchors[0]
        for pdf_page in range(first_pdf - 1, 0, -1):
            sequence_value = first_value - (first_pdf - pdf_page)
            if sequence_value < 1 or pdf_page in resolved:
                break
            label = _format_label(kind, sequence_value)
            if label is None:
                break
            resolved[pdf_page] = PageLabelCandidate(
                kind=kind,
                label=label,
                sequence_value=sequence_value,
            )

        last_pdf, last_value = anchors[-1]
        max_pdf = len(pages)
        for pdf_page in range(last_pdf + 1, max_pdf + 1):
            sequence_value = last_value + (pdf_page - last_pdf)
            if pdf_page in resolved:
                break
            label = _format_label(kind, sequence_value)
            if label is None:
                break
            resolved[pdf_page] = PageLabelCandidate(
                kind=kind,
                label=label,
                sequence_value=sequence_value,
            )

    return resolved


def extract_page_label_candidate(text: str) -> PageLabelCandidate | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return None

    candidate_lines = lines[:8] + lines[-8:]
    for line in candidate_lines:
        normalized = _normalize_label_text(line)
        if not normalized:
            continue

        arabic_match = ARABIC_WITH_PAGE_PATTERN.fullmatch(normalized)
        if arabic_match:
            value = int(arabic_match.group(1))
            return PageLabelCandidate(kind="arabic", label=str(value), sequence_value=value)

        if ARABIC_PATTERN.fullmatch(normalized):
            value = int(normalized)
            return PageLabelCandidate(kind="arabic", label=str(value), sequence_value=value)

        if ROMAN_PATTERN.fullmatch(normalized):
            value = _roman_to_int(normalized)
            if value is not None:
                return PageLabelCandidate(kind="roman", label=normalized, sequence_value=value)

    return None


def _normalize_label_text(line: str) -> str:
    normalized = line.translate(FULLWIDTH_TRANSLATION)
    normalized = normalized.replace(" ", "").replace("\u3000", "")
    return normalized.strip()


def _format_label(kind: Literal["roman", "arabic"], sequence_value: int) -> str | None:
    if kind == "arabic":
        return str(sequence_value)
    return _int_to_roman(sequence_value)


def _roman_to_int(value: str) -> int | None:
    roman_values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    previous = 0
    for char in reversed(value):
        current = roman_values.get(char)
        if current is None:
            return None
        if current < previous:
            total -= current
        else:
            total += current
            previous = current
    return total


def _int_to_roman(value: int) -> str | None:
    if value < 1 or value > 3999:
        return None
    numerals = [
        ("M", 1000),
        ("CM", 900),
        ("D", 500),
        ("CD", 400),
        ("C", 100),
        ("XC", 90),
        ("L", 50),
        ("XL", 40),
        ("X", 10),
        ("IX", 9),
        ("V", 5),
        ("IV", 4),
        ("I", 1),
    ]
    parts: list[str] = []
    remaining = value
    for symbol, number in numerals:
        while remaining >= number:
            parts.append(symbol)
            remaining -= number
    return "".join(parts)
