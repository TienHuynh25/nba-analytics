# Task 0.8. Targets from the spec: refresh, eval, test, serve.
.PHONY: refresh backfill backfill-status eval test serve lint fmt typecheck check

UV ?= uv
AS_OF ?=
SNAPSHOT_ID ?=

refresh:
ifeq ($(AS_OF),)
	$(UV) run python -m ingest.refresh
else
	$(UV) run python -m ingest.refresh --as-of $(AS_OF) $(if $(SNAPSHOT_ID),--snapshot-id $(SNAPSHOT_ID))
endif

backfill:
	$(UV) run python -m ingest.backfill

backfill-status:
	$(UV) run python -m ingest.backfill --status

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
