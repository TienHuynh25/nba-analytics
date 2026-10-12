# T-SEC2 evidence
- checkout v4 -> commit 11d5960a326750d5838078e36cf38b85af677262 (lightweight tag); verified via repos/actions/checkout/commits/<sha>
- setup-uv v6 -> annotated tag d0d8abe... -> commit d0cc045d04ccac9d8b7881df0226f9e82c39688e; verified via repos/astral-sh/setup-uv/commits/<sha>
- ci.yml: permissions contents: read; persist-credentials: false; both actions pinned with tag comments
- dbt 1.12.5: `flags: send_anonymous_usage_stats: false` in dbt_project.yml; `dbt parse --profiles-dir .` succeeded (only pre-existing deprecation warnings). dev.duckdb mtime unchanged (Oct 11 22:53).
- yaml.safe_load(ci.yml) OK.
