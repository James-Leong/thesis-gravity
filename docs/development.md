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

## 认证约定

- 前端不保存 Bearer token
- 登录态通过 `HttpOnly` Cookie 维持
