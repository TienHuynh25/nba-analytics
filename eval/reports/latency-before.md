# Stats-path latency: before

51 dev-split stats seeds, model qwen3.5:9b, one warm-up first.

| Step | n | p50 s | p95 s | max s |
| --- | --- | --- | --- | --- |
| whole answer | 51 | 8.29 | 21.34 | 25.58 |
| tool-choice call | 56 | 4.90 | 7.02 | 10.65 |
| answer-writing call | 54 | 3.46 | 10.32 | 15.36 |

Budget (spec): typed tool path p95 <= 3 s on the target Mac.
