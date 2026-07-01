#!/bin/sh -e
# set -x

MODE="${1:-dev}"
PROJECT_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

print_usage() {
	printf "Usage: %s [dev|prod]\n" "$0"
	printf "  dev   Start backend and frontend in development mode (default).\n"
	printf "  prod  Build frontend and start FastAPI with the built frontend.\n"
}

run_dev() {
	# Fail fast on missing frontend dependencies instead of mutating the environment.
	if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
		printf "frontend/node_modules is missing. Run: cd frontend && npm install\n" >&2
		exit 1
	fi

	# 前端：后台启动，不用 nohup。终端关闭时它随 SIGHUP 退出；正常退出时由 EXIT trap 清理。
	cd "$PROJECT_ROOT/frontend"
	mkdir -p "$PROJECT_ROOT/logs"
	frontend_log="$PROJECT_ROOT/logs/frontend-dev-$(date +%Y%m%d).log"
	npm run dev >> "$frontend_log" 2>&1 &
	frontend_pid=$!
	cd "$PROJECT_ROOT"

	# 给 Vite 一个短暂启动窗口；若提前退出，直接回显日志并失败，避免打印误导地址。
	sleep 2
	if ! kill -0 "$frontend_pid" 2>/dev/null; then
		printf "frontend dev server failed to start. Logs:\n" >&2
		cat "$frontend_log" >&2
		exit 1
	fi

	# 打印前端地址，用空行和分隔符让它在 FastAPI 输出前清晰可见
	printf "\n  ➜  Frontend:   http://localhost:5173\n"
	printf "  ➜  Backend:    http://127.0.0.1:8000\n"
	printf "  ➜  API Docs:   http://127.0.0.1:8000/docs\n\n"
	printf "  ➜  Frontend log: %s\n\n" "$frontend_log"

	# 仅此一条：后端退出时（正常、异常、或 Ctrl+C 导致后端退出后）自动杀前端
	trap 'kill "$frontend_pid" 2>/dev/null; wait "$frontend_pid" 2>/dev/null' EXIT

	# 后端：前台运行，阻塞 shell。Ctrl+C 直接发给后端进程组，shell 不参与。
	uv run fastapi dev app/main.py
}

run_prod() {
	# Production mode still requires preinstalled dependencies and a successful frontend build.
	if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
		printf "frontend/node_modules is missing\n" >&2
		exit 1
	fi

	export ENV=production

	(
		cd "$PROJECT_ROOT/frontend"
		npm run build
	)

	cd "$PROJECT_ROOT"
	# prod 只跑后端，exec 替换 shell 最干净
	exec uv run fastapi run app/main.py --host 0.0.0.0 --port 8000
}

case "$MODE" in
	-h|--help)
		print_usage
		exit 0
		;;
	dev)
		run_dev
		;;
	prod)
		run_prod
		;;
	*)
		printf "Unknown mode: %s\n" "$MODE"
		print_usage
		exit 2
		;;
esac
