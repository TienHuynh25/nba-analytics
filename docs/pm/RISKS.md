# Risks and assumptions

| ID | Item | Owner | Status |
|---|---|---|---|
| A-001 | Phase 1 code accepted as built; Gate 1 work is verification plus finishing the backfill | PM | open |
| A-002 | Phase 2 authoring may run in parallel with Gate 1 close-out | PM | open |
| R-001 | The nightly anomaly check is a pure ±10% rule (matches spec/config `row_count_tolerance`), so one missing game on a big slate (up to 1 of 10) can pass. Not a bug. Question for owner: add an absolute floor? Not added: no scope beyond the spec. | user | open |
| A-003 | NBA.com schedule uses gameStatus 3 for final games and MM/DD/YYYY dates; confirmed on the cached 2025-26 schedule only | PM | open |
| R-002 (mitigated: shebangs, imports and stale .pyc fixed by T-ENV; test evidence taken before T-ENV is superseded) | The venv was likely created at `/Users/tienhuynh/Desktop/nba-analytics`; an editable install may import `app`/`ingest` from that second checkout, so any test run so far may have exercised the wrong code. All earlier test evidence is provisional until T-ENV and T-QA1 re-run. | PM | open |
| R-003 | Q48-v1 ("Dubs") gold `entities` empty (team only in `tool_call.args`). Gold values are all `None` until T-2.6; resolve there, not now | PM | open |
| R-004 | Plan file names `ingest/publish.py` and `ingest/rollback.py` (plan:109-110) do not exist; code is in `ingest/snapshots.py` (open_current :305, health_check :224, point_current :257, publish :284, prune :293). Recorded divergence; user to choose: update plan or split code. PM recommends updating the plan (no behavior change). | user | open |
| R-005 | First reader open after process start or swap now hashes the snapshot (~0.5 s/GB warm cache, measured on 200 MB dev build only). Re-measure on the full-history snapshot after the backfill | PM | open |
| R-006 | `pyproject.toml` addopts `-q` plus CLI `-q` hides pytest's summary line; use `-rA` or drop one `-q` when reading counts | PM | open |
