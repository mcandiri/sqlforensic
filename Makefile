.PHONY: install install-dev test lint type-check format clean build

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	pytest tests/ -v --tb=short

test-cov:
	pytest tests/ -v --cov=sqlforensic --cov-report=html --cov-report=term-missing

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

type-check:
	mypy src/sqlforensic/

clean:
	rm -rf build/ dist/ *.egg-info .mypy_cache .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

build: clean
	python -m build

all: install-dev lint type-check test
