# Stats-path latency: shared-conversation

51 dev-split stats seeds, model qwen3.5:9b, one warm-up first.

| Step | n | p50 s | p95 s | max s |
| --- | --- | --- | --- | --- |
| whole answer | 51 | 8.91 | 26.33 | 36.57 |
| tool-choice call | 56 | 4.99 | 7.19 | 8.64 |
| answer-writing call | 57 | 3.66 | 13.26 | 16.73 |

Budget (spec): typed tool path p95 <= 3 s on the target Mac.
