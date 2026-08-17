.PHONY: help install install-frontend test lint lint-frontend build build-python build-frontend release-preflight release-preflight-build dev-web

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
NPM ?= npm

help:
	@printf '%s\n' \
		'VulnClaw development targets:' \
		'  make install          Install Python dev extras and frontend dependencies' \
		'  make test             Run the backend pytest suite' \
		'  make lint             Run Ruff checks' \
		'  make lint-frontend    Run oxlint (anti-slop) on the frontend' \
		'  make build            Build Python distributions and the frontend' \
		'  make release-preflight Run release validation script' \
		'  make release-preflight-build Run release validation with dist checks' \
		'  make dev-web          Start the frontend Vite dev server'

install:
	$(PIP) install -e ".[dev,web,pdf]"
	$(NPM) --prefix frontend install
	git config core.hooksPath .githooks

install-frontend:
	$(NPM) --prefix frontend install

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .

lint-frontend:
	$(NPM) --prefix frontend run lint -- --deny-warnings

build: build-python build-frontend

build-python:
	$(PYTHON) -m build

build-frontend:
	$(NPM) --prefix frontend run build

release-preflight:
	$(PYTHON) scripts/release_preflight.py

release-preflight-build:
	$(PYTHON) scripts/release_preflight.py --build

dev-web:
	$(NPM) --prefix frontend run dev
