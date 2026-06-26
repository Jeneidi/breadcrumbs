# breadcrumbs

A Claude Code plugin that keeps a structured checkpoint of task-critical state and re-injects it right after context compaction, so auto-compaction never silently drops decisions or constraints.

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

TBD — pending real API run

## Compatibility

The plugin manifest and hooks schema in this repo were verified against the official docs:

- https://code.claude.com/docs/en/plugins-reference
- https://code.claude.com/docs/en/hooks

## License

MIT — see [LICENSE](LICENSE).
