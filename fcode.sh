#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
uv run --locked ruff check --fix .
uv run --locked ruff format .
