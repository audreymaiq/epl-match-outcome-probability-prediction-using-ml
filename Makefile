# ══════════════════════════════════════════════════════════════════════════════
# Makefile - Premier League Match Outcome Probability Prediction
# ══════════════════════════════════════════════════════════════════════════════

.DEFAULT_GOAL := help
SHELL := /bin/bash

# ── Docker ────────────────────────────────────────────────────────────────────

.PHONY: up down restart logs ps

up: ## Start all core services
	docker compose up -d

down: ## Stop all services
	docker compose down

restart: ## Restart all services
	docker compose restart

logs: ## Tail logs (all services)
	docker compose logs -f

ps: ## Show running services
	docker compose ps

# ── Pipeline ──────────────────────────────────────────────────────────────────

.PHONY: pipeline features train

pipeline: ## Run ELT pipeline (fetch match data)
	docker compose --profile pipeline run --rm pipeline

features: ## Compute all ML features
	docker compose exec api python -m feature_pipeline.orchestrator

train: ## Train the ensemble model (walk-forward CV)
	docker compose exec api python -m ml.training.train

# ── Development ───────────────────────────────────────────────────────────────

.PHONY: test test-backend test-frontend lint

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend Python tests (60 tests)
	cd backend && PYTHONPATH=. python -m pytest tests/ -v

test-frontend: ## Type-check and build frontend
	cd frontend && npx next build

lint: ## Lint backend code
	cd backend && python -m flake8 api/ ml/ feature_pipeline/ providers/ --max-line-length 120

# ── Database ──────────────────────────────────────────────────────────────────

.PHONY: db-shell db-reset

db-shell: ## Open psql shell
	docker compose exec postgres psql -U $${DB_USER:-epl_user} -d $${DB_NAME:-epl_db}

db-reset: ## Reset database (DESTRUCTIVE)
	docker compose down -v
	docker compose up -d postgres
	@echo "Waiting for postgres..."
	sleep 5
	@echo "Database reset complete. Run 'make pipeline' to reload data."

# ── Cleanup ───────────────────────────────────────────────────────────────────

.PHONY: clean

clean: ## Remove runtime artifacts
	find backend -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f backend/cache/*.sqlite backend/logs/*.log
	rm -rf frontend/.next

# ── Help ──────────────────────────────────────────────────────────────────────

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

