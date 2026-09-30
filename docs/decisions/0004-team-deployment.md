# 0004 — Team deployment (scaling stage 2)

- Task: 0.4
- Date: 2026-09-30
- Status: accepted (owner)

## Decision

Yes. A shared team deployment is planned.

## Consequences

- Task **3.20** (FastAPI service boundary around the pipeline, `app/api.py`) is in scope for phase 3. Its done-when check is: eval results through the API equal in-process results.
- Design phase 3 components so each request carries its own conversation state and holds a read-only snapshot connection per worker, as the spec's "Small team" stage says. The `SnapshotStore`, `LLMClient` and answer-cache interfaces must not assume a single process.
- Per 0001, use stays non-commercial and internal.
