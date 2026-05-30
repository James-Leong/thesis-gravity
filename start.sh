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
		printf "frontend/node_modules is missing. Run: cd frontend && npm install\n"
		exit 1
	fi

	python_cmd="uv run fastapi dev app/main.py"
	frontend_cmd="npm run dev"

	(
		cd "$PROJECT_ROOT"
		sh -c "$python_cmd"
	) &
	backend_pid=$!

	(
		cd "$PROJECT_ROOT/frontend"
		sh -c "$frontend_cmd"
	) &
	frontend_pid=$!

	trap 'kill "$backend_pid" "$frontend_pid" 2>/dev/null || true' INT TERM EXIT
	wait "$backend_pid" "$frontend_pid"
}

run_prod() {
	# Production mode still requires preinstalled dependencies and a successful frontend build.
	if [ ! -d "$PROJECT_ROOT/frontend/node_modules" ]; then
		printf "frontend/node_modules is missing. Run: cd frontend && npm install\n"
		exit 1
	fi

	(
		cd "$PROJECT_ROOT/frontend"
		npm run build
	)

	cd "$PROJECT_ROOT"
	uv run fastapi dev app/main.py --host 0.0.0.0 --port 8000
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
