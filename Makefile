.PHONY: dev test testing lint format typecheck migrate docker clean evaluate

PYTHON ?= python3
PIP ?= pip3

dev:
	$(PIP) install -r requirements-dev.txt

test:
	pytest tests/

testing: test

lint:
	ruff check app/ tests/ scripts/

format:
	ruff format app/ tests/ scripts/

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
	PYTHONPATH=. $(PYTHON) scripts/evaluate.py
