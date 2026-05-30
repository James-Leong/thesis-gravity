#!/bin/sh -e
set -x

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROJECT_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"

print_usage() {
	printf "Usage: %s --run\n" "$0"
	printf "  --run    Remove local runtime data under DATA_DIR after confirmation.\n"
	printf "  -h/--help  Show this help message.\n"
	printf "\n"
	printf "Default DATA_DIR: %s\n" "$DATA_DIR"
}

confirm_delete() {
	printf "This will permanently delete local runtime data under:\n"
	printf "  %s\n" "$DATA_DIR"
	printf "It may remove the SQLite database and uploaded thesis files.\n"
	printf "Type DELETE to continue: "
	read -r answer
	[ "$answer" = "DELETE" ]
}

run_cleanup() {
	if [ -z "$DATA_DIR" ] || [ "$DATA_DIR" = "/" ] || [ "$DATA_DIR" = "." ]; then
		printf "Refusing to operate on unsafe DATA_DIR: %s\n" "$DATA_DIR"
		exit 2
	fi

	if [ ! -d "$DATA_DIR" ]; then
		printf "DATA_DIR does not exist: %s\n" "$DATA_DIR"
		exit 0
	fi

	find "$DATA_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
	printf "Local runtime data cleared under %s\n" "$DATA_DIR"
}

case "${1:-}" in
	-h|--help|"")
		print_usage
		exit 0
		;;
	--run)
		if confirm_delete; then
			run_cleanup
		else
			printf "Aborted.\n"
			exit 1
		fi
		;;
	*)
		printf "Unknown option: %s\n" "$1"
		print_usage
		exit 2
		;;
esac
