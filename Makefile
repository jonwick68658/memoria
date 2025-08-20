# Memoria AI - Makefile
# Build, test, and deployment commands

.PHONY: help install dev-install test test-coverage lint format type-check security-check clean build docker-build docker-run docker-compose-up docker-compose-down migrate migrate-up migrate-down seed-db run-dev run-prod docs docs-serve setup-dev setup-prod backup-db restore-db deploy-staging deploy-prod

# Default target
help:
	@echo "Memoria AI - Available Commands"
	@echo "==============================="
	@echo ""
	@echo "Development:"
	@echo "  make setup-dev      - Set up development environment"
	@echo "  make install        - Install production dependencies"
	@echo "  make dev-install    - Install development dependencies"
	@echo "  make run-dev        - Run development server"
	@echo "  make test           - Run tests"
	@echo "  make test-coverage  - Run tests with coverage"
	@echo "  make lint           - Run linting"
	@echo "  make format         - Format code"
	@echo "  make type-check     - Run type checking"
	@echo "  make docs           - Build documentation"
	@echo "  make docs-serve     - Serve documentation locally"
	@echo ""
	@echo "Database:"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migrate-up     - Apply pending migrations"
	@echo "  make migrate-down   - Rollback last migration"
	@echo "  make seed-db        - Seed database with test data"
	@echo "  make backup-db      - Backup database"
	@echo "  make restore-db     - Restore database from backup"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-run     - Run Docker container"
	@echo "  make docker-compose-up   - Start all services with Docker Compose"
	@echo "  make docker-compose-down - Stop all services"
	@echo ""
	@echo "Production:"
	@echo "  make setup-prod     - Set up production environment"
	@echo "  make run-prod       - Run production server"
	@echo "  make security-check - Run security checks"
	@echo "  make build          - Build production package"
	@echo "  make deploy-staging - Deploy to staging"
	@echo "  make deploy-prod    - Deploy to production"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make help           - Show this help message"

# Environment setup
setup-dev:
	@echo "Setting up development environment..."
	python -m venv venv
	. venv/bin/activate && pip install --upgrade pip
	. venv/bin/activate && pip install -e .[dev,all]
	. venv/bin/activate && pre-commit install
	@echo "Development environment setup complete!"

setup-prod:
	@echo "Setting up production environment..."
	pip install --upgrade pip
	pip install -e .[all]
	@echo "Production environment setup complete!"

# Installation
install:
	pip install -e .

dev-install:
	pip install -e .[dev,all]

# Testing
test:
	pytest tests/ -v

test-coverage:
	pytest tests/ -v --cov=src/memoria --cov-report=html --cov-report=term

test-integration:
	python test_integration.py

test-watch:
	ptw tests/ -- -v

# Code quality
lint:
	flake8 src/ tests/
	pylint src/memoria/
	bandit -r src/
	safety check

format:
	black src/ tests/
	isort src/ tests/
	black --check src/ tests/
	isort --check-only src/ tests/

type-check:
	mypy src/memoria/ --strict

security-check:
	bandit -r src/
	safety check
	semgrep --config=auto src/

# Database operations
migrate:
	alembic upgrade head

migrate-up:
	alembic upgrade +1

migrate-down:
	alembic downgrade -1

migrate-create:
	alembic revision --autogenerate -m "$(m)"

seed-db:
	python scripts/seed_database.py

backup-db:
	@echo "Creating database backup..."
	docker exec memoria-postgres-1 pg_dump -U memoria memoria_db > backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "Backup created: backup_$(shell date +%Y%m%d_%H%M%S).sql"

restore-db:
	@echo "Restoring database from backup..."
	@read -p "Enter backup file name: " backup_file; \
	docker exec -i memoria-postgres-1 psql -U memoria memoria_db < $$backup_file

# Development server
run-dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-prod:
	gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000

# Docker operations
docker-build:
	docker build -t memoria-ai:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env memoria-ai:latest

docker-compose-up:
	docker-compose up -d

