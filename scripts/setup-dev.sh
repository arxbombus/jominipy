#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$ROOT_DIR"

if ! command -v uv >/dev/null 2>&1; then
	echo "uv is required but not installed. Please install uv (https://docs.astral.sh/uv/getting-started/) and rerun this script." >&2
	exit 1
fi

echo "Syncing dependencies with uv..."
uv sync

echo "Installing git hooks with lefthook..."
uv run lefthook install

if [ -f ".venv/bin/activate" ]; then
	echo "Activating virtual environment..."
	# shellcheck disable=SC1091
	source .venv/bin/activate
else
	echo "Expected virtual environment at .venv/bin/activate but it was not found." >&2
	exit 1
fi

echo "Development environment is ready."
