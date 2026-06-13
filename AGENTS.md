# AGENTS.md

## Purpose

本项目是学位论文辅导系统，帮助学生完成论文写作，并辅助导师完成论文评审。

## Read This First

- 产品需求与范围：`docs/requirements.md`
- 开发与运行说明：`docs/development.md`
- 对外说明与项目概览：`README.md`

## Development Constraints

- Python 使用 `uv` 管理，执行时优先使用 `uv run` 或 `.venv/bin/python`。
- 后端框架使用 `fastapi`，智能体工作流框架使用 `agno`。
- 本地运行数据统一落在 `data/` 下。
- 前端登录态通过 `HttpOnly` Cookie 维持，生产环境后端接口必须校验权限。

## Documentation Rules

- 调整接口、状态枚举、环境变量、启动方式或脚本行为时，必须同步更新对应说明文档。
- 涉及启动、依赖安装、脚本使用的细节，写入 `docs/development.md`。

## Change Rules

- 不要提交本地运行产物、数据库、上传文件。
- **禁止自动删除 `data/` 下的任何内容**（包括 `data/app.db` 数据库文件、上传的论文 PDF 等）。涉及 `data/` 的删除操作必须先征求用户同意。
- 完成功能开发应补测试；完成技术改造至少做回归验证。

## Database Safety Rules

**这是最高优先级规则。违反以下任何一条都视为严重错误。**

- **严禁对 `data/app.db` 执行任何破坏性操作**，包括但不限于：`DELETE FROM`、`DROP TABLE`、`TRUNCATE`、`UPDATE` 无 WHERE 条件、`VACUUM`、直接替换文件等。
- **测试必须使用独立的测试数据库**。`tests/conftest.py` 已设置 `DATABASE_URL` 指向 `data/test.db`，所有测试自动隔离。不得在测试中覆盖此配置指向 `data/app.db`。
- **任何涉及数据库写入、修改、删除的脚本或代码，执行前必须确认目标数据库是测试库**（`data/test.db` 或其他明确标记为测试的数据库），而非 `data/app.db`。
- **运行测试前，确认 `DATABASE_URL` 指向测试库**。如果 `data/test.db` 不存在，测试框架会自动创建，不会影响 `data/app.db`。
- 如果需要手动操作数据库进行调试，优先使用 `sqlite3` 只读模式（`sqlite3 -readonly data/app.db`），或在副本上操作。
