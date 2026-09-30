# 0001 — NBA.com terms-of-use position

- Task: 0.1
- Date: 2026-09-30
- Status: accepted (owner)

## Decision

This project is for personal and research use only. It is not commercial.

## Consequences

- `nba_api` over stats.nba.com stays the primary source for v1, as the spec says.
- Nothing is redistributed. Raw JSON and snapshots stay under `data/`, which is git-ignored.
- A team deployment (0004) is internal, for the same non-commercial use. The spec's "Public app" scaling stage still needs a licensed NBA data feed, and it needs a new decision first.
