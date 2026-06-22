from __future__ import annotations

import fitz
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.schemas.analysis import AnalysisCheck
from app.services.analysis_checklist import ChecklistDefinition, extract_query_terms


@dataclass(frozen=True)
class ExtractedPage:
    number: int
    text: str
    document_page_label: str | None = None
    document_page_number: int | None = None
    document_page_kind: str | None = None


@dataclass(frozen=True)
class VisualPageIndex:
    caption_pages: list[int]
    reference_pages: list[int]
    candidate_pages: list[int]
    image_pages: list[int]


def _is_likely_toc_page(page: ExtractedPage) -> bool:
    """Heuristic to skip table-of-contents / figure-directory pages."""
    if any(keyword in page.text for keyword in ("目录", "图目录", "表目录", "Contents")):
        return True
    # TOC lines are dominated by dots and page numbers.
    dot_leader_lines = 0
    for line in page.text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.count(".") >= 4 and re.search(r"\d+\s*$", stripped):
            dot_leader_lines += 1
    return dot_leader_lines >= 3


SENSITIVE_PAGE_PATTERNS = {
    "封面": ("学号", "姓名", "导师", "指导教师"),
    "扉页": ("指导小组",),
    "致谢": ("致谢",),
    "独创性声明": ("独创性声明", "签名"),
    "论文使用授权声明": ("论文使用授权声明", "导师签名", "作者签名"),
}

FIGURE_TABLE_DIRECTORY_PATTERNS = ("图目录", "表目录")
FIGURE_TABLE_CAPTION_PATTERNS = (
    re.compile(
        r"^\s*(图|表)\s*[0-9]{1,2}(?:[-.．][0-9]{1,3})?(?:\s*[（(][A-Za-z0-9一二三四五六七八九十]+[)）])?(?:\s*[:：].*|\s+.+)?$"
    ),
    re.compile(
        r"^\s*(Figure|Fig\.?|Table)\s+[0-9]{1,2}(?:[-.][0-9]{1,3})?(?:\s*[(:：.].*|\s+.+)?$",
        re.IGNORECASE,
    ),
)
FIGURE_TABLE_REFERENCE_PATTERNS = (
    re.compile(
        r"(如图|见图|参见图|如表|见表|参见表)\s*[0-9]{1,2}(?:[-.．][0-9]{1,3})?(?:\s*[（(][A-Za-z0-9一二三四五六七八九十]+[)）])?"
    ),
    re.compile(
        r"\b(Figure|Fig\.?|Table)\s+[0-9]{1,2}(?:[-.][0-9]{1,3})?(?:\s*[(:：.][^)）\n]*)?",
        re.IGNORECASE,
    ),
)


def evaluate_rule_check(
    definition: ChecklistDefinition,
    pages: list[ExtractedPage],
    total_pages: int,
) -> AnalysisCheck:
    detector = definition.detector
    if detector == "blind_review_redaction":
        return _evaluate_blind_review_redaction(definition, pages)
    if detector == "english_title_case":
        return _evaluate_english_title_case(definition, pages)
    if detector == "page_count":
        return _evaluate_page_count(definition, pages, total_pages)
    if detector == "reference_statistics":
        return _evaluate_reference_statistics(definition, pages)
    if detector == "reference_citations":
        return _evaluate_reference_citations(definition, pages)
    if detector == "figure_reference_placement":
        return _evaluate_figure_reference_placement(definition, pages)
    if detector == "figure_table_numbering":
        return _evaluate_figure_table_numbering(definition, pages)
    if detector == "first_person_pronouns":
        return _evaluate_first_person_pronouns(definition, pages)
    if detector == "duplicate_text":
        return _evaluate_duplicate_text(definition, pages)
    return _manual_review_check(
        definition,
        "当前规则层没有为这一项提供确定性判定，已保留到后续模型层或人工复核。",
    )


