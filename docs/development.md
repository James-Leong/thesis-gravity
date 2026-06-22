# 开发说明

## 适用范围

本文件用于记录开发环境准备、启动方式、脚本入口和开发期约定。

## 环境准备

要求：

- Python 3.12+
- Node.js 18+
- `uv`

安装后端依赖：

```bash
uv sync --all-groups
```

安装前端依赖：

```bash
cd frontend
npm install
```

## 环境变量

复制模板：

```bash
cp .env.example .env
```

至少确认以下配置：

- `JWT_SECRET_KEY`
- `LLM_PROVIDER`
- `LLM_MODEL_ID`
- `LLM_API_KEY`
- `LLM_BASE_URL`
- `VISION_LLM_MODEL_ID`（如需启用图表视觉检查）
- `VISION_LLM_API_KEY`
- `VISION_LLM_BASE_URL`
- `LOCAL_REVIEW_PAGE_BATCH_SIZE`
- `MAX_CHECK_ITEMS_PER_BATCH`
- `MAX_VISUAL_IMAGES_PER_BATCH`
- `LOG_LEVEL`
- `REFERENCE_DOC_PATH`

## 启动方式

### 开发模式

```bash
./start.sh
```

行为：

- 同时启动 FastAPI 后端和 Vite 前端
- 默认后端地址：`http://127.0.0.1:8000`
- 默认前端地址：`http://127.0.0.1:5173`
- 前端日志会写到临时文件；如果 Vite 启动失败，脚本会直接输出日志并退出

### 生产模式

```bash
./start.sh prod
```

行为：

- 先构建前端
- 再由 FastAPI 提供静态资源和 API

## 启动脚本约定

- `start.sh` 只做启动和依赖检查，不自动安装依赖。
- 缺少后端依赖时，手动执行 `uv sync --all-groups`。
- 缺少前端依赖时，手动执行 `cd frontend && npm install`。
- 如果 `frontend/node_modules` 缺失，`start.sh` 应直接失败，不要在脚本里隐式补装。
- `./start.sh` 会在打印地址前检查前端是否成功启动，避免输出误导性的访问地址。

## 开发脚本

代码检查与格式化：

```bash
./scripts/lint.sh --all
```

或分别执行：

```bash
uv run ruff check .
uv run ruff format .
```

清理本地运行数据前先查看帮助：

```bash
./scripts/clean_local_data.sh
```

抽取论文 PDF 中的图、表截图到临时目录，便于调试图表视觉检查：

```bash
PYTHONPATH=. uv run python scripts/extract_figure_table_assets.py source/M公司盈利能力分析及提升策略研究_廖雨璐.pdf /tmp/thesis-gravity-figure-assets
```

该脚本会生成 `index.json`、`figures/` 和 `tables/`。截图来自自动裁剪，可能包含相邻正文、公式或页码，调试多模态判断时应以图表标题和主体为准。

## 运行数据

- SQLite 数据库默认位于 `data/app.db`
- **测试数据库**：`tests/conftest.py` 已设置 `DATABASE_URL` 指向 `data/test.db`，所有自动化测试自动使用独立测试库，不会触碰 `data/app.db`
- 论文上传目录默认位于 `data/theses/{student_id}/`
- 本地运行数据统一放在 `data/` 下
- **严禁对 `data/app.db` 执行破坏性操作**（DELETE、DROP、TRUNCATE 等），详见 `AGENTS.md` Database Safety Rules
- 上传的 PDF 会先做内容校验；无法解析、空白或纯图片扫描件会被拒绝，且不会保留无效文件
- 论文分析会按 `source/common-problems-for-students.md` 自动拆分为规则层、文本模型层和图表视觉层，并返回逐项校验结果
- 文本模型层不会再按零散小条目任意切批，而是优先按大的检查方向聚合请求，再在同一次模型返回中展开各个细分检查点，以减少模型调用次数
- 文本模型与视觉模型请求会把论文片段放在用户输入最前面，并把变化更大的检查要求放在后部，以提高 provider prompt cache 命中率
- 图表类视觉检查会优先抽取全量图、表截图，按 `MAX_VISUAL_IMAGES_PER_BATCH` 分批送入视觉模型，并附带截图顺序说明；未抽取到图表资产时回退到整页截图，回退时同样按该配置限制单次视觉模型可见图片数
- 长论文会先按局部页批次做文本段落审阅，再基于全文梗概做一次整体逻辑复核，避免再次退化成单次超长上下文审阅
- 如果 PDF 总页数超过 `MAX_PAGES`，分析任务会直接失败，并返回超页数错误，而不是只读取前若干页
- 分析时会先建立“PDF 物理页 -> 论文印刷页码”的映射；返回结果优先展示论文页码，同时保留 PDF 页码用于定位原文件
- 未配置 `VISION_LLM_MODEL_ID` 时，图表清晰度、坐标轴、排版等图表视觉类条目会标记为“待人工复核”
- 每次分析任务会额外记录 LLM 调用摘要到 `analysis_tasks.llm_usage_summary_json`，并把每次模型调用的详细输入输出/耗时/token/cache 指标记录到 `analysis_llm_call_logs`，便于后续计费与调用分析
- 学生可通过 `GET /theses/usage-stats` 查看个人 AI 用量汇总；当前口径只做调用统计，不做费用换算
- 学生工作台现在按“论文任务”组织：`POST /theses/drafts` 首次提交会创建新论文任务；后续提交同一篇论文时携带 `thesis_id`，会在原论文下新增版本，而不是新建一条独立任务
- 论文状态建议按 `analysis_pending`（AI 处理中）→ `analysis_done`（待提交导师）→ `mentor_review`（导师审核中）→ `approved`（已完成）流转；若导师退回，则切到 `changes_requested`（待修改），学生上传新版本后重新回到 `analysis_pending`
- 学生处理完分析问题后可通过 `/tasks/{task_id}/submit-for-mentor` 将当前最新版本提交导师评审；论文进入 `mentor_review` 后，学生不能再次提交新版本，必须等待导师给出通过或退回结果
- 导师通过 `/mentor/pending-reviews` 查看待评审的“当前最新版本”，通过 `/mentor/reviews` 提交 `approved` 或 `changes_requested` 决定；评审结果会以站内通知形式告知学生，同时更新论文状态与版本 stage
- 导师可通过 `/mentor/theses` 查看已绑定学生的论文最新进度；待评审完成后，论文会从“待评审列表”移出，但仍可在该进度列表中继续搜索和展开查看
- 导师或学生可通过 `/theses/versions/{version_id}/file` 受控预览对应版本的 PDF 原文件

## 认证约定

- 前端不保存 Bearer token
- 登录态通过 `HttpOnly` Cookie 维持
