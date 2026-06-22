from app.services.analysis_checklist import parse_reference_checklist


def test_parse_reference_checklist_extracts_items_and_layers() -> None:
    reference_text = """
## 论文的格式、结构和文字表达

### 论文符合盲审要求
- 封面（去掉封面中的学号、姓名和导师信息）；

### 论文图表要求
- 图表应一般应放在引用该图表段落之后；

### 论文说法需严谨，语句需通顺、写法要规范
- 文中大量用了“我们”甚至“我们在本章中提出....”与论文是作者一人独立完成的规则相冲突。

#### 专家评语再现：
- “重复的文字太多，论文写作过于敷衍。”
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 3
    assert parsed.checklist[0].layer == "rule"
    assert parsed.checklist[1].detector == "figure_reference_placement"
    assert parsed.checklist[2].detector == "first_person_pronouns"
    # The generic "我们" expert comment is itself a check item; the example under it is attached.
    pronoun_definition = parsed.checklist[2]
    assert len(pronoun_definition.examples) == 1
    assert "重复的文字太多" in pronoun_definition.examples[0]


def test_expert_comments_become_examples_not_check_items() -> None:
    reference_text = """
## 论文的写法与内容

### 论文工作要与现有工作/前人工作进行比较
#### 2）注意所引用的相关工作的最新研究成果
- 论文应讨论所引用方法的年代与局限性。

##### 专家评语再现
- “另外，建议在谈论某种方法时，增加年代信息，比如YOLO框架在完成论文时，其版本已经更新了版本，已克服了论文所述的YOLO框架的不足”
""".strip()

    parsed = parse_reference_checklist(reference_text)

    # The YOLO expert comment should be an example on the parent check item, not a standalone check item.
    assert len(parsed.checklist) == 1
    yolo_definition = parsed.checklist[0]
    assert len(yolo_definition.examples) == 1
    assert "YOLO" in yolo_definition.examples[0]


def test_heading_only_expert_comments_create_text_check_with_examples() -> None:
    reference_text = """
## 论文的格式、结构和文字表达

### 论文说法需严谨，语句需通顺、写法要规范

#### 专家评语再现：
- “文中大量用了“我们”甚至“我们在本章中提出....”与论文是作者一人独立完成的规则相冲突。”
- “大部分情感识别模型存在笨重的问题”，“笨重”用词不当。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 1
    definition = parsed.checklist[0]
    assert definition.layer == "text_model"
    assert definition.detector == "text_review"
    assert definition.requirement == "论文说法需严谨，语句需通顺、写法要规范"
    assert len(definition.examples) == 2
    assert "我们" in definition.examples[0]


def test_quoted_example_bullets_do_not_become_independent_checks() -> None:
    reference_text = """
## 论文的写法与内容

### 论文工作要与现有工作/前人工作进行比较
#### 2）注意所引用的相关工作的最新研究成果
- “另外，建议在谈论某种方法时，增加年代信息，比如YOLO框架在完成论文时，其版本已经更新了版本。”
- 例如DC违反检测对比的工作有Hydra(2017)、VioFinder(2020)批量检测。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 1
    definition = parsed.checklist[0]
    assert definition.requirement == "2）注意所引用的相关工作的最新研究成果"
    assert len(definition.examples) == 2


def test_section_expert_examples_attach_to_all_checks_in_section() -> None:
    reference_text = """
## 论文的格式、结构和文字表达

### 参考文献要求
- 参考文献数量要够，一般硕士应在40篇以上；
- 参考文献及引用要规范统一。

#### 专家评语再现
- 文献综述中近5年的相关文献占比太低。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 2
    assert all(item.examples == ("文献综述中近5年的相关文献占比太低。",) for item in parsed.checklist)


def test_expert_comment_example_heading_is_stripped_from_section_path() -> None:
    reference_text = """
## 论文的格式、结构和文字表达

### 论文题目要求
- 题目应准确概括论文核心对象、方法和贡献。

#### 专家评语示例
- 论文题目与正文内容不太吻合。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 1
    assert parsed.checklist[0].source_section == "论文的格式、结构和文字表达 / 论文题目要求"
    assert parsed.checklist[0].examples == ("论文题目与正文内容不太吻合。",)


def test_page_header_requirement_stays_in_text_flow() -> None:
    reference_text = """
## 页眉页脚（章节编号与页码）要求：
- 页眉的章节标题要与正文相对应。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    assert len(parsed.checklist) == 1
    assert parsed.checklist[0].layer == "text_model"
    assert parsed.checklist[0].examples == ()


def test_code_algorithm_requirements_are_scoped_to_computing_theses() -> None:
    reference_text = """
### 论文代码与算法描述要求
- 本组要求仅适用于计算机、软件工程、信息系统、人工智能、算法模型、数据处理平台，或论文正文包含程序实现、代码、伪代码、算法流程、模型训练和系统开发等内容的论文。
- 对财务分析、管理案例、教育研究、文献综述等不涉及计算机实现或算法模型的论文，不应仅因未出现代码、伪代码、系统架构、算法复杂度或实现细节而判定不合格。
- 在适用论文中，算法、模型或关键技术应说明输入、输出、步骤、参数选择、复杂度或适用条件。
""".strip()

    parsed = parse_reference_checklist(reference_text)

    requirements = [item.requirement for item in parsed.checklist]
    assert any("仅适用于计算机" in requirement for requirement in requirements)
    assert any("不应仅因未出现代码" in requirement for requirement in requirements)
