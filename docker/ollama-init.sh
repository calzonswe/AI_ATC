#!/bin/bash
set -euo pipefail

# ──────────────────────────────────────────────────────
# Ollama initialisation script
# Runs on container startup; pulls the target model if
# it is not already present locally.
# ──────────────────────────────────────────────────────

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL="${OLLAMA_MODEL:-qwen3:30b}"
OLLAMA_BIN="/usr/bin/ollama"

echo "==> Ollama init: checking for model '${MODEL}'"

# Wait for Ollama server to be ready
for i in $(seq 1 30); do
    if curl -sf "${OLLAMA_HOST}/api/tags" > /dev/null 2>&1; then
        echo "==> Ollama server is ready"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "==> WARNING: Ollama server not reachable after 30s — continuing"
    fi
    sleep 1
done

# Pull the model if not already present
if ${OLLAMA_BIN} list 2>/dev/null | grep -q -E "^${MODEL}\b"; then
    echo "==> Model '${MODEL}' already present"
else
    echo "==> Pulling model '${MODEL}' (this may take a while on first run)..."
    ${OLLAMA_BIN} pull "${MODEL}" || echo "==> WARNING: 'ollama pull' failed — will retry on demand"
fi

echo "==> Ollama init complete"
