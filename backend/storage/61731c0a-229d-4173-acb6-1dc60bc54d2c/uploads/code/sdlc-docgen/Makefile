.PHONY: up down ps logs db-psql backend-install backend-dev backend-test backend-lint frontend-install frontend-dev frontend-build init-git

COMPOSE := docker compose -f infra/docker-compose.yml

## Infra ----------------------------------------------------------------------
up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

db-psql:
	$(COMPOSE) exec db psql -U docgen -d docgen

## Backend --------------------------------------------------------------------
backend-install:
	python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt

backend-dev:
	.venv/bin/uvicorn app.main:app --reload --port 8000

backend-test:
	cd backend && ../.venv/bin/pytest -q

backend-lint:
	cd backend && ../.venv/bin/ruff check .

## Frontend -------------------------------------------------------------------
frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
