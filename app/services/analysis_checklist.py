from __future__ import annotations

import re
from dataclasses import dataclass, field
from hashlib import sha1
from typing import Literal


# Keywords that trigger rule-layer detectors.
RULE_KEYWORDS = (
    "盲审",
    "英文题目",
    "页数要求",
    "参考文献数量",
    "参考文献及引用",
    "文献未在正文中全部、按序、正确引用",
    "图表应一般应放在引用该图表段落之后",
    "图表不要放在章节一开头",
    "图表要分别统一、规范编号",
    "文中大量用了“我们”",
    "相似度检测",
)

# Keywords that identify figure/table visual checks.
FIGURE_TABLE_VISION_KEYWORDS = (
    "坐标",
    "单位",
    "清晰度",
    "模糊",
    "截图",
    "标题放在图的下方",
    "标题放在表的上方",
    "不要跨页",
    "页面宽度",
    "布局",
    "字体",
    "对齐",
    "图中文字",
    "泳道图",
    "时序图",
    "顺序图",
    "框架图",
    "流程图",
)

FIGURE_TABLE_CONTEXT_KEYWORDS = (
    "图表",
    "图的",
    "如图",
    "Figure",
    "Fig ",
    "表格",
    "如表",
    "Table",
)

HIGH_SEVERITY_KEYWORDS = (
    "盲审",
    "学术不端",
    "抄袭",
    "剽窃",
    "伪造",
    "篡改",
    "买卖论文",
    "代写",
    "相似度检测",
)


@dataclass(frozen=True)
class ChecklistDefinition:
    check_id: str
    title: str
    source_section: str
    requirement: str
    layer: Literal["rule", "text_model", "vision_model"]
    detector: str
    severity: Literal["low", "medium", "high"]
    examples: tuple[str, ...] = field(default_factory=tuple)

    def with_example(self, example: str) -> "ChecklistDefinition":
        return ChecklistDefinition(
            check_id=self.check_id,
            title=self.title,
            source_section=self.source_section,
            requirement=self.requirement,
            layer=self.layer,
            detector=self.detector,
            severity=self.severity,
            examples=self.examples + (example,),
        )


@dataclass(frozen=True)
class ParsedReference:
    checklist: list[ChecklistDefinition]
    raw_text: str


