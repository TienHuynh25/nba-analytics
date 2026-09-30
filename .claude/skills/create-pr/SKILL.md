---
name: create-pr
description: Package uncommitted changes into separate PRs, one per logical chunk, each on its own branch with a what/why/risk/test summary, pasted test output, pushed and opened with gh.
disable-model-invocation: true
---

# /create-pr

Package the uncommitted changes in the working tree into separate PRs.

## Preconditions (check first, stop and report if any fail)

- `git rev-parse --is-inside-work-tree` succeeds. If not, say so; do not `git init` unless asked.
- `git status --short` shows changes. If empty, say so and stop.
- `git remote get-url origin` exists and `gh auth status` is logged in.
- Note the base branch (default branch of origin). Never commit to it directly.

## Steps

1. **Split into chunks.** Read `git status` and `git diff`. Group changes by logical purpose (one feature, fix, or doc/config change per chunk). Files in the same chunk must be reviewable together. List the proposed chunks (files + one line each) and confirm with the user if the grouping is ambiguous. If a single file mixes chunks, use `git add -p` equivalents; say so.
2. **Per chunk**, starting from the base branch each time:
   1. **Branch:** `git switch -c <type>/<short-slug>` from the base, then stage only that chunk's files. Carry other chunks' changes along (e.g. `git stash` and pop selectively) so nothing is lost.
   2. **Commit:** a short imperative message. Include the task ID from the execution plan when the chunk maps to one (e.g. `1.5`). End with the attribution line from the session's system-reminder.
   3. **Test evidence:** run the project's tests (`make test`, or the narrowest relevant command; also `uv run ruff check .` and `uv run mypy .` if they exist). Capture the real output. If tests fail or no tests exist yet, say so plainly in the PR; never invent output.
   4. **PR body**, in this format:
      ```
      ## What
      <the change, 1-3 bullets>
      ## Why
      <motivation; cite spec/plan task ID if any>
      ## Risk
      <what could break, blast radius, rollback; "low" only with a reason>
      ## Test
      <command(s) run>
      <details><summary>Test output</summary>

      ```
      <pasted output, trimmed to the summary and any failures>
      ```
      </details>
      ```
      End with: `🤖 Generated with [Claude Code](https://claude.com/claude-code)`
   5. **Push and open:** `git push -u origin <branch>` then `gh pr create --base <base> --head <branch> --title "<title>" --body-file <file>`. Write the body file in the scratchpad directory.
3. **Finish:** return to the base branch and print a table of branch, PR URL, and test result per chunk. Confirm the working tree has no leftover changes.

## Rules

- Pushing and opening PRs is outward-facing: if the user has not clearly asked for it in this invocation, show the chunk plan and PR bodies first and ask before pushing.
- Never force-push, never amend published commits, never skip hooks.
- Do not include secrets, `data/` contents, or `.env` files; flag them instead.
- Keep chunks independent. If chunk B depends on chunk A, base B on A's branch and say so in the PR.
