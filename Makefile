# Makefile
# --------
# Usage:
# make [COMMAND]
# E.g.:
# make build

.PHONY: build clean test clean-pycache format

install:
	pip install -U pip wheel
	pip install .[dev]
	pip uninstall gemsrun -y
	make clean

format:
	ruff check gemsrun --fix
	ruff format gemsrun
	black gemsrun

build:
	python -m build

clean:
	rm -rf build dist *.egg-info

test:
	PYTHONPATH=$(shell pwd) pytest tests/
	PYTHONPATH=$(shell pwd) pytest tests/unittests/
	PYTHONPATH=$(shell pwd) pytest tests/guitests/

clean-pycache:
	find . -type d -name "__pycache__" -exec rm -rf {} +
