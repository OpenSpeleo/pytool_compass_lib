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

DATA_DIRS := \
	tests/artifacts/dlubom/ciekawa \
	tests/artifacts/dlubom/hagen_all \
	tests/artifacts/fountainware \
	tests/artifacts/migovecsurveydata \
	tests/artifacts/plankermira \
	tests/artifacts/private \
	tests/artifacts/sausage-cave-map \
	tests/artifacts/suu-akan \
	tests/artifacts/synthese_clot_daspres \
	tests/artifacts/synthese-psm_larra/complexe_lonne_peyret-bourrugues \
	tests/artifacts/synthese-psm_larra/database_criou \
	tests/artifacts/synthese-psm_larra/database_hashim-oyuk \
	tests/artifacts/synthese-psm_larra/database_jb \
	tests/artifacts/synthese-psm_larra/gouffre_z510 \
	tests/artifacts/synthese-psm_larra/lonne_peyret \
	tests/artifacts/synthese-psm_larra/padavka \
	tests/artifacts/synthese-psm_larra/rabbit \
	tests/artifacts/synthese-psm_larra/z510

test-regen-json:  ## rerun the json conversion to JSON of the test artifacts
	@for dir in $(DATA_DIRS); do \
		shopt -s nocaseglob; \
		for file in $$dir/*.dat; do \
			[ -f "$$file" ] || continue; \
			out=$${file%.[dD][aA][tT]}.json; \
			echo "Converting $$file → $$out"; \
			compass convert -i "$$file" -o "$$out" -f json -w; \
		done; \
		shopt -u nocaseglob; \
	done

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
# Encryption
# ============================================================================ #

ENCRYPTED_FILES_DIR := tests/artifacts/private

encrypt:
	@for file in ${ENCRYPTED_FILES_DIR}/*.clear.dat ${ENCRYPTED_FILES_DIR}/*.clear.json; do \
		if [ -f "$$file" ]; then \
			echo "Encrypting $$file -> $$file.encrypted"; \
			compass encrypt -i "$$file" -o "$$file.encrypted" -e .env -w; \
		fi; \
	done
