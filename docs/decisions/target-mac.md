# Target Mac

- Task: 0.2
- Date: 2026-09-30
- Status: accepted (owner)

## Decision

The target machine is an **Apple M1 Pro with 16 GB of unified memory**, the development machine this repo lives on.

## Model size ceiling

On a 16 GB Apple Silicon Mac, Metal can use about two thirds of RAM by default, about 10.5 GB. The resident models must fit inside that and leave room for DuckDB and the OS.

| Component | Budget |
| --- | --- |
| Instruct LLM (Q4 quant) | ≤ 9B parameters, about 6.5 GB (for example `qwen3.5:9b`, already pulled) |
| `bge-m3` embeddings | about 1.2 GB |
| `bge-reranker-v2-m3` | about 1.1 GB |
| DuckDB working memory | capped at 2 GB (`memory_limit`) for the app connection |

Models larger than 9B, or a second LLM loaded next to the main one, are out of budget. The spec's risk mitigation "send the SQL fallback to a larger local model" is therefore limited to at most about 14B at Q4, loaded on demand (not resident with the main model).

## Latency budgets

The spec's per-path p95 budgets stay as written: typed tool ≤ 3 s, SQL fallback ≤ 6 s, RAG ≤ 4 s, mixed ≤ 10 s. They are measured on this machine in task 4.11. The model benchmark (3.17) runs here and records latency next to accuracy.
