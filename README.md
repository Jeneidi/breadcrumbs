<div align="center">

# breadcrumbs

### _Claude forgets. breadcrumbs remembers._

Drop a trail through your task. When /compact eats the forest, you still know the way back.

[![GitHub stars](https://img.shields.io/github/stars/Jeneidi/breadcrumbs?style=flat-square&color=111111&label=stars)](https://github.com/Jeneidi/breadcrumbs/stargazers)
[![License: MIT](https://img.shields.io/badge/license-MIT-111111?style=flat-square)](LICENSE)
[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-111111?style=flat-square)](https://github.com/Jeneidi/breadcrumbs)
[![hooks](https://img.shields.io/badge/hooks-Stop%20%C2%B7%20PreCompact%20%C2%B7%20PostCompact-111111?style=flat-square)](#how-it-works)

**task-state retention: 33.3% → 87.5% across Haiku 4.5 · Sonnet 4.6 · Opus 4.8** · _real pilot run, N=1/cell_

_Pilot run (N=1 per model x arm, 6 cells) measuring how much task-critical state survives a forced compaction: checkpoint-seeded context (treatment) vs. naive summary (baseline). Models were invoked via the Claude Agent SDK subagent runtime (the Agent tool's `model` parameter), NOT raw Anthropic Messages API calls — there's no `ANTHROPIC_API_KEY` in this environment. Scoring is deterministic against 8 fixed hard constraints. A full run via the existing harness (`bench/run_bench.py`) against the real Messages API, with N>1 for variance, would be a stronger follow-up. Treat this as directional pilot evidence, not definitive proof — see the honest caveats in the [benchmark](#benchmark) section._

</div>

## The problem

Claude Code's auto-compaction fires when a session approaches its context limit. It's a well-known, frequently-raised complaint that compaction can be lossy — it fires under token pressure, often mid-task, and can silently drop decisions, constraints, or state that mattered. There's no generic way to guarantee a given fact survives a generic summarization pass.

breadcrumbs doesn't try to make compaction itself smarter. Instead it keeps a small, separate, always-current checkpoint of the things that actually matter, outside the part of history that gets summarized — and puts it back in front of the model the moment compaction finishes.

## How it works

- **Skill** (`skills/breadcrumbs/SKILL.md`) — instructs Claude to maintain `.breadcrumbs/checkpoint.md` at the end of every clean step: Active Task, Decisions (with why), Files Touched, Open TODOs, Hard Constraints. It's a living document that gets edited in place, not a growing log.
- **Stop hook** (`hooks/on_stop.sh`) — on every Stop, checks whether the checkpoint is missing or stale (older than the transcript). If so, reminds Claude to update it. Never blocks stopping.
- **PreCompact hook** (`hooks/on_precompact.sh`) — just before compaction, copies the live checkpoint to `.breadcrumbs/last_precompact_snapshot.md` as a durable safety net. Never blocks compaction.
- **PostCompact hook** (`hooks/on_postcompact.sh`) — right after compaction completes, reads the checkpoint (falling back to the pre-compact snapshot) and re-injects it verbatim as `additionalContext`.

```
 task work ──► Stop (reminds if stale) ──► checkpoint.md kept current
                                                  │
                                     compaction triggered
                                                  │
                                          PreCompact (snapshot only)
                                                  │
                                            [ compaction happens ]
                                                  │
                                          PostCompact (re-injects checkpoint)
```

### Architecture note: why three hooks, not two

It's tempting to assume PreCompact could both snapshot *and* inject the checkpoint into the compacted summary in one step. It can't. Per the official docs, PreCompact's output schema only supports `decision`/`reason` (to optionally block compaction) plus universal fields — there is no `additionalContext` field on PreCompact. It cannot influence what the summary contains. So the two hooks are not redundant: PreCompact's only honest job is taking a safety-net snapshot before history is replaced; PostCompact is the one that actually re-injects the checkpoint, because it fires after the summary already exists and `additionalContext` is supported there.

## Install

### As a plugin (local dev)

```bash
claude --plugin-dir /path/to/breadcrumbs
```

### As a plugin (via marketplace)

This repo is also a single-plugin marketplace (`.claude-plugin/marketplace.json` at the repo root, sibling to the plugin's own `.claude-plugin/plugin.json`). Once published:

```
/plugin marketplace add Jeneidi/breadcrumbs
/plugin install breadcrumbs@breadcrumbs
```

### Manual install (no plugin system)

1. Copy `skills/breadcrumbs/` to `~/.claude/skills/breadcrumbs/`.
2. Merge the contents of `hooks/hooks.json` into your own `~/.claude/settings.json` under `"hooks"`.
3. `${CLAUDE_PLUGIN_ROOT}` only resolves inside a plugin context — outside of it, replace each hook's `command` with the absolute path to the script, e.g. `/Users/you/.claude/skills/breadcrumbs/hooks/on_stop.sh` (wherever you copied the `hooks/` scripts to).

## Tests

```bash
make test
# or: bash tests/run.sh
```

Plain bash + python3 stdlib asserts against temp directories — no test framework. Covers: PreCompact snapshotting, PostCompact re-injection, and the Stop hook's stale/fresh checkpoint detection.

## Benchmark

`bench/run_bench.py` (stdlib + `urllib` only) asks: does seeding context with a breadcrumbs-style checkpoint (TREATMENT) preserve task-critical constraints better than a generic "summarize this conversation" pass (BASELINE)?

- A synthetic fixture conversation embeds K constraints (default 8).
- BASELINE context = a generic summary of that conversation.
- TREATMENT context = the same summary plus a `## Hard Constraints` checkpoint block listing the K constraints, simulating what the skill + hooks would have produced.
- Each of 3 models (`claude-haiku-4-5-20251001`, `claude-sonnet-4-6`, `claude-opus-4-8`) is asked a final task prompt under both conditions, N times (default 5). Scoring: what fraction of the K constraints show up in the answer.

```bash
python3 bench/run_bench.py --mock   # zero network access, canned/fake responses, exercises the pipeline only
python3 bench/run_bench.py          # real run, requires ANTHROPIC_API_KEY
```

Outputs `bench/results.json` (raw, includes top-level `"mode": "mock"|"real"`) and `bench/results.md` (per-model table).

**Honest limitation:** this benchmark measures the *compaction strategy* — checkpoint-seeded vs. naive-summary context — via direct Messages API calls that simulate what compaction produces. It does **not** measure live in-harness Claude Code compaction behavior, which isn't independently scriptable from the outside. Treat results as evidence about the strategy, not a measurement of the shipped hooks running inside a real session.

### Results

**Real pilot run** (not mock) via the Claude Agent SDK subagent runtime — see [`bench/results.md`](bench/results.md) and [`bench/pilot_results.json`](bench/pilot_results.json) for full detail, raw model outputs, and per-constraint breakdown. N=1 per (model, arm) cell, 6 cells total, scored deterministically against 8 fixed hard constraints in a fixed payments-module scenario.

| Model | Baseline % | Treatment % | Delta (pp) |
|---|---|---|---|
| Haiku 4.5 | 37.5 | 87.5 | +50.0 |
| Sonnet 4.6 | 25.0 | 87.5 | +62.5 |
| Opus 4.8 | 37.5 | 87.5 | +50.0 |

Mean across the 3 models: 33.3% → 87.5% (+54.2pp).

This is a pilot, not a definitive benchmark: N=1 per cell has no variance estimate, and a single completion can swing a cell by 12.5pp. The direction is consistently positive across all three models in this pilot, but the magnitude should not be over-read. Notably, even in the treatment arm, all 3 models missed constraint C8 (reading `APP_CONFIG` directly via `os.environ` inside `process_payment`) — they delegated to the existing `load_config()` helper instead, which is reasonable code but didn't satisfy the literal check. That miss is reported as-is, not smoothed over. The mock numbers that previously lived in `bench/results.md` are scripted/fake and are kept there only for reference, clearly labeled — they are not real evidence and were not used to produce any number on this page.

## Compatibility

The plugin manifest and hooks schema in this repo were verified against the official docs:

- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/hooks

## License

MIT — see [LICENSE](LICENSE).