def parse_reference_checklist(reference_text: str) -> ParsedReference:
    """Parse the reference Markdown into check definitions.

    Headings form the section path. Bullet items under normal headings become
    check definitions. Bullet items under a heading whose title contains
    "专家评语再现" are treated as expert comment examples and attached to the
    most recent normal check definition in the same section path.
    """
    headings: list[tuple[int, str]] = []
    checklist: list[ChecklistDefinition] = []
    heading_example_definitions: dict[str, ChecklistDefinition] = {}
    plain_expert_section = False

    for line_number, raw_line in enumerate(reference_text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        heading_match = re.match(r"^(#{2,5})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            headings = [item for item in headings if item[0] < level]
            headings.append((level, title))
            plain_expert_section = False
            continue

        if "专家评语" in line and not line.startswith("- "):
            plain_expert_section = True
            continue

        if not line.startswith("- "):
            plain_expert_section = False
            continue

        requirement = line[2:].strip("；; ")
        if not requirement:
            continue

        source_section = _build_section_path(headings)
        if _is_expert_comment_section(headings) or plain_expert_section or _looks_like_expert_example(requirement):
            _attach_or_create_heading_example(
                checklist,
                heading_example_definitions,
                source_section,
                requirement,
                line_number,
            )
            continue

        title = _derive_title(source_section, requirement)
        layer, detector = _classify_requirement(source_section, requirement)
        severity = _classify_severity(source_section, requirement)
        digest = sha1(f"{source_section}|{requirement}|{line_number}".encode("utf-8")).hexdigest()[:12]
        definition = ChecklistDefinition(
            check_id=f"chk_{digest}",
            title=title,
            source_section=source_section,
            requirement=requirement,
            layer=layer,
            detector=detector,
            severity=severity,
        )
        checklist.append(definition)
        plain_expert_section = False

    return ParsedReference(checklist=checklist, raw_text=reference_text)


def _is_expert_comment_section(headings: list[tuple[int, str]]) -> bool:
    return any("专家评语" in title for _, title in headings)


def _attach_example_to_section_definitions(
    checklist: list[ChecklistDefinition], source_section: str, example: str
) -> bool:
    updated_any = False
    for index, definition in enumerate(checklist):
        if definition.source_section != source_section:
            continue
        checklist[index] = definition.with_example(example)
        updated_any = True
    return updated_any


def _attach_or_create_heading_example(
    checklist: list[ChecklistDefinition],
    heading_example_definitions: dict[str, ChecklistDefinition],
    source_section: str,
    example: str,
    line_number: int,
) -> None:
    updated_any = _attach_example_to_section_definitions(checklist, source_section, example)
    if updated_any:
        return

    definition = heading_example_definitions.get(source_section)
    if definition is None:
        definition = _build_heading_example_definition(source_section, line_number)
        checklist.append(definition)
    updated = definition.with_example(example)
    checklist[checklist.index(definition)] = updated
    heading_example_definitions[source_section] = updated


def _looks_like_expert_example(requirement: str) -> bool:
    stripped = requirement.strip()
    if stripped.startswith(("“", '"', "‘", "'")):
        return True
    if re.match(r"^P\d+\s*页", stripped, flags=re.IGNORECASE):
        return True
    if stripped.startswith(("例如", "比如", "如：", "如:", "评语")):
        return True
    if "评语" in stripped[:16]:
        return True
    return False


def _build_heading_example_definition(source_section: str, line_number: int) -> ChecklistDefinition:
    requirement = source_section.split(" / ")[-1]
    layer, detector = _classify_requirement(source_section, requirement)
    if layer == "rule":
        layer = "text_model"
        detector = "text_review"
    severity = _classify_severity(source_section, requirement)
    digest = sha1(f"{source_section}|{requirement}|heading_examples|{line_number}".encode("utf-8")).hexdigest()[:12]
    return ChecklistDefinition(
        check_id=f"chk_{digest}",
        title=_derive_title(source_section, requirement),
        source_section=source_section,
        requirement=requirement,
        layer=layer,
        detector=detector,
        severity=severity,
    )


def extract_query_terms(text: str) -> list[str]:
    normalized = text.replace("（", "(").replace("）", ")")
    ascii_terms = re.findall(r"[A-Za-z][A-Za-z0-9_\-+.]{1,}", normalized)
    cjk_terms = [
        chunk
        for chunk in re.findall(r"[一-鿿]{2,}", normalized)
        if chunk not in {"专家评语再现", "论文", "本文", "作者", "建议", "一般", "部分", "内容", "要求"}
    ]
    tokens = ascii_terms + cjk_terms
    # Prefer longer CJK phrases to reduce noisy matches.
    tokens.sort(key=len, reverse=True)
    deduped: list[str] = []
    for token in tokens:
        if token not in deduped:
            deduped.append(token)
    return deduped[:12]


def _build_section_path(headings: list[tuple[int, str]]) -> str:
    if not headings:
        return "未分类"

    titles = [title for _, title in headings]
    # Strip the "专家评语再现" marker from the displayed path so definitions
    # group naturally under their parent section.
    if titles and "专家评语" in titles[-1] and len(titles) >= 2:
        titles = titles[:-1]
    return " / ".join(titles)


def _derive_title(source_section: str, requirement: str) -> str:
    section_title = source_section.split(" / ")[-1]
    compact_requirement = re.sub(r"\s+", " ", requirement)
    if len(compact_requirement) <= 24:
        return compact_requirement
    return f"{section_title}检查"


def _classify_requirement(
    source_section: str, requirement: str
) -> tuple[Literal["rule", "text_model", "vision_model"], str]:
    combined = f"{source_section} {requirement}"

    if "论文符合盲审要求" in source_section:
        lowered = requirement
        if any(keyword in lowered for keyword in ("封面", "扉页", "致谢", "独创性声明", "论文使用授权声明")):
            return "rule", "blind_review_redaction"

    if "英文题目实词首字母大写" in combined:
        return "rule", "english_title_case"
    if "字数与页数要求" in source_section:
        return "rule", "page_count"
    if "参考文献数量要够" in requirement:
        return "rule", "reference_statistics"
    if "参考文献及引用要规范统一" in requirement or "文献未在正文中全部、按序、正确引用" in requirement:
        return "rule", "reference_citations"
    if "图表应一般应放在引用该图表段落之后" in requirement or "图表不要放在章节一开头" in requirement:
        return "rule", "figure_reference_placement"
    if "图表要分别统一、规范编号" in requirement:
        return "rule", "figure_table_numbering"
    if "文中大量用了“我们”" in requirement:
        return "rule", "first_person_pronouns"
    if "相似度检测" in source_section:
        return "rule", "duplicate_text"

    if _has_figure_table_context(combined) and any(keyword in combined for keyword in FIGURE_TABLE_VISION_KEYWORDS):
        return "vision_model", "vision_review"
    if any(keyword in combined for keyword in RULE_KEYWORDS):
        return "rule", "generic_rule_review"
    return "text_model", "text_review"


def _has_figure_table_context(combined: str) -> bool:
    if any(keyword in combined for keyword in FIGURE_TABLE_CONTEXT_KEYWORDS):
        return True
    if re.search(r"图\d", combined):
        return True
    return False


def _classify_severity(source_section: str, requirement: str) -> Literal["low", "medium", "high"]:
    combined = f"{source_section} {requirement}"
    if any(keyword in combined for keyword in HIGH_SEVERITY_KEYWORDS):
        return "high"
    if any(keyword in combined for keyword in ("图表", "参考文献", "摘要", "创新性", "工作量", "技术深度")):
        return "medium"
    return "low"