def build_visual_page_index(pages: list[ExtractedPage], pdf_path: Path | None = None) -> VisualPageIndex:
    caption_pages = sorted(
        {page.number for page in pages if not _is_likely_toc_page(page) and _page_has_figure_table_caption(page)}
    )
    reference_pages = sorted(
        {page.number for page in pages if not _is_likely_toc_page(page) and _page_has_figure_table_reference(page)}
    )

    candidate_pages: set[int] = set()
    max_page = max((page.number for page in pages), default=0)
    toc_page_set = {page.number for page in pages if _is_likely_toc_page(page)}
    for page_number in caption_pages:
        for neighbor in (page_number - 1, page_number, page_number + 1):
            if 1 <= neighbor <= max_page and neighbor not in toc_page_set:
                candidate_pages.add(neighbor)
    for page_number in reference_pages:
        for neighbor in (page_number, page_number + 1):
            if 1 <= neighbor <= max_page and neighbor not in toc_page_set:
                candidate_pages.add(neighbor)

    image_pages: list[int] = []
    if pdf_path is not None and pdf_path.exists():
        try:
            doc = fitz.open(str(pdf_path))
            for page in pages:
                if _is_likely_toc_page(page):
                    continue
                pdf_page = doc.load_page(page.number - 1)
                # Use raster images as a strong signal of figure/table pages.
                # Vector-only charts are rarer and harder to distinguish from text headers.
                if pdf_page.get_images(full=True):
                    image_pages.append(page.number)
            doc.close()
        except Exception:
            pass

    return VisualPageIndex(
        caption_pages=caption_pages,
        reference_pages=reference_pages,
        candidate_pages=sorted(candidate_pages),
        image_pages=sorted(image_pages),
    )


