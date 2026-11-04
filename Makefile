.DEFAULT_GOAL := help
PYTHON ?= python
LEAGUE ?= epl
SOURCE ?= sofascore
SEASON_COUNT ?= 7
CLI = docker compose --profile operations run --rm cli

.PHONY: help up down logs ps migrate pipeline ingest features train status test test-backend test-frontend check-frontend

help:
	@echo "up, down, logs, ps, migrate, pipeline, ingest, features, train, status"
	@echo "test, test-backend, test-frontend, check-frontend"
	@echo "Options: LEAGUE=epl SOURCE=sofascore SEASON_COUNT=7 PYTHON=python"
	@echo "Training creates a candidate. Activate explicitly with the football CLI."

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

ps:
	docker compose ps

migrate:
	$(CLI) migrate

pipeline:
	$(CLI) pipeline run --league $(LEAGUE) --source $(SOURCE) --season-count $(SEASON_COUNT)

ingest:
	$(CLI) ingest --league $(LEAGUE) --source $(SOURCE) --season-count $(SEASON_COUNT)

features:
	$(CLI) features --league $(LEAGUE)

train:
	$(CLI) train --league $(LEAGUE)

status:
	$(CLI) pipeline status --league $(LEAGUE)

test: test-backend test-frontend

test-backend:
	cd backend && $(PYTHON) -m pytest tests -q

test-frontend:
	cd frontend && npm test

check-frontend:
	cd frontend && npm run typecheck && npm run lint && npm run build
