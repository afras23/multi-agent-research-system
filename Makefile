.PHONY: dev test lint format typecheck migrate docker clean evaluate

PYTHON ?= python3
PIP ?= pip3

dev:
	$(PIP) install -r requirements-dev.txt

test:
	pytest tests/

lint:
	ruff check app/ tests/

format:
	ruff format app/ tests/

typecheck:
	mypy app/

migrate:
	alembic upgrade head

docker:
	docker compose up --build

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage

evaluate:
	$(PYTHON) scripts/evaluate.py
