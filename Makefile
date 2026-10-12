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

# Eval harness (tasks 2.15-2.19): dev split, temperature 0, cache off. SPLIT=heldout only at gates.
SPLIT ?= dev
ANSWERER ?= stub
eval:
	$(UV) run pytest eval/harness -q -p no:cacheprovider --split $(SPLIT) --answerer $(ANSWERER) $(if $(ACCEPT),--accept)

# Local assistant (task 4.10). DB=<snapshot .duckdb> to use a file instead of current.
serve:
	$(UV) run python -m app.cli $(if $(DB),--db $(DB)) $(if $(SHOTS),--shots $(SHOTS))

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