def _evaluate_blind_review_redaction(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    head_pages = pages[:8]
    matched_pages: list[int] = []
    matched_terms: list[str] = []
    for marker, patterns in SENSITIVE_PAGE_PATTERNS.items():
        if marker not in definition.requirement:
            continue
        for page in head_pages:
            for pattern in patterns:
                if pattern in page.text:
                    matched_pages.append(page.number)
                    matched_terms.append(pattern)
        break

    if matched_pages:
        terms = "、".join(sorted(set(matched_terms)))
        return _failed_check(
            definition,
            pages=matched_pages,
            rationale=f"前置页面检测到与盲审要求冲突的敏感词：{terms}。",
            suggestion="请检查封面、扉页或声明页，移除姓名、学号、导师或签名等身份信息。",
        )

    return _passed_check(
        definition,
        pages=[page.number for page in head_pages[:2]],
        rationale="前置页面未检测到这一项对应的明显敏感词。",
    )


def _evaluate_english_title_case(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    """Check English title case on the cover/abstract page title line.

    Strategy:
    1. Try to find a title line on the cover page: mostly ASCII, standalone,
       centered-ish (not a paragraph), and short.
    2. Fall back to the first page that has an ``Abstract`` heading and look for
       a standalone English line near that heading.
    3. Only if both fail, fall back to a heuristic over the first 3 pages.
    """
    stopwords = {"a", "an", "the", "and", "or", "of", "to", "for", "in", "on", "with"}

    def _looks_like_title_line(line: str, page_width: float | None = None) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        # Exclude obvious non-title lines.
        lower = stripped.lower()
        if lower.startswith(("abstract", "key words", "keywords", "key words:", "keywords:")):
            return False
        # A title line is mostly ASCII words, no sentence punctuation at the end,
        # and does not start with common sentence starters.
        sentence_starters = {
            "with",
            "this",
            "in",
            "the",
            "as",
            "it",
            "there",
            "these",
            "those",
            "however",
            "therefore",
            "furthermore",
            "moreover",
            "thus",
            "hence",
            "and",
            "are",
            "new",
        }
        ascii_words = re.findall(r"[A-Za-z][A-Za-z'-]*", stripped)
        ascii_text = " ".join(ascii_words)
        if len(ascii_words) < 4 or len(ascii_text) < 20 or len(ascii_text) > 120:
            return False
        if ascii_words[0].lower() in sentence_starters:
            return False
        if stripped[-1] in {".", ",", ";", "?", "!"}:
            return False
        # Substantial Chinese text makes it unlikely to be the English title.
        if len(re.findall(r"[一-鿿]", stripped)) > 2:
            return False
        # A title line should be a short, standalone line; long wrapped paragraphs are not titles.
        if len(stripped) > 80:
            return False
        # Require a high ratio of ASCII letters to total characters, i.e. little punctuation/numbers.
        if len(ascii_text) / len(stripped) < 0.75:
            return False
        return True

    def _is_centered(block_x0: float, block_x1: float, page_width: float) -> bool:
        if page_width <= 0:
            return False
        left_margin = block_x0
        right_margin = page_width - block_x1
        # Allow some tolerance; centered means left/right margins are roughly equal.
        return abs(left_margin - right_margin) / page_width < 0.25

    # Pass 1: cover page (first page). Use text blocks to locate standalone title lines.
    if pages:
        cover = pages[0]
        try:
            import fitz

            doc = fitz.open(str(cover.text))  # type: ignore[arg-type]
        except Exception:
            doc = None
        try:
            if doc is None:
                # Fallback: inspect text lines only.
                for line in cover.text.splitlines():
                    if _looks_like_title_line(line):
                        candidate_lines = [line.strip()]
                        break
                else:
                    candidate_lines = []
            else:
                # We cannot access the original PDF here; use heuristics on lines.
                candidate_lines = []
                for line in cover.text.splitlines():
                    if _looks_like_title_line(line):
                        candidate_lines.append(line.strip())
        finally:
            if doc is not None:
                doc.close()
        if candidate_lines:
            title_line = candidate_lines[0]
            words = re.findall(r"[A-Za-z][A-Za-z'-]*", title_line)
            invalid_words = [word for word in words if word.lower() not in stopwords and word[0].islower()]
            if invalid_words:
                return _failed_check(
                    definition,
                    pages=[1],
                    rationale=f"识别到英文题目行 `{title_line}`，其中存在未按标题式大写的实词：{', '.join(invalid_words[:4])}。",
                    suggestion="请检查英文题目，确保主要实词首字母大写。",
                )
            return _passed_check(
                definition,
                pages=[1],
                rationale=f"识别到英文题目行 `{title_line}`，未发现明显的实词首字母小写问题。",
            )

    # Pass 2: look for a standalone English title near the "Abstract" heading (pages 1-3).
    candidate_lines: list[str] = []
    for page in pages[:3]:
        lines = page.text.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.lower() == "abstract" or stripped == "英文摘要":
                # Look at the next few lines for a standalone English title.
                for candidate in lines[index + 1 : index + 6]:
                    if _looks_like_title_line(candidate):
                        candidate_lines.append(candidate.strip())
                        break
            if _looks_like_title_line(stripped):
                candidate_lines.append(stripped)
        if candidate_lines:
            break

    if not candidate_lines:
        return _manual_review_check(
            definition,
            "前 3 页中未可靠识别出独立的英文题目行，无法用规则判断大小写是否规范。",
        )

    title_line = candidate_lines[0]
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", title_line)
    invalid_words = [word for word in words if word.lower() not in stopwords and word[0].islower()]
    if invalid_words:
        return _failed_check(
            definition,
            pages=[1],
            rationale=f"识别到英文题目行 `{title_line}`，其中存在未按标题式大写的实词：{', '.join(invalid_words[:4])}。",
            suggestion="请检查英文题目，确保主要实词首字母大写。",
        )

    return _passed_check(
        definition,
        pages=[1],
        rationale=f"识别到英文题目行 `{title_line}`，未发现明显的实词首字母小写问题。",
    )


def _evaluate_page_count(
    definition: ChecklistDefinition, pages: list[ExtractedPage], total_pages: int
) -> AnalysisCheck:
    first_pages_text = "\n".join(page.text for page in pages[:8])
    degree = _infer_degree(first_pages_text)

    if "一般不少于50页" in definition.requirement or "一般不少于100页" in definition.requirement:
        if degree is None:
            return _manual_review_check(
                definition,
                f"当前总页数为 {total_pages} 页，但未识别出论文类型（硕士/博士），无法套用精确阈值。",
            )
        threshold = 100 if degree == "doctor" else 50
        if total_pages < threshold:
            return _failed_check(
                definition,
                pages=[1],
                rationale=f"识别为{_degree_label(degree)}论文，当前 PDF 总页数约为 {total_pages} 页，低于 {threshold} 页阈值。",
                suggestion="请确认正文篇幅是否满足学位论文要求，并核对上传版本是否完整。",
            )
        return _passed_check(
            definition,
            pages=[1],
            rationale=f"识别为{_degree_label(degree)}论文，当前 PDF 总页数约为 {total_pages} 页，满足最低篇幅要求。",
        )

    return _manual_review_check(
        definition,
        "当前规则层无法可靠识别绪论、背景介绍和相关工作的精确页段范围，建议结合目录和章节页码人工复核。",
    )


def _evaluate_reference_statistics(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    references = _extract_reference_entries(pages)
    if not references:
        return _failed_check(
            definition,
            pages=_find_pages(pages, ["参考文献"]),
            rationale="未识别到结构化参考文献条目。",
            suggestion="请确认论文包含规范的参考文献章节，并使用统一编号格式列出条目。",
        )

    degree = _infer_degree("\n".join(page.text for page in pages[:8]))
    minimum = 90 if degree == "doctor" else 40
    foreign_count = sum(_looks_like_foreign_entry(entry.text) for entry in references)
    recent_count = sum(_extract_year(entry.text) >= 2021 for entry in references if _extract_year(entry.text))
    website_count = sum("http" in entry.text.lower() or "www." in entry.text.lower() for entry in references)

    failures: list[str] = []
    if len(references) < minimum:
        failures.append(
            f"参考文献数量仅 {len(references)} 篇，低于 {_degree_label(degree or 'master')}论文建议下限 {minimum} 篇"
        )
    if foreign_count == 0:
        failures.append("未识别到明显的外文参考文献")
    if recent_count == 0:
        failures.append("未识别到近五年的参考文献")
    if website_count > max(3, len(references) // 5):
        failures.append("疑似网站类引用占比偏高")

    reference_pages = sorted({entry.number for entry in references})
    if failures:
        return _failed_check(
            definition,
            pages=reference_pages,
            rationale="；".join(failures) + "。",
            suggestion="请补充近五年和外文文献，控制网站引用占比，并确保参考文献总量达到论文要求。",
        )

    return _passed_check(
        definition,
        pages=reference_pages,
        rationale=(
            f"识别到 {len(references)} 篇参考文献，其中外文文献 {foreign_count} 篇，近五年文献 {recent_count} 篇，"
            f"网站类引用 {website_count} 条，未发现明显统计性风险。"
        ),
    )


def _evaluate_reference_citations(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    references = _extract_reference_entries(pages)
    citations = _extract_inline_citations(pages)
    if not references:
        return _failed_check(
            definition,
            pages=_find_pages(pages, ["参考文献"]),
            rationale="未识别到参考文献条目，因此无法建立正文引用与文献条目的对应关系。",
            suggestion="请为论文补充规范的参考文献列表。",
        )

    ref_numbers = {entry.index for entry in references}
    cited_numbers = [citation[0] for citation in citations]
    cited_set = set(cited_numbers)
    missing_in_body = sorted(ref_numbers - cited_set)
    out_of_range = sorted(number for number in cited_set if number not in ref_numbers)
    non_monotonic = _has_non_monotonic_citations(cited_numbers)
    citation_pages = sorted({page for _, page in citations})

    failures: list[str] = []
    if missing_in_body:
        failures.append(f"存在未在正文引用的文献编号，如 {missing_in_body[:5]}")
    if out_of_range:
        failures.append(f"正文中出现超出参考文献范围的编号，如 {out_of_range[:5]}")
    if non_monotonic:
        failures.append("正文引用编号顺序存在明显回跳")

    if failures:
        return _failed_check(
            definition,
            pages=citation_pages or _find_pages(pages, ["参考文献"]),
            rationale="；".join(failures) + "。",
            suggestion="请核对正文中的文献编号、引用顺序和文末参考文献列表，确保全部、按序、正确引用。",
        )

    return _passed_check(
        definition,
        pages=citation_pages or _find_pages(pages, ["参考文献"]),
        rationale=f"识别到 {len(citations)} 处正文引用，引用编号均落在文末参考文献范围内，且未发现明显顺序问题。",
    )


def _evaluate_figure_reference_placement(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    captions = _extract_figure_table_captions(pages)
    if not captions:
        return _manual_review_check(
            definition,
            "未在文本层识别到稳定的图表标题，当前无法仅凭规则判断引用位置是否合理。",
        )

    if "章节一开头" in definition.requirement:
        problematic_pages = [
            caption.page
            for caption in captions
            if _caption_near_heading(_page_text(pages, caption.page), caption.label)
        ]
        if problematic_pages:
            return _failed_check(
                definition,
                pages=problematic_pages,
                rationale="部分图表标题紧贴章节或小节标题出现，缺少引入性文字。",
                suggestion="请在章节标题后先补充介绍性文字，再放置对应图表。",
            )
        return _passed_check(
            definition,
            pages=sorted({caption.page for caption in captions}),
            rationale="未发现图表标题紧贴章节标题的明显情况。",
        )

    missing_reference_pages: list[int] = []
    for caption in captions:
        previous_text = _page_text(pages, caption.page - 1) + "\n" + _page_text(pages, caption.page)
        if caption.label not in previous_text.replace(" ", ""):
            continue
        ref_pattern = re.escape(caption.label)
        if not re.search(rf"(如图|见图|如表|见表).*{ref_pattern}|{ref_pattern}.*(所示|如下)", previous_text):
            missing_reference_pages.append(caption.page)

    if missing_reference_pages:
        return _failed_check(
            definition,
            pages=missing_reference_pages,
            rationale="部分图表标题所在页附近未识别到对应的正文引用。",
            suggestion="请在图表出现前后的正文中明确引用对应图表，例如“如图 3-2 所示”。",
        )

    return _passed_check(
        definition,
        pages=sorted({caption.page for caption in captions}),
        rationale="已识别到的图表标题附近均存在对应的正文引用或未发现明显违例。",
    )


def _evaluate_figure_table_numbering(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    captions = _extract_figure_table_captions(pages)
    if not captions:
        return _manual_review_check(
            definition,
            "文本层未稳定识别到图表标题，无法自动检查编号连续性。",
        )

    figures = [caption for caption in captions if caption.kind == "图"]
    tables = [caption for caption in captions if caption.kind == "表"]
    figure_issues = _find_numbering_issues(figures)
    table_issues = _find_numbering_issues(tables)
    issues = figure_issues + table_issues
    if issues:
        issue_pages = sorted({issue.page for issue in issues})
        issue_text = "；".join(issue.message for issue in issues[:4])
        return _failed_check(
            definition,
            pages=issue_pages,
            rationale=f"检测到图表编号异常：{issue_text}。",
            suggestion="请核对图、表编号是否连续、是否存在重复编号，以及正文引用的编号是否与标题一致。",
        )

    return _passed_check(
        definition,
        pages=sorted({caption.page for caption in captions}),
        rationale=f"共识别到 {len(figures)} 个图标题、{len(tables)} 个表标题，未发现明显的重复或倒序编号问题。",
    )


def _evaluate_first_person_pronouns(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    hit_pages = [page.number for page in pages if "我们" in page.text or "我们在本章" in page.text]
    if hit_pages:
        return _failed_check(
            definition,
            pages=hit_pages[:8],
            rationale="正文中出现了第一人称“我们”的表述。",
            suggestion="请将“我们”调整为“本文”“本研究”“论文”等更符合学位论文风格的表达。",
        )
    return _passed_check(
        definition,
        pages=[1],
        rationale="未检测到明显的第一人称“我们”表述。",
    )


def _evaluate_duplicate_text(definition: ChecklistDefinition, pages: list[ExtractedPage]) -> AnalysisCheck:
    paragraphs: list[tuple[int, str]] = []
    for page in pages:
        for paragraph in re.split(r"\n{2,}", page.text):
            normalized = _normalize_paragraph(paragraph)
            if len(normalized) >= 60:
                paragraphs.append((page.number, normalized))

    counter = Counter(text for _, text in paragraphs)
    duplicates = {text for text, count in counter.items() if count >= 2}
    if not duplicates:
        return _passed_check(
            definition,
            pages=[1],
            rationale="未识别到长度较长且重复出现的正文段落。",
        )

    duplicate_pages = sorted({page for page, text in paragraphs if text in duplicates})
    sample = next(iter(duplicates))
    preview = sample[:48] + ("..." if len(sample) > 48 else "")
    return _failed_check(
        definition,
        pages=duplicate_pages[:8],
        rationale=f"检测到重复段落，示例：`{preview}`。",
        suggestion="请检查摘要、绪论和各章节中是否存在整段复用或轻微改写的重复内容，并进行精简。",
    )


@dataclass(frozen=True)
class ReferenceEntry:
    index: int
    number: int
    text: str


@dataclass(frozen=True)
class CaptionEntry:
    kind: str
    label: str
    chapter: int
    sequence: int
    page: int


@dataclass(frozen=True)
class NumberingIssue:
    page: int
    message: str


def _find_reference_start_index(pages: list[ExtractedPage]) -> int | None:
    """Locate the real reference section, not the table-of-contents entry.

    Strategy: use the last page that contains the heading "参考文献", and
    verify that at least one numbered reference entry appears soon after.
    If the last occurrence yields no entries, fall back to earlier occurrences.
    """
    candidate_indices = [index for index, page in enumerate(pages) if "参考文献" in page.text]
    if not candidate_indices:
        return None

    entry_pattern = re.compile(r"^\s*[\[\(]?\d{1,3}[\]\)\.、]\s*\S")
    # Try candidates from the end (most likely the real section).
    for start_index in reversed(candidate_indices):
        found_entries = 0
        for page in pages[start_index : start_index + 3]:
            for line in page.text.splitlines():
                if entry_pattern.search(_normalize_reference_numbering_text(line)):
                    found_entries += 1
                    if found_entries >= 2:
                        return start_index
        # Even a single entry is a strong signal compared with a bare TOC line.
        if found_entries >= 1:
            return start_index
    return candidate_indices[-1]


def _extract_reference_entries(pages: list[ExtractedPage]) -> list[ReferenceEntry]:
    start_index = _find_reference_start_index(pages)
    if start_index is None:
        return []

    entries: list[ReferenceEntry] = []
    current_index: int | None = None
    current_lines: list[str] = []
    current_page = pages[start_index].number
    for page in pages[start_index:]:
        for line in page.text.splitlines():
            line = _normalize_reference_numbering_text(line).strip()
            if not line:
                continue
            match = re.match(r"^\s*[\[\(]?(\d{1,3})[\]\)\.、]\s*(.*)$", line)
            if match:
                if current_index is not None:
                    entries.append(
                        ReferenceEntry(
                            index=current_index,
                            number=current_page,
                            text=" ".join(current_lines).strip(),
                        )
                    )
                current_index = int(match.group(1))
                current_page = page.number
                current_lines = [match.group(2).strip()]
            elif current_index is not None:
                current_lines.append(line)

    if current_index is not None:
        entries.append(
            ReferenceEntry(
                index=current_index,
                number=current_page,
                text=" ".join(current_lines).strip(),
            )
        )
    return entries


def _extract_inline_citations(pages: list[ExtractedPage]) -> list[tuple[int, int]]:
    """Extract in-text citations such as [1] or full-width ［1］ before the reference section."""
    citations: list[tuple[int, int]] = []
    pattern = re.compile(r"\[(\d{1,3})\]")
    ref_start = _find_reference_start_index(pages)
    for page in pages[:ref_start]:
        normalized_text = _normalize_reference_numbering_text(page.text)
        for match in pattern.finditer(normalized_text):
            citations.append((int(match.group(1)), page.number))
    return citations


def _normalize_reference_numbering_text(text: str) -> str:
    return text.translate(
        str.maketrans(
            {
                "［": "[",
                "］": "]",
                "（": "(",
                "）": ")",
                "．": ".",
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
            }
        )
    )


def _page_has_figure_table_caption(page: ExtractedPage) -> bool:
    if any(pattern in page.text for pattern in FIGURE_TABLE_DIRECTORY_PATTERNS):
        return False
    for line in page.text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(pattern.search(stripped) for pattern in FIGURE_TABLE_CAPTION_PATTERNS):
            return True
    return False


def _page_has_figure_table_reference(page: ExtractedPage) -> bool:
    if any(pattern in page.text for pattern in FIGURE_TABLE_DIRECTORY_PATTERNS):
        return False
    normalized = page.text.replace("　", " ")
    return any(pattern.search(normalized) for pattern in FIGURE_TABLE_REFERENCE_PATTERNS)


def _extract_figure_table_captions(pages: list[ExtractedPage]) -> list[CaptionEntry]:
    captions: list[CaptionEntry] = []
    pattern = re.compile(r"(图|表)\s*([0-9]{1,2})[-.．]([0-9]{1,3})")
    dot_leader_pattern = re.compile(r"\.{4,}")
    seen_lines: set[tuple[str, int, str]] = set()
    for page in pages:
        if _is_likely_toc_page(page):
            continue
        for line in page.text.splitlines():
            stripped_line = line.strip()
            if dot_leader_pattern.search(line):
                # Skip table-of-contents lines that repeat captions with trailing page numbers.
                continue
            for match in pattern.finditer(line):
                if not _looks_like_caption_line(stripped_line, match):
                    continue
                kind = match.group(1)
                chapter = int(match.group(2))
                sequence = int(match.group(3))
                label = f"{kind}{chapter}-{sequence}"
                key = (label, page.number, stripped_line)
                if key in seen_lines:
                    continue
                seen_lines.add(key)
                captions.append(
                    CaptionEntry(
                        kind=kind,
                        label=label,
                        chapter=chapter,
                        sequence=sequence,
                        page=page.number,
                    )
                )
    return captions


def _looks_like_caption_line(stripped_line: str, match: re.Match[str]) -> bool:
    if not stripped_line:
        return False
    # Captions should begin with the figure/table number. In-text references
    # such as "由表4.1及图4.1可以看出" must not be treated as new captions.
    if match.start() != 0:
        return False
    if not re.match(r"^(图|表)\s*\d{1,2}[-.．]\d{1,3}(?:\s+|[:：])\S+", stripped_line):
        return False
    # Very long lines are usually prose that begins with a reference rather than
    # a concise title.
    return len(stripped_line) <= 100


def _find_numbering_issues(captions: list[CaptionEntry]) -> list[NumberingIssue]:
    issues: list[NumberingIssue] = []
    grouped: dict[int, list[CaptionEntry]] = defaultdict(list)
    for caption in captions:
        grouped[caption.chapter].append(caption)

    for chapter, items in grouped.items():
        seen: set[int] = set()
        last_sequence = 0
        for item in sorted(items, key=lambda value: (value.sequence, value.page)):
            if item.sequence in seen:
                issues.append(NumberingIssue(page=item.page, message=f"{item.label} 重复"))
                continue
            if item.sequence < last_sequence:
                issues.append(NumberingIssue(page=item.page, message=f"{item.label} 编号倒序"))
            if last_sequence and item.sequence > last_sequence + 1:
                issues.append(NumberingIssue(page=item.page, message=f"第 {chapter} 章存在图表编号跳号"))
            seen.add(item.sequence)
            last_sequence = item.sequence
    return issues


def _has_non_monotonic_citations(numbers: list[int]) -> bool:
    last = 0
    regressions = 0
    for number in numbers:
        if number < last:
            regressions += 1
        last = max(last, number)
    return regressions >= 3


def _looks_like_foreign_entry(text: str) -> bool:
    # Count Latin/Cyrillic/Greek letters as likely foreign-language content.
    non_cjk_letters = len(re.findall(r"[A-Za-z]", text))
    cjk_letters = len(re.findall("[\u4e00-\u9fff]", text))
    return non_cjk_letters > cjk_letters


def _extract_year(text: str) -> int | None:
    years = [int(year) for year in re.findall(r"\b(19\d{2}|20\d{2})\b", text)]
    if not years:
        return None
    return max(years)


def _infer_degree(text: str) -> str | None:
    if "博士" in text:
        return "doctor"
    if "硕士" in text:
        return "master"
    return None


def _degree_label(degree: str) -> str:
    return "博士" if degree == "doctor" else "硕士"


def _find_pages(pages: Iterable[ExtractedPage], keywords: list[str], limit: int = 5) -> list[int]:
    matched: list[int] = []
    for page in pages:
        if any(keyword in page.text for keyword in keywords):
            matched.append(page.number)
        if len(matched) >= limit:
            break
    return matched


def _normalize_paragraph(paragraph: str) -> str:
    paragraph = re.sub(r"\s+", "", paragraph)
    return paragraph.strip("，。；：,. ")


def _page_text(pages: list[ExtractedPage], page_number: int) -> str:
    for page in pages:
        if page.number == page_number:
            return page.text
    return ""


def _caption_near_heading(page_text: str, label: str) -> bool:
    normalized_lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    label_line_index = next((i for i, line in enumerate(normalized_lines) if label in line.replace(" ", "")), None)
    if label_line_index is None:
        return False
    for line in normalized_lines[: max(0, label_line_index)]:
        if re.match(r"^(第[一二三四五六七八九十]+章|\d+(\.\d+)+)", line):
            return label_line_index <= 2
    return False


def _passed_check(definition: ChecklistDefinition, pages: list[int], rationale: str) -> AnalysisCheck:
    return AnalysisCheck(
        check_id=definition.check_id,
        title=definition.title,
        source_section=definition.source_section,
        requirement=definition.requirement,
        layer=definition.layer,
        severity=definition.severity,
        status="passed",
        rationale=rationale,
        suggestion="当前检查项通过，无需针对这一项额外修改。",
        pages=sorted(set(pages)),
    )


def _failed_check(
    definition: ChecklistDefinition,
    pages: list[int],
    rationale: str,
    suggestion: str,
) -> AnalysisCheck:
    return AnalysisCheck(
        check_id=definition.check_id,
        title=definition.title,
        source_section=definition.source_section,
        requirement=definition.requirement,
        layer=definition.layer,
        severity=definition.severity,
        status="failed",
        rationale=rationale,
        suggestion=suggestion,
        pages=sorted(set(page for page in pages if page >= 1)),
    )


def _manual_review_check(definition: ChecklistDefinition, rationale: str) -> AnalysisCheck:
    pages = []
    query_terms = extract_query_terms(f"{definition.source_section} {definition.requirement}")
    if query_terms:
        pages = []
    return AnalysisCheck(
        check_id=definition.check_id,
        title=definition.title,
        source_section=definition.source_section,
        requirement=definition.requirement,
        layer=definition.layer,
        severity=definition.severity,
        status="needs_manual_review",
        rationale=rationale,
        suggestion="请结合原文与版式人工复核这一项，必要时再启用对应层的模型检查。",
        pages=pages,
    )
