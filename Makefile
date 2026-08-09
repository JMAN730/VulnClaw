.PHONY: help install install-frontend test test-go lint build build-python build-frontend build-go release-preflight release-preflight-build dev-web

PYTHON ?= python
PIP ?= $(PYTHON) -m pip
NPM ?= npm
GO ?= go

help:
	@printf '%s\n' \
		'VulnClaw development targets:' \
		'  make install          Install Python dev extras and frontend dependencies' \
		'  make test             Run the backend pytest suite' \
		'  make test-go          Run the Go edge tests' \
		'  make lint             Run Ruff checks' \
		'  make build            Build Python distributions and the frontend' \
		'  make build-go         Build the opt-in Go web edge' \
		'  make release-preflight Run release validation script' \
		'  make release-preflight-build Run release validation with dist checks' \
		'  make dev-web          Start the frontend Vite dev server'

install:
	$(PIP) install -e ".[dev,web,pdf]"
	$(NPM) --prefix frontend install

install-frontend:
	$(NPM) --prefix frontend install

test:
	$(PYTHON) -m pytest

test-go:
	$(GO) test ./cmd/vulnclaw-edge/...

lint:
	$(PYTHON) -m ruff check .

build: build-python build-frontend

build-python:
	$(PYTHON) -m build

build-frontend:
	$(NPM) --prefix frontend run build

build-go:
	$(GO) build -o bin/vulnclaw-edge ./cmd/vulnclaw-edge

release-preflight:
	$(PYTHON) scripts/release_preflight.py

release-preflight-build:
	$(PYTHON) scripts/release_preflight.py --build

dev-web:
	$(NPM) --prefix frontend run dev
