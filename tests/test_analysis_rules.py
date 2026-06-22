from app.services.analysis_checklist import ChecklistDefinition
from app.services.analysis_rules import ExtractedPage, build_visual_page_index, evaluate_rule_check


def test_first_person_pronoun_rule_fails_when_we_is_present() -> None:
    definition = ChecklistDefinition(
        check_id="chk_pronoun",
        title="第一人称表述",
        source_section="论文的写法与内容 / 论文说法需严谨，语句需通顺、写法要规范",
        requirement="“文中大量用了“我们”甚至“我们在本章中提出....”与论文是作者一人独立完成的规则相冲突。”",
        layer="rule",
        detector="first_person_pronouns",
        severity="low",
    )
    pages = [
        ExtractedPage(number=1, text="本文介绍研究背景。"),
        ExtractedPage(number=2, text="我们在本章中提出一种新的方法。"),
    ]

    result = evaluate_rule_check(definition, pages, total_pages=2)

    assert result.status == "failed"
    assert result.pages == [2]


def test_reference_citation_rule_fails_when_body_missing_entries() -> None:
    definition = ChecklistDefinition(
        check_id="chk_refs",
        title="参考文献引用",
        source_section="论文的格式、结构和文字表达 / 参考文献要求（续）",
        requirement="文献未在正文中全部、按序、正确引用。",
        layer="rule",
        detector="reference_citations",
        severity="medium",
    )
    pages = [
        ExtractedPage(number=1, text="如文献[1]所示，方法有效。"),
        ExtractedPage(number=2, text="另一个观点见［2］。"),
        ExtractedPage(number=3, text="参考文献\n[1] Author A. Paper A. 2022.\n[2] Author B. Paper B. 2021."),
    ]

    result = evaluate_rule_check(definition, pages, total_pages=3)

    assert result.status == "passed"
    assert "55" not in result.rationale


def test_reference_entries_skip_toc_and_find_real_section() -> None:
    pages = [
        ExtractedPage(
            number=1,
            text="目录\n参考文献 ............................. 5\n第一章 绪论 .............................. 1",
        ),
        ExtractedPage(number=2, text="第一章 绪论\n本文[1]引用了文献。"),
        ExtractedPage(number=3, text="第二章 相关工作\n如［2］所述。"),
        ExtractedPage(number=4, text="结论"),
        ExtractedPage(number=5, text="参考文献\n[1] Author A. Paper A. 2022.\n[2] Author B. Paper B. 2021."),
    ]
    from app.services.analysis_rules import _extract_reference_entries, _extract_inline_citations

    refs = _extract_reference_entries(pages)
    assert len(refs) == 2
    assert refs[0].index == 1
    assert refs[-1].index == 2

    citations = _extract_inline_citations(pages)
    assert len(citations) == 2
    assert {c[0] for c in citations} == {1, 2}


def test_reference_entries_normalize_full_width_numbering() -> None:
    pages = [
        ExtractedPage(number=1, text="正文引用见［１］和［２］。"),
        ExtractedPage(number=2, text="参考文献\n［１］ Author A. Paper A. 2022.\n［２］ Author B. Paper B. 2021."),
    ]
    from app.services.analysis_rules import _extract_reference_entries, _extract_inline_citations

    refs = _extract_reference_entries(pages)
    citations = _extract_inline_citations(pages)

    assert [ref.index for ref in refs] == [1, 2]
    assert [citation[0] for citation in citations] == [1, 2]


def test_page_count_rule_passes_for_master_thesis_over_threshold() -> None:
    definition = ChecklistDefinition(
        check_id="chk_pages",
        title="页数要求",
        source_section="论文的格式、结构和文字表达 / 论文的字数与页数要求",
        requirement="硕士论文篇幅正文（不含参考文献）一般不少于50页，博士论文篇幅正文一般不少于100页。",
        layer="rule",
        detector="page_count",
        severity="medium",
    )
    pages = [ExtractedPage(number=1, text="硕士学位论文")] + [
        ExtractedPage(number=index, text=f"第 {index} 页内容") for index in range(2, 55)
    ]

    result = evaluate_rule_check(definition, pages, total_pages=len(pages))

    assert result.status == "passed"


def test_build_visual_page_index_prefers_caption_and_reference_pages() -> None:
    pages = [
        ExtractedPage(number=1, text="第一章 绪论\n本文结构如下。"),
        ExtractedPage(number=2, text="如图2-1所示，系统架构包括采集层与分析层。"),
        ExtractedPage(number=3, text="图2-1 系统总体架构"),
        ExtractedPage(number=4, text="进一步分析实验设置。"),
        ExtractedPage(number=5, text="表3-1 实验参数设置"),
        ExtractedPage(number=6, text="图目录\n图2-1 系统总体架构\n图4-2 消融实验结果"),
    ]

    index = build_visual_page_index(pages)

    assert index.caption_pages == [3, 5]
    assert index.reference_pages == [2]
    assert 6 not in index.candidate_pages
    assert index.image_pages == []


def test_figure_table_caption_extraction_ignores_inline_references() -> None:
    pages = [
        ExtractedPage(number=28, text="图4.1 M 公司基于财务指标的盈利能力评价\n表4.1 M 公司总资产收益率（%）"),
        ExtractedPage(
            number=29,
            text="图4.2 M 公司总资产收益率折线\n由表4.1 及图4.1 可以看出趋势。\n表4.2 M 公司净资产收益率（%）",
        ),
        ExtractedPage(number=30, text="图4.3 M 公司净资产收益率折线\n通过图4.2 我们可以清晰地看出变化。"),
    ]
    from app.services.analysis_rules import _extract_figure_table_captions, _find_numbering_issues

    captions = _extract_figure_table_captions(pages)
    assert [(caption.label, caption.page) for caption in captions] == [
        ("图4-1", 28),
        ("表4-1", 28),
        ("图4-2", 29),
        ("表4-2", 29),
        ("图4-3", 30),
    ]
    assert _find_numbering_issues([caption for caption in captions if caption.kind == "图"]) == []
    assert _find_numbering_issues([caption for caption in captions if caption.kind == "表"]) == []
