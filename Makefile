.PHONY: clean test coverage build install lint

# ============================================================================ #
# CLEAN COMMANDS
# ============================================================================ #

clean: clean-build clean-pyc clean-test ## remove all build, test, coverage and Python artifacts

clean-build: ## remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

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
	pytest

test-all: ## run tests on every Python version with tox
	tox

test-regen-json:  ## rerun the json conversion to JSON of the test artifacts
	compass convert -i tests/artifacts/1998.dat -o tests/artifacts/1998.json -f json -w
	compass convert -i tests/artifacts/flags.dat -o tests/artifacts/flags.json -f json -w
	compass convert -i tests/artifacts/flags.dat -o tests/artifacts/flags.json -f json -w
	compass convert -i tests/artifacts/fulford.dat -o tests/artifacts/fulford.json -f json -w
	compass convert -i tests/artifacts/fulsurf.dat -o tests/artifacts/fulsurf.json -f json -w
	compass convert -i tests/artifacts/random.dat -o tests/artifacts/random.json -f json -w
	compass convert -i tests/artifacts/unicode.dat -o tests/artifacts/unicode.json -f json -w

coverage: ## check code coverage quickly with the default Python
	coverage run --source comp_bench_tools -m pytest
	coverage report -m
	coverage html
	$(BROWSER) htmlcov/index.html

# ============================================================================ #
# BUILD COMMANDS
# ============================================================================ #

build: clean ## builds source and wheel package
	pip install --upgrade wheel
	python3 -m build --wheel
	ls -l dist

publish: build
	pip install --upgrade twine
	twine upload --config-file=.pypirc dist/*.whl

# ============================================================================ #
# INSTALL COMMANDS
# ============================================================================ #

install: clean ## install the package to the active Python's site-packages
	pip install -e ".[dev,test]"

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
