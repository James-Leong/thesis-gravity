from app.services.analysis_page_mapping import (
    extract_page_label_candidate,
    map_document_page_labels,
)
from app.services.analysis_rules import ExtractedPage


def test_extract_page_label_candidate_handles_roman_and_arabic() -> None:
    roman_text = "M 公司盈利能力分析及提升策略研究\nI\n摘 要"
    arabic_text = "M 公司盈利能力分析及提升策略研究\n23\n图4.3 M 公司净资产收益率折线"

    roman_candidate = extract_page_label_candidate(roman_text)
    arabic_candidate = extract_page_label_candidate(arabic_text)

    assert roman_candidate is not None
    assert roman_candidate.kind == "roman"
    assert roman_candidate.label == "I"
    assert roman_candidate.sequence_value == 1

    assert arabic_candidate is not None
    assert arabic_candidate.kind == "arabic"
    assert arabic_candidate.label == "23"
    assert arabic_candidate.sequence_value == 23


def test_map_document_page_labels_fills_missing_sequence_between_anchors() -> None:
    pages = [
        ExtractedPage(number=1, text=""),
        ExtractedPage(number=2, text="Title\nI\n摘要"),
        ExtractedPage(number=3, text="Abstract\nII"),
        ExtractedPage(number=4, text="目录"),
        ExtractedPage(number=5, text="目录"),
        ExtractedPage(number=6, text="图目录\nV"),
        ExtractedPage(number=7, text="表目录\nVI"),
        ExtractedPage(number=8, text="Title\n1\n绪论"),
        ExtractedPage(number=9, text="Title\n2\n正文"),
    ]

    mapping = map_document_page_labels(pages)

    assert mapping[2].label == "I"
    assert mapping[4].label == "III"
    assert mapping[5].label == "IV"
    assert mapping[8].label == "1"
    assert mapping[9].label == "2"
