# T-QA7 verification (DEF-028, 029, 030, 031)
Method: scratch trees under the session scratchpad (git archive HEAD; "oldcode" = same tree with app/sql_fallback.py from 16a5c0e). Real repo untouched (no git writes). Counting: `pytest -q -p no:cacheprovider -o addopts=''` summary line, `-m "not network"`.
- Logs: T-QA7-1 (old vs fixed, gc off, 6 seeds + direct mechanism), T-QA7-2 (8 real full runs + 100 isolated), T-QA7-3 (lint/type/gate2+eval_report tests), T-QA7-4 (dirty matrix + gate2 checker matrix).
- Old: regression test fails 6/6; flake leaks to other tests (target test 1/6, others seeds 3,4); direct repro 3/20 gc-off, 8/20 gc-on. Fixed: 0/6 (+0/40 direct).
- Real tree: 8/8 full runs 1237 passed, 2 skipped; 100/100 isolated.
- Scratch-only artifact: test_career_gaps::test_no_tracked_file_names_a_desktop_path fails in both scratch trees (no .git there); passes in the real tree.
