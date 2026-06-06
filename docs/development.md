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

## 运行数据

- SQLite 数据库默认位于 `data/app.db`
- 论文上传目录默认位于 `data/theses/{student_id}/`
- 本地运行数据统一放在 `data/` 下
- 上传的 PDF 会先做内容校验；无法解析、空白或纯图片扫描件会被拒绝，且不会保留无效文件
- 论文分析会按 `source/common-problems-for-students.md` 自动拆分为规则层、文本模型层和图表视觉层，并返回逐项校验结果
- 文本模型层不会再按零散小条目任意切批，而是优先按大的检查方向聚合请求，再在同一次模型返回中展开各个细分检查点，以减少模型调用次数
- 文本模型与视觉模型请求会把论文片段放在用户输入最前面，并把变化更大的检查要求放在后部，以提高 provider prompt cache 命中率
- 长论文会先按局部页批次做文本段落审阅，再基于全文梗概做一次整体逻辑复核，避免再次退化成单次超长上下文审阅
- 如果 PDF 总页数超过 `MAX_PAGES`，分析任务会直接失败，并返回超页数错误，而不是只读取前若干页
- 分析时会先建立“PDF 物理页 -> 论文印刷页码”的映射；返回结果优先展示论文页码，同时保留 PDF 页码用于定位原文件
- 未配置 `VISION_LLM_MODEL_ID` 时，图表清晰度、坐标轴、排版等图表视觉类条目会标记为“待人工复核”
- 每次分析任务会额外记录 LLM 调用摘要到 `analysis_tasks.llm_usage_summary_json`，并把每次模型调用的详细输入输出/耗时/token/cache 指标记录到 `analysis_llm_call_logs`，便于后续计费与调用分析

## 认证约定

- 前端不保存 Bearer token
- 登录态通过 `HttpOnly` Cookie 维持
