# PM-led Claude Code team (v2, token-optimized)

One session, the PM, runs a team of specialist subagents. You only talk to the PM.

## Files

```
CLAUDE.md                            PM role, formats, model routing, token rules, gates
.claude/settings.json                Default model/effort, concurrency cap, deny rules
.claude/agents/architect.md          opus / high
.claude/agents/developer.md          sonnet / medium
.claude/agents/qa-tester.md          sonnet / medium
.claude/agents/devops.md             sonnet / medium
.claude/agents/security-reviewer.md  sonnet / high
.claude/agents/governance.md         sonnet / medium
```

## Setup

1. Copy `CLAUDE.md` and `.claude/` into your repo root. If you already have a `CLAUDE.md`, keep this one and move your project notes into `docs/pm/PROJECT.md` after intake.
2. Start Claude Code in the repo. Run `/agents` to confirm six agents, and `/status` to confirm settings loaded.
3. Paste the kickoff prompt.

## Kickoff prompt

```
You are the PM. Follow CLAUDE.md.

Brief: <what to build, for whom, why>
Constraints: <stack, deadline, compliance, anything fixed>
Tier guess: <Lite | Standard | Full, or "you decide">

Start Phase 0. Ask your intake questions, then draft docs/pm/PROJECT.md for my approval. Delegate nothing until I reply "approve".
```

## What changed from v1, and why

| Change | Effect |
|---|---|
| Agents set `omitClaudeMd: true` | v1 agents loaded the PM's whole CLAUDE.md on every spawn. That cost tokens each time and told them they were the PM. |
| Protocol embedded per agent; `PROTOCOL.md` removed | Each agent carries only the formats it uses. No extra file read per spawn. |
| `COMPLEXITY: L/M/H` on every TASK | PM routes L work to haiku and H work to opus per call. Most work stays on sonnet. |
| `effort` and `maxTurns` per agent | Caps thinking and runaway loops on routine roles. |
| Rework by resuming the same agent with a short `REWORK` message | The agent keeps its context instead of re-reading every file. Second rework goes to a fresh agent one model up. |
| Evidence logs go to `docs/pm/evidence/`, REPORTs quote ≤10 lines per command, ≤350 words | Keeps the PM's context small. Full logs stay on disk for governance spot checks. |
| PM never reads code; asks the built-in `Explore` agent (haiku) instead | The PM's context is the one that grows all project long. |
| TASKs point to files instead of pasting content | TASKs stay under 250 words. |
| Process tiers: Lite / Standard / Full | Small jobs skip per-phase security and governance passes. |
| Batch reviews | QA and security review a build batch, not each task (except Full tier). |
| Gate checkpoints | After each gate, `/clear` and say `resume`. The state files carry everything forward. |
| Static CLAUDE.md, state in `docs/pm/` | Keeps the prompt cacheable across turns. |
| Minimal tool lists; reviewers read-only | Smaller tool definitions per agent; reviewers can't edit by accident. |
| `settings.json` deny rules | Blocks force-push, hard reset, `rm -rf`, and reading `.env` at the tool level, not just by instruction. |

## Model guide

| Where | Default | Switch when |
|---|---|---|
| PM (main session) | sonnet / medium | `/model opus` for intake and for any replanning after an escalation, then switch back. |
| architect | opus / high | Lite tier: the PM can pass sonnet. |
| developer, devops, qa-tester | sonnet / medium | PM passes haiku for L tasks, opus for H tasks or the second rework. |
| security-reviewer | sonnet / high | PM passes opus in Full tier or for auth, payment, or PII code. |
| governance | sonnet / medium | Rarely needs more; it's checklist and spot-check work. |
| Explore (built-in) | haiku | Never. |

To force one model on every agent for a cheap run: set `CLAUDE_CODE_SUBAGENT_MODEL=haiku` and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`. That overrides all per-agent and per-call choices, so use it only for trial runs.

## Your habits that save the most

1. Answer intake thoroughly once. Vague charters cause rework, and rework is the biggest cost.
2. `/clear` + `resume` at every gate checkpoint.
3. Use `status` instead of asking open questions like "how's it going?"
4. Pick the lowest tier that fits. Lite is fine for scripts and internal tools.
5. Disconnect MCP servers you don't need for the project; their tool definitions load into every turn of the PM.
6. Run `/cost` (or `/usage`) after each gate to see where tokens went.

## Commands

| You say | PM does |
|---|---|
| `approve` | Passes G0 (or G1 in Lite) |
| `release` | Passes G4 after governance APPROVE |
| `status` | Sends a USER UPDATE |
| `resume` | Reloads from `docs/pm/` and continues |
| `show board` / `risks` / `defects` / `decisions` | Prints that file |
| `accept DEF-###` | Accepts an S3/S4 defect without fix |
| `option A` / `option B` | Answers an escalation |
| `pause` | Stops new delegation |

## Notes

- `effort`, `omitClaudeMd`, and per-call `effort` need a recent Claude Code version. Older versions silently ignore unknown frontmatter fields, so nothing breaks; you just lose that saving. Update with `claude update`.
- The deny rules are a floor, not a full sandbox. Add your project's own dangerous commands (e.g. `Bash(terraform destroy *)`, `Bash(dbt run --target prod *)`).
- For data projects, the QA agent already includes reconciliation, idempotent re-run, and schema-drift checks.
