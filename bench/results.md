# breadcrumbs benchmark results

## REAL pilot run (subagent-runtime, N=1 per cell)

This is a **real, non-mock** result. Models were invoked via the Claude Agent
SDK subagent runtime (the Agent tool's `model` parameter set to `haiku` /
`sonnet` / `opus`), not via raw Anthropic Messages API calls — there was no
`ANTHROPIC_API_KEY` available in this environment to run `bench/run_bench.py`
for real. N=1 per (model, arm) cell, 6 cells total. Scoring is deterministic
(`bench/score_pilot.py`) against 8 fixed hard constraints (C1-C8) from a
single fixed payments-module scenario — see `bench/pilot_results.json` for
the full constraint list, raw model responses, and per-constraint
true/false breakdown.

| Model | Baseline % | Treatment % | Delta (pp) |
|---|---|---|---|
| Haiku 4.5 | 37.5 | 87.5 | +50.0 |
| Sonnet 4.6 | 25.0 | 87.5 | +62.5 |
| Opus 4.8 | 37.5 | 87.5 | +50.0 |

Mean across the 3 models: **33.3% → 87.5%** (delta +54.2pp).

Honest caveat: N=1 per cell means each number is a single sample, not a
distribution — there is no variance estimate and one unlucky/lucky
completion swings a whole cell by 12.5 percentage points. Treat this as
pilot-strength directional evidence, not a definitive result. Also note: in
every treatment cell here, all 3 models still missed C8 (reading
`APP_CONFIG` via `os.environ` directly inside `process_payment`) — they
called the existing `load_config()` helper instead, which is reasonable
code but doesn't satisfy the literal scoring check. That's a real, recorded
miss, not omitted to flatter the result.

## MOCK results (scripted/fake, zero evidentiary value, kept for reference only)

**These numbers below come from canned, scripted responses with zero
network access. They exercise the scoring pipeline only and say nothing
about real model behavior. Do not confuse this table with the real pilot
table above.**

K=8 constraints, N=5 repeats per condition.

| Model | Baseline retention | Treatment retention | Delta |
|---|---|---|---|
| claude-haiku-4-5-20251001 | 0.62 | 1.00 | +0.38 |
| claude-sonnet-4-6 | 0.62 | 1.00 | +0.38 |
| claude-opus-4-8 | 0.62 | 1.00 | +0.38 |
