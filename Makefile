.PHONY: install dev test lint policy-test config-check verify run compose-up compose-down

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install -e '.[dev,production]'

run:
	.venv/bin/duke-agent-fabric

dev:
	.venv/bin/duke-agent-fabric --reload

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check src tests
	.venv/bin/ruff format --check src tests

policy-test:
	opa fmt --fail policies
	opa test policies

config-check:
	python3 -m json.tool deploy/keycloak/realm-duke.json >/dev/null

verify: lint test policy-test config-check

compose-up:
	docker compose up --build -d

compose-down:
	docker compose down
