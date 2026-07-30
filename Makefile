.PHONY: setup install lint test test-e2e test-all clean build up down logs

# ── Initial Setup ────────────────────────────────────────────────

setup:
	@scripts/setup.sh

install:
	@scripts/setup.sh

# ── Lint & Type Check ───────────────────────────────────────────

lint:
	uv run ruff check apps services packages tests
	uv run ruff format --check apps services packages tests

lint-fix:
	uv run ruff check --fix apps services packages tests

typecheck:
	uv run pyright

# ── Testing ──────────────────────────────────────────────────────

test:
	uv run pytest apps/server/tests apps/client/tests packages/ tests/e2e/ -v

test-server:
	uv run pytest apps/server/tests -v

test-client:
	uv run pytest apps/client/tests -v

test-e2e:
	uv run pytest tests/e2e/ -v

test-all: test-server test-client test-e2e

test-cov:
	uv run pytest --cov=apps --cov=services --cov=packages --cov-report=term-missing -v

# ── Docker ───────────────────────────────────────────────────────

build:
	docker compose -f docker/docker-compose.yml build

up:
	docker compose -f docker/docker-compose.yml up -d

down:
	docker compose -f docker/docker-compose.yml down

logs:
	docker compose -f docker/docker-compose.yml logs -f

ps:
	docker compose -f docker/docker-compose.yml ps

# ── Cleanup ──────────────────────────────────────────────────────

clean:
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf **/.pytest_cache
	rm -rf **/__pycache__
	rm -rf **/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
