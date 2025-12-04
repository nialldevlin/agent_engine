SHELL := /bin/bash
PYTHON ?= python3
VENV ?= .venv
ACTIVATE = . $(VENV)/bin/activate

.PHONY: install format lint typecheck test coverage clean

$(VENV)/bin/activate:
	$(PYTHON) -m venv $(VENV)

install: $(VENV)/bin/activate
	$(ACTIVATE) && $(PYTHON) -m pip install --upgrade pip
	$(ACTIVATE) && $(PYTHON) -m pip install -e .[dev]

format:
	$(ACTIVATE) && ruff format src tests

lint:
	$(ACTIVATE) && ruff check src tests

typecheck:
	$(ACTIVATE) && mypy src

test:
	PYTHONPATH=src $(ACTIVATE) && pytest

coverage:
	PYTHONPATH=src $(ACTIVATE) && pytest --cov=agent_engine --cov-report=term-missing

clean:
	rm -rf $(VENV) .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov
