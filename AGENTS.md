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
- 完成功能开发应补测试；完成技术改造至少做回归验证。
