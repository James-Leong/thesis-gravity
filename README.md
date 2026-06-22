# Thesis Gravity

学位论文辅导系统，面向学生、导师、教务和管理员，提供论文草稿提交、自动分析、导师评审与通知闭环。

## 项目目标

- 为学生提供从草稿提交到结构化反馈的完整链路。
- 为导师提供基于版本的评审入口与状态流转能力。
- 为后续前端联调和智能体能力扩展提供稳定后端基线。

## 当前实现状态

### 已有能力

- FastAPI 后端服务与 `/health` 健康检查。
- 基于 `HttpOnly` 会话 Cookie 的注册/登录接口。
- 基于角色的基础访问控制。
- PDF 草稿上传与本地存储。
- 以“论文任务 -> 多个提交版本”组织学生工作流，而不是把每次上传视为独立任务。
- 分析任务创建、后台执行、状态查询。
- 学生工作台展示单次分析任务、本月累计、总累计 AI 调用消耗统计。
- 基于 Agno 的论文草稿分析代理。
- 基于 `source/common-problems-for-students.md` 的分层逐项校验：规则层优先、文本模型补充、图表视觉模型可选。
- 长论文文本分析采用“局部页批次审阅 + 全文梗概复核”，兼顾上下文完整性与 token 控制。
- 分析结果优先展示论文印刷页码，并同时保留 PDF 物理页码，减少封面、目录、摘要等前置页导致的页码错位。
- 站内通知查询与已读标记。
- React + Vite 前端骨架，可用于后续联调。

### 尚未完成

- 教务与管理员的细粒度查询视图。
- 队列化异步任务执行。
- 参考文档 PDF 到 Markdown 的正式转换流程。
- 自动化测试、CI、生产部署配置。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Pydantic
- 智能体：Agno
- 模型接入：OpenAI / OpenAI-compatible API
- 数据库：SQLite（默认），后续可切换
- 前端：React、TypeScript、Vite
- 环境管理：uv

## 目录结构

```text
app/
  agents/        Agno 智能体定义
  core/          配置、常量、安全相关逻辑
  routers/       FastAPI 路由
  schemas/       请求/响应与结构化输出模型
  services/      文件存储、分析执行等服务
docs/
  requirements.md
  development.md
frontend/
  src/           前端页面与 API 客户端
scripts/
  lint.sh        Ruff 检查与格式化脚本
  clean_local_data.sh  清理本地运行数据
source/
  common-problems-for-students.pdf
  common-problems-for-students.md
```

## 本地开发

详细开发说明见 [docs/development.md](/Users/lzq/project/thesis-gravity/docs/development.md)。

### 1. 准备环境

要求：

- Python 3.12+
- Node.js 18+
- `uv`

安装后端依赖：

```bash
uv sync
```

安装前端依赖：

```bash
cd frontend
npm install
```

### 2. 配置环境变量

复制环境变量模板并按需调整：

```bash
cp .env.example .env
```

至少需要确认以下配置：

- `JWT_SECRET_KEY`
- `LLM_PROVIDER`
- `LLM_MODEL_ID`
- `LLM_API_KEY`
- `LLM_BASE_URL`（使用兼容网关时）
- `VISION_LLM_MODEL_ID`、`VISION_LLM_API_KEY`、`VISION_LLM_BASE_URL`（需要自动做图表视觉检查时）
- `LOG_LEVEL`
- `REFERENCE_DOC_PATH`

如果只做接口联调，不调用真实模型，可以先保留默认值，但分析任务会在实际执行模型时失败。

### 3. 启动后端

```bash
uv run fastapi dev app/main.py
```

也可以用根目录脚本启动：

```bash
./start.sh
```

生产模式：

```bash
./start.sh prod
```

默认地址：

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`

首次启动会自动创建：

- `data/app.db`
- `data/theses/`

### 4. 启动前端

```bash
cd frontend
npm run dev
```

默认前端地址：

- `http://127.0.0.1:5173`

可通过 `VITE_API_BASE_URL` 指向后端服务。

`./start.sh prod` 会先构建前端，再用 FastAPI 提供静态资源和 API。
开发模式下，`./start.sh` 会把前端日志写入临时文件；如果 Vite 启动失败，会直接输出日志并退出。

