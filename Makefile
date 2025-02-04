.PHONY: all lint

all_tests: lint unittest integrationtest

help:
	@echo "Please use 'make <target>' where <target> is one of:"
	@echo "  lint			to run flake8 on all Python files"
	@echo "  unittest		to run unit tests on connPFM"
	@echo "  integrationtest		to run integration tests"

lint:
	@flake8 connPFM

unittest:
	@py.test --skipintegration --cov-append --cov-report xml --cov-report term-missing --cov=connPFM connPFM

integration:
	@pip install -e ".[test]"
	@py.test --cov-append --cov-report xml --cov-report term-missing --cov=connPFM connPFM/tests/test_integration.py
