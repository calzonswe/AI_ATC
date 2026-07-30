#!/usr/bin/env bash
set -euo pipefail

echo "==> Running ruff check"
uv run ruff check apps services packages

echo "==> Running ruff format check"
uv run ruff format --check apps services packages

echo "==> Running pyright"
uv run pyright
