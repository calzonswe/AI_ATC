#!/usr/bin/env bash
set -euo pipefail

echo "==> OpenATC Bootstrap Setup"
echo ""

# ── Prerequisites ────────────────────────────────────────────────
echo "==> Checking prerequisites..."

PYTHON_OK=false
for cmd in python3.12 python3.11 python3.10 python3; do
    if command -v "$cmd" &>/dev/null; then
        VER=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        MAJOR=${VER%.*}
        MINOR=${VER#*.}
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 10 ]; then
            echo "  Python $VER found: $cmd"
            PYTHON_OK=true
            break
        fi
    fi
done

if [ "$PYTHON_OK" = false ]; then
    echo "Error: Python >=3.10 required. Install it first:"
    echo "  https://www.python.org/downloads/"
    exit 1
fi

if ! command -v docker &>/dev/null; then
    echo "Warning: docker not found. Install Docker Desktop for containerized setup."
    echo "  https://www.docker.com/products/docker-desktop/"
fi

# ── uv (Python package manager) ──────────────────────────────────
echo ""
echo "==> Installing uv (if not present)"
if ! command -v uv &>/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env" 2>/dev/null || true
fi

# ── Environment file ─────────────────────────────────────────────
echo ""
echo "==> Setting up .env"
if [ ! -f .env ]; then
    cp .env.example .env
    echo "  Created .env from .env.example — edit it to match your setup."
else
    echo "  .env already exists, skipping."
fi

# ── Virtual environment ──────────────────────────────────────────
echo ""
echo "==> Creating virtual environment"
uv venv

echo "==> Installing all workspace packages"
uv sync

# ── Done ─────────────────────────────────────────────────────────
echo ""
echo "============================================"
echo "  OpenATC setup complete!"
echo ""
echo "  Activate the environment:"
echo "    source .venv/bin/activate"
echo ""
echo "  Run tests:"
echo "    make test"
echo ""
echo "  Start with Docker:"
echo "    docker compose up -d"
echo ""
echo "  Start server locally:"
echo "    cd apps/server && uv run uvicorn main:app --reload"
echo ""
echo "  Start client (GUI):"
echo "    cd apps/client && uv run python main_gui.py"
echo "============================================"
