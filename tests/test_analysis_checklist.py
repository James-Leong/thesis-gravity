from app.services.analysis_checklist import parse_reference_checklist


def test_parse_reference_checklist_extracts_items_and_layers() -> None:
    reference_text = """
## 论文的格式、结构和文字表达

### 论文符合盲审要求
- 封面（去掉封面中的学号、姓名和导师信息）；

### 论文图表要求
- 图表应一般应放在引用该图表段落之后；

### 论文说法需严谨，语句需通顺、写法要规范
#### 专家评语再现：
- “文中大量用了“我们”甚至“我们在本章中提出....”与论文是作者一人独立完成的规则相冲突。”

### 论文图表要求（续）
#### 专家评语再现
- 部分图（特别是框架图/流程图）比较模糊
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 4
    assert parsed.checklist[0].layer == "rule"
    assert parsed.checklist[1].detector == "figure_reference_placement"
    assert parsed.checklist[2].detector == "first_person_pronouns"
    assert parsed.checklist[3].layer == "vision_model"


def test_page_header_requirement_stays_in_text_flow() -> None:
    reference_text = """
## 页眉页脚（章节编号与页码）要求：
- 页眉的章节标题要与正文相对应。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 1
    assert parsed.checklist[0].layer == "text_model"
