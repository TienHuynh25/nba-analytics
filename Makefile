# Task 0.8. Targets from the spec: refresh, eval, test, serve.
.PHONY: refresh eval test serve lint fmt typecheck check

UV ?= uv
AS_OF ?=

refresh:
	@echo "refresh: not implemented yet (task 1.26)"; exit 0

eval:
	@echo "eval: not implemented yet (task 2.15)"; exit 0

serve:
	@echo "serve: not implemented yet (task 4.10)"; exit 0

test:
	$(UV) run pytest -m "not network"

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

fmt:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck:
	$(UV) run mypy

check: lint typecheck test