docker-compose-down:
	docker-compose down

docker-compose-logs:
	docker-compose logs -f

docker-compose-build:
	docker-compose build

# Documentation
docs:
	cd docs && make html

docs-serve:
	cd docs && make html && python -m http.server 8001 -d _build/html

docs-clean:
	cd docs && make clean

# Building
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

build:
	python -m build

# Deployment
deploy-staging:
	@echo "Deploying to staging..."
	./scripts/deploy-staging.sh

deploy-prod:
	@echo "Deploying to production..."
	./scripts/deploy-production.sh

# Monitoring
logs:
	docker-compose logs -f memoria-api

logs-api:
	docker-compose logs -f memoria-api

logs-worker:
	docker-compose logs -f celery-worker

logs-beat:
	docker-compose logs -f celery-beat

# Performance testing
load-test:
	locust -f tests/load_test.py --host=http://localhost:8000

# Database initialization
init-db:
	alembic init alembic
	alembic revision --autogenerate -m "Initial migration"
	alembic upgrade head

# Health checks
health-check:
	curl -f http://localhost:8000/healthz || exit 1

# Environment management
env-dev:
	cp .env.example .env
	@echo "Created .env file from .env.example"
	@echo "Please edit .env with your actual configuration values"

env-prod:
	cp .env.example .env.production
	@echo "Created .env.production file from .env.example"
	@echo "Please edit .env.production with your production configuration values"

# Quick start
quick-start: env-dev setup-dev docker-compose-up migrate seed-db
	@echo "🎉 Memoria AI is ready!"
	@echo "API: http://localhost:8000"
	@echo "Docs: http://localhost:8000/docs"
	@echo "Flower: http://localhost:5555"
	@echo "Grafana: http://localhost:3000 (admin/admin123)"

# CI/CD helpers
ci-test:
	pytest tests/ -v --cov=src/memoria --cov-report=xml --junitxml=test-results.xml

ci-lint:
	black --check src/ tests/
	isort --check-only src/ tests/
	flake8 src/ tests/
	mypy src/memoria/ --strict

ci-security:
	bandit -r src/ -f json -o security-report.json
	safety check --json --output safety-report.json

# Development utilities
shell:
	docker-compose exec memoria-api bash

db-shell:
	docker-compose exec postgres psql -U memoria -d memoria_db

redis-cli:
	docker-compose exec redis redis-cli

# Maintenance
update-deps:
	pip-compile requirements.in
	pip-compile requirements-dev.in

upgrade-deps:
	pip install --upgrade -r requirements.txt
	pip install --upgrade -r requirements-dev.txt

# Version management
bump-version:
	@read -p "Enter new version (e.g., 1.0.0): " version; \
	bump2version $$version

# Release
release-patch:
	bump2version patch

release-minor:
	bump2version minor

release-major:
	bump2version major

# Git hooks
install-hooks:
	pre-commit install
	pre-commit install --hook-type commit-msg

# Data management
export-data:
	python scripts/export_data.py

import-data:
	python scripts/import_data.py

# Cache management
clear-cache:
	docker-compose exec redis redis-cli FLUSHALL
	@echo "Redis cache cleared"

clear-vector-cache:
	docker-compose exec weaviate curl -X DELETE http://localhost:8080/v1/schema
	@echo "Weaviate vector cache cleared"

# System monitoring
system-stats:
	@echo "System Resource Usage:"
	@echo "====================="
	@docker stats --no-stream
	@docker system df

# Backup and restore
backup-all:
	./scripts/backup-all.sh

restore-all:
	./scripts/restore-all.sh

# Testing utilities
test-api:
	python -m pytest tests/test_api.py -v

test-security:
	python -m pytest tests/test_security.py -v

test-integration-local:
	python test_integration.py

# Quick commands
up: docker-compose-up
down: docker-compose-down
restart: docker-compose-down docker-compose-up
logs: logs-api
test: test
dev: run-dev
prod: run-prod