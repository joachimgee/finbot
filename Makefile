.PHONY: help install test lint format clean run-api

help:
	@echo "FinBot - Financial Market Analyzer"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make test       - Run tests with coverage"
	@echo "  make lint       - Run linting (flake8, mypy)"
	@echo "  make format     - Format code with black"
	@echo "  make clean      - Clean cache and build files"
	@echo "  make run-api    - Run FastAPI server"
	@echo "  make notebook   - Start Jupyter notebook"

install:
	pip install --upgrade pip
	pip install -r requirements.txt
	pip install -e .
	cp -n .env.example .env || true
	@echo "✅ Installation complete! Don't forget to edit .env with your API keys"

test:
	pytest tests/ -v --cov=financial_analyzer --cov-report=html --cov-report=term

lint:
	flake8 src/ --max-line-length=100 --exclude=__pycache__
	mypy src/ --ignore-missing-imports

format:
	black src/ tests/ --line-length=100

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
	@echo "✅ Cleaned cache and build files"

run-api:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

notebook:
	jupyter notebook notebooks/
