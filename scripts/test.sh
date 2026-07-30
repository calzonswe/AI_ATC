#!/usr/bin/env bash
set -euo pipefail

echo "==> Running pytest with coverage"
uv run pytest --cov=apps --cov=services --cov=packages --cov-report=term-missing -v
