.PHONY: clean test coverage build install lint

SHELL := /bin/bash

# ============================================================================ #
# CLEAN COMMANDS
# ============================================================================ #

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

clean-test: ## remove test and coverage artifacts
	rm -fr .tox/
	rm -f .coverage*
	rm -fr htmlcov/
	rm -fr .pytest_cache

# ============================================================================ #
# LINT COMMANDS
# ============================================================================ #

lint:
# Lint all files in the current directory (and any subdirectories).
	ruff check --fix

format:
# Format all files in the current directory (and any subdirectories).
	ruff format

# ============================================================================ #
# TEST COMMANDS
# ============================================================================ #

test: ## run tests quickly with the default Python
	pytest -n 24

test-all: ## run tests on every Python version with tox
	tox

coverage: ## check code coverage quickly with the default Python
	coverage run --source comp_bench_tools -m pytest
	coverage report -m
	coverage html
	$(BROWSER) htmlcov/index.html

# ============================================================================ #
# BUILD COMMANDS
# ============================================================================ #

build: clean
	flit build --format wheel

# ============================================================================ #
# INSTALL COMMANDS
# ============================================================================ #

install: clean
	uv sync --all-extras --dev

# ============================================================================ #
# Private Data Directory
# ============================================================================ #

PRIVATE_DATA_DIR := tests/artifacts/private

# ============================================================================ #
# Encryption
# ============================================================================ #

encrypt:
	@shopt -s nocaseglob; \
	for file in $(PRIVATE_DATA_DIR)/*.{mak,dat,kml,geojson,json}; do \
		if [ -f "$$file" ]; then \
			echo "Encrypting $$file -> $$file.encrypted"; \
			compass encrypt -i "$$file" -o "$$file.encrypted" --compress -e .env -w; \
		fi; \
	done

# ============================================================================ #
# Test File Generation
# ============================================================================ #

regen-test-geojson:  ## rerun the json conversion to JSON of the test artifacts
	@shopt -s nocaseglob; \
	for file in $(PRIVATE_DATA_DIR)/*.mak; do \
		[ -f "$$file" ] || continue; \
		out=$${file%.[mM][aA][kK]}.geojson; \
		echo "Converting $$file → $$out"; \
		compass geojson -i "$$file" -o "$$out" --passages; \
	done; \
	shopt -u nocaseglob;

regen-test-json:  ## rerun the json conversion to JSON of the test artifacts
	@shopt -s nocaseglob; \
	for file in $(PRIVATE_DATA_DIR)/*.{mak,dat}; do \
		[ -f "$$file" ] || continue; \
		out=$$file.json; \
		echo "Converting $$file → $$out"; \
		compass convert -i "$$file" -o "$$out" -f json; \
	done; \
	shopt -u nocaseglob;


regen-test-files: regen-test-geojson regen-test-json encrypt
