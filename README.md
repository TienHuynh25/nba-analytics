# NBA Analytics RAG

A fully local assistant that answers natural-language NBA questions with correct, cited numbers. NBA.com stats come through `nba_api` into DuckDB, and a small local LLM (Ollama / llama.cpp) runs the pipeline. Numbers come from code and words from the model: every number in an answer is checked by a numeric verifier against the query result. The release bar is at least 85% correct on the held-out split with zero unverified numbers.

## Architecture diagrams

- [System architecture (Figma board)](https://www.figma.com/board/aWEQ5Oc8WauiAaFaUK2ACB/NBA-Analytics-RAG---System-Architecture?node-id=0-1&p=f&t=lKtRkEuG6CXvZMZl-0)
- [System architecture (Figma board, second view)](https://www.figma.com/board/aWEQ5Oc8WauiAaFaUK2ACB/NBA-Analytics-RAG---System-Architecture?node-id=0-1&p=f&t=wc5NKPnPVkSNCNNd-0)

## Documents

- [Spec](Basketball%20Analytics%20RAG%20%E2%80%94%20Spec.md): what to build and why.
- [Execution Plan](Basketball%20Analytics%20RAG%20%E2%80%94%20Execution%20Plan.md): ordered tasks, gates 1 to 4, and spec gaps.
- [CLAUDE.md](CLAUDE.md): commands, invariants, architecture and the data pipeline as built.
- [docs/decisions/](docs/decisions/): recorded decisions (0001 to 0009).
- [ingest/ENDPOINTS.md](ingest/ENDPOINTS.md): what the NBA.com source data looks like.
- [eval/README.md](eval/README.md): the evaluation harness and the pinned snapshot.

## Getting started

Python 3.12 managed with `uv`. See [CLAUDE.md](CLAUDE.md) for the full command list (`uv sync`, `make check`, `make test`, `make backfill`, `make refresh`, `make eval`, `make serve`).
