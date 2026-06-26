#!/usr/bin/env python3
"""Deterministic scorer for the breadcrumbs subagent pilot (N=1 per cell).

Extracts the python code block from each raw response and checks it against
the 8 fixed hard constraints (C1-C8) from the payments-module scenario.
Writes bench/pilot_results.json. Stdlib only.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, "/private/tmp/claude-501/-Users-jeneidi-Desktop-Projects/01e5535c-152d-4ce2-a5d9-dfbc5573a62a/scratchpad/breadcrumbs_pilot")
from contexts import NAIVE_BASELINE_SUMMARY, TREATMENT_CHECKPOINT_BLOCK, TASK_INSTRUCTION
import raw_responses as R

REPO = Path("/Users/jeneidi/Desktop/Projects/breadcrumbs")

BLOCKED_IMPORTS = ["requests", "boto3", "numpy", "pandas", "flask", "django",
                   "pydantic", "sqlalchemy", "aiohttp", "httpx"]


def extract_code(raw: str) -> str:
    """Pull the first ```python ... ``` block out of a raw response."""
    m = re.search(r"```python\s*\n(.*?)```", raw, re.DOTALL)
    if m:
        return m.group(1)
    m = re.search(r"```\s*\n(.*?)```", raw, re.DOTALL)
    return m.group(1) if m else raw


def score(code: str) -> dict:
    checks = {}
    checks["C1_snake_case"] = (
        "def process_payment(" in code
        and re.search(r"def [a-z]+[A-Z]", code) is None
    )
    checks["C2_decimal_no_float"] = ("Decimal" in code) and ("float(" not in code)
    checks["C3_utc"] = "utc" in code.lower()
    checks["C4_stdlib_only"] = not any(
        re.search(rf"^\s*(import {b}|from {b})", code, re.MULTILINE)
        for b in BLOCKED_IMPORTS
    )
    sig_match = re.search(r"def process_payment\((.*?)\)\s*(->.*?)?:", code, re.DOTALL)
    sig_span = code[sig_match.start():sig_match.end()] if sig_match else ""
    # approximate full signature region (handles multi-line defs) by grabbing
    # from "def process_payment(" up to the first "):" inclusive of any "->"
    def_start = code.find("def process_payment(")
    sig_region = ""
    if def_start != -1:
        close = code.find("):", def_start)
        if close == -1:
            close = code.find(") ->", def_start)
        sig_region = code[def_start: close + 2] if close != -1 else code[def_start:def_start + 200]
    checks["C5_type_hints"] = ("->" in sig_region) and (": " in sig_region)
    checks["C6_docstring"] = '"""' in code or "'''" in code
    checks["C7_err_prefix"] = "ERR:" in code
    checks["C8_app_config_env"] = ("APP_CONFIG" in code) and (
        "os.environ" in code or "getenv" in code
    )
    satisfied = sum(checks.values())
    return {
        "checks": checks,
        "score": satisfied,
        "max_score": 8,
        "pct": round(satisfied / 8 * 100, 1),
    }


CELLS = {
    ("haiku", "baseline"): R.HAIKU_BASELINE_RAW,
    ("haiku", "treatment"): R.HAIKU_TREATMENT_RAW,
    ("sonnet", "baseline"): R.SONNET_BASELINE_RAW,
    ("sonnet", "treatment"): R.SONNET_TREATMENT_RAW,
    ("opus", "baseline"): R.OPUS_BASELINE_RAW,
    ("opus", "treatment"): R.OPUS_TREATMENT_RAW,
}

MODEL_LABELS = {
    "haiku": "Haiku 4.5",
    "sonnet": "Sonnet 4.6",
    "opus": "Opus 4.8",
}


def main():
    results = {
        "mode": "pilot-subagent",
        "note": (
            "Real pilot run via the Claude Agent SDK subagent runtime (Agent tool, "
            "model param set to haiku/sonnet/opus), NOT raw Anthropic Messages API "
            "calls. N=1 per cell (6 cells total: 3 models x 2 arms). Scoring is "
            "deterministic, computed by this script against the 8 fixed hard "
            "constraints below."
        ),
        "n_per_cell": 1,
        "constraints": [
            "C1: all function names in snake_case",
            "C2: all monetary amounts use decimal.Decimal, never float",
            "C3: datetimes must be timezone-aware UTC (datetime.now(timezone.utc))",
            "C4: standard library only, no third-party imports",
            "C5: type hints on all params and return",
            "C6: docstring on every public function",
            "C7: raised error messages prefixed with \"ERR: \"",
            "C8: configuration read from env var APP_CONFIG via os.environ (never hardcoded/from file)",
        ],
        "naive_baseline_summary": NAIVE_BASELINE_SUMMARY,
        "treatment_checkpoint_block": TREATMENT_CHECKPOINT_BLOCK,
        "task_instruction": TASK_INSTRUCTION,
        "runs": {},
        "model_aggregates": {},
        "failed_cells": [],
    }

    per_model = {}
    for (model, arm), raw in CELLS.items():
        code = extract_code(raw)
        s = score(code)
        key = f"{model}_{arm}"
        results["runs"][key] = {
            "model": model,
            "model_label": MODEL_LABELS[model],
            "arm": arm,
            "rep": 1,
            "status": "ok",
            "raw_response": raw,
            "extracted_code": code,
            "constraint_checks": s["checks"],
            "score": s["score"],
            "max_score": s["max_score"],
            "retention_pct": s["pct"],
        }
        per_model.setdefault(model, {})[arm] = s["pct"]

    for model, arms in per_model.items():
        b = arms.get("baseline", 0.0)
        t = arms.get("treatment", 0.0)
        results["model_aggregates"][model] = {
            "model_label": MODEL_LABELS[model],
            "mean_baseline_pct": b,
            "mean_treatment_pct": t,
            "delta_pp": round(t - b, 1),
        }

    mean_baseline = round(
        sum(v["mean_baseline_pct"] for v in results["model_aggregates"].values())
        / len(results["model_aggregates"]),
        1,
    )
    mean_treatment = round(
        sum(v["mean_treatment_pct"] for v in results["model_aggregates"].values())
        / len(results["model_aggregates"]),
        1,
    )
    results["overall"] = {
        "mean_baseline_pct": mean_baseline,
        "mean_treatment_pct": mean_treatment,
        "delta_pp": round(mean_treatment - mean_baseline, 1),
    }

    out_path = REPO / "bench" / "pilot_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out_path}")
    print(json.dumps(results["model_aggregates"], indent=2))
    print(json.dumps(results["overall"], indent=2))


if __name__ == "__main__":
    main()
