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
- 分析任务创建、后台执行、状态查询。
- 基于 Agno 的论文草稿分析代理。
- 站内通知查询与已读标记。
- React + Vite 前端骨架，可用于后续联调。

### 尚未完成

- 导师评审接口与评审记录查询。
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
| `REFERENCE_DOC_PATH` | `source/common-problems-for-students.md` | 参考规范文档，仅支持 `.md/.txt` |
| `MAX_PAGES` | `30` | 单次分析最多读取页数 |
| `MAX_PAGE_CHARS` | `4000` | 单页截断字符数 |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | 允许跨域来源 |

## 已实现接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/auth/register` | 注册 |
| `POST` | `/auth/login` | 登录并设置 `HttpOnly` 会话 Cookie |
| `POST` | `/auth/logout` | 清除当前会话 Cookie |
| `GET` | `/auth/me` | 获取当前登录用户 |
| `POST` | `/theses/drafts` | 学生上传论文草稿 PDF |
| `GET` | `/tasks/{task_id}` | 查询分析任务状态与结果 |
| `GET` | `/notifications` | 获取当前用户通知 |
| `POST` | `/notifications/{id}/read` | 标记通知已读 |
| `GET` | `/health` | 健康检查 |

## 开发约定

- Python 使用 `uv`、`.venv/bin/python` 或 `uv run` 执行。
- 默认使用绝对导入。
- 前端不保存 Bearer token；登录态通过 `HttpOnly` Cookie 维持。
- 上传文件仅支持 PDF。
- 论文分析参考文档当前只读取 Markdown 或纯文本，不直接读取 PDF。
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