## 关键环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_NAME` | `Thesis Guidance` | FastAPI 应用名 |
| `DATABASE_URL` | `sqlite:///data/app.db` | 数据库连接串 |
| `DATA_DIR` | `data/` | SQLite 与运行时数据目录 |
| `JWT_SECRET_KEY` | `change-me` | JWT 密钥，正式环境必须替换 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `60` | Token 过期时间 |
| `SESSION_COOKIE_NAME` | `tg_session` | 会话 Cookie 名称 |
| `SESSION_COOKIE_SECURE` | `false` | 是否仅允许 HTTPS 发送 Cookie，生产环境应设为 `true` |
| `SESSION_COOKIE_SAMESITE` | `strict` | 会话 Cookie 的 SameSite 策略 |
| `LLM_PROVIDER` | `openai` | Agno 模型提供方 |
| `LLM_MODEL_ID` | `gpt-4o-mini` | 模型标识 |
| `LLM_API_KEY` | 空 | 模型访问密钥 |
| `LLM_BASE_URL` | 空 | OpenAI-compatible 网关地址 |
| `VISION_LLM_PROVIDER` | 跟随 `LLM_PROVIDER` | 视觉模型提供方 |
| `VISION_LLM_MODEL_ID` | 空 | 图表视觉检查专用模型；为空时图表视觉类条目仅标记为待人工复核 |
| `VISION_LLM_API_KEY` | 跟随 `LLM_API_KEY` | 视觉模型访问密钥 |
| `VISION_LLM_BASE_URL` | 跟随 `LLM_BASE_URL` | 视觉模型网关地址 |
| `LOG_LEVEL` | `DEBUG` | 应用日志级别 |
| `REFERENCE_DOC_PATH` | `source/common-problems-for-students.md` | 参考规范文档，仅支持 `.md/.txt` |
| `MAX_PAGES` | `120` | 单次分析允许的最大页数；超过该页数时任务直接失败，不再静默截断 |
| `MAX_PAGE_CHARS` | `4000` | 单页截断字符数 |
| `MAX_CHECK_ITEMS_PER_BATCH` | `8` | 文本/视觉模型每批次处理的清单项数量 |
| `MAX_PAGES_PER_CHECK` | `6` | 每项文本检查最多检索的页数 |
| `MAX_PAGES_PER_BATCH` | `12` | 单次文本模型批处理最多拼接的页数，避免长论文上下文过大 |
| `MAX_VISUAL_IMAGES_PER_BATCH` | `4` | 单次视觉模型调用最多附带的图表截图或整页截图数量 |
| `LOCAL_REVIEW_PAGE_BATCH_SIZE` | `30` | 文本模型做局部段落审阅时的页批次大小 |
| `SEGMENT_REVIEW_PAGE_CHARS` | `2000` | 局部段落审阅时，每页最多带入的摘要字符数 |
| `GLOBAL_ANCHOR_PAGE_CHARS` | `500` | 全局梗概审阅时，每个锚点页最多带入的摘要字符数 |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | 允许跨域来源 |

## 已实现接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/login` | 登录并设置 `HttpOnly` 会话 Cookie |
| `POST` | `/auth/logout` | 清除当前会话 Cookie |
| `GET` | `/auth/me` | 获取当前登录用户 |
| `GET` | `/theses` | 学生获取自己的论文任务与版本列表 |
| `POST` | `/theses/drafts` | 学生上传论文草稿 PDF；首次创建论文任务，后续可带 `thesis_id` 追加新版本 |
| `GET` | `/theses/usage-stats` | 学生查看个人 AI 调用统计汇总（单价与费用暂不计算） |
| `GET` | `/theses/versions/{version_id}/file` | 按权限预览某个版本的 PDF |
| `GET` | `/tasks` | 获取当前用户可见的分析任务列表 |
| `GET` | `/tasks/{task_id}` | 查询分析任务状态与结果 |
| `POST` | `/tasks/{task_id}/submit-for-mentor` | 学生将当前最新版本提交导师审核 |
| `GET` | `/notifications` | 获取当前用户通知 |
| `POST` | `/notifications/{id}/read` | 标记通知已读 |
| `GET` | `/mentor/pending-reviews` | 导师获取待评审版本列表 |
| `GET` | `/mentor/theses` | 导师按学生/论文查看当前论文进度，可搜索 |
| `GET` | `/mentor/versions/{version_id}` | 导师查看版本详情与分析结果 |
| `GET` | `/mentor/reviews/{version_id}` | 查询某版本的导师评审记录 |
| `POST` | `/mentor/reviews` | 导师提交评审（approved / changes_requested） |
| `GET` | `/health` | 健康检查 |

## 开发约定

- Python 使用 `uv`、`.venv/bin/python` 或 `uv run` 执行。
- 默认使用绝对导入。
- 前端不保存 Bearer token；登录态通过 `HttpOnly` Cookie 维持。
- 上传文件仅支持 PDF。
- 上传的 PDF 必须可解析且能提取到文本内容；空白文件、纯图片扫描件会被拒绝，且不会保留无效上传文件。
- 论文分析参考文档当前只读取 Markdown 或纯文本，不直接读取 PDF。
- 学生侧流程按论文任务推进：`analysis_pending`（AI 处理中）、`analysis_done`（待提交导师）、`mentor_review`（审核中）、`changes_requested`（待修改）、`approved`（已完成）。
- 导师待评审列表只展示每篇论文当前最新、且已提交导师审核的版本。
- 提交前运行：

```bash
./scripts/lint.sh --all
```

- 清理本地运行数据前先查看帮助：

```bash
./scripts/clean_local_data.sh
```

- 启动脚本只检查依赖，不会自动安装。缺少后端依赖时先执行 `uv sync --all-groups`，缺少前端依赖时先执行 `cd frontend && npm install`。

- 可选：安装 pre-commit

```bash
uv run pre-commit install
```

## 正式开发前建议

### P0

- 将 `JWT_SECRET_KEY` 改为非默认值。
- 补齐导师评审路由、Schema 与权限校验。
- 为认证、上传、分析任务状态流转补测试。
- 明确参考文档维护流程，避免 PDF 与 Markdown 内容漂移。

### P1

- 引入 Alembic 管理数据库迁移。
- 将后台任务从 `BackgroundTasks` 迁移到独立任务队列。
- 增加统一日志、异常追踪和审计字段。

### P2

- 补齐前端与后端端到端联调脚本。
- 增加 SMTP 邮件通知。
- 拆分多角色工作台页面。

## 需求文档

- 需求基线见 [docs/requirements.md](/Users/lzq/project/thesis-gravity/docs/requirements.md)

## 说明

- `source/common-problems-for-students.pdf` 是原始论文规范文档。
- `source/common-problems-for-students.md` 是转换后的规范文档。
