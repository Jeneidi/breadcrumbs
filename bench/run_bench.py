#!/usr/bin/env python3
"""
breadcrumbs benchmark: does a checkpoint-seeded context (TREATMENT) survive
into a model's final answer better than a naive "summarize the conversation"
context (BASELINE)?

This does NOT measure live in-harness Claude Code compaction (not
independently scriptable). It measures the underlying strategy — feeding a
model a checkpoint block vs. a generic summary — via direct Messages API
calls. See README for the full caveat.

Stdlib only (+ urllib for HTTP). No third-party deps.
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.error

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
MODELS = ["claude-haiku-4-5-20251001", "claude-sonnet-4-6", "claude-opus-4-8"]

# Rough order-of-magnitude per-call cost estimate for the cost note only.
# Not a billing guarantee — short prompts, cheapest tier assumed as floor.
ROUGH_COST_PER_CALL_USD = 0.01


def build_synthetic_fixture(k):
    """Synthetic fixture data — not real project content. K constraints."""
    constraints = [
        "the API key env var is named BREADCRUMBS_API_KEY",
        "never touch the file legacy/do_not_edit.py",
        "the deploy target region is eu-west-2",
        "the database migration tool is alembic, not raw SQL",
        "all timestamps must be stored in UTC",
        "the staging branch is named release/staging, not develop",
        "rate limit is capped at 50 requests per minute",
        "the only supported Python version is 3.11",
        "logs must be written to /var/log/app, never stdout in prod",
        "the feature flag service is LaunchDarkly, not a custom one",
        "test coverage must stay above 80 percent",
        "the primary contact for infra approvals is the on-call SRE",
    ]
    if k > len(constraints):
        raise ValueError(f"k={k} exceeds available fixture constraints ({len(constraints)})")
    return constraints[:k]


def build_conversation(constraints):
    """A synthetic long conversation embedding the constraints, clearly
    labeled as fixture data."""
    lines = [
        "[SYNTHETIC FIXTURE CONVERSATION - not a real project]",
        "User: We're starting a new task. Here are the ground rules.",
    ]
    for c in constraints:
        lines.append(f"User: Constraint - {c}.")
        lines.append("Assistant: Understood, noted.")
    lines.append("User: Now let's do a bunch of unrelated busywork to pad the context...")
    lines.append("Assistant: (long synthetic mid-task back-and-forth omitted for brevity)")
    return "\n".join(lines)


def build_baseline_context(conversation, summarizer):
    """Generic 'please summarize this conversation' context."""
    summary = summarizer(conversation)
    return summary


def build_treatment_context(conversation, constraints, summarizer):
    """Same generic summary PLUS a breadcrumbs-style checkpoint block."""
    summary = summarizer(conversation)
    checkpoint = ["## Hard Constraints"]
    checkpoint += [f"- {c}" for c in constraints]
    return summary + "\n\n" + "\n".join(checkpoint)


TASK_PROMPT = (
    "Based on the context above, list every constraint that was established "
    "for this task. Be specific and complete."
)


def score_retention(answer_text, constraints):
    """How many of the K constraints appear correctly reflected in the
    answer. Crude substring/keyword check - good enough for a relative
    comparison between baseline and treatment, not a claim of NLU."""
    hits = 0
    for c in constraints:
        # Use a few distinguishing keywords from each constraint rather than
        # the full string, since a model may paraphrase.
        keywords = [w.strip(".,") for w in c.split() if len(w) > 4]
        keywords = keywords[:3] if keywords else [c]
        if any(kw.lower() in answer_text.lower() for kw in keywords):
            hits += 1
    return hits


# --- Mock mode -------------------------------------------------------------

def mock_summarizer(conversation):
    return "[MOCK] Generic summary: discussed a task with several setup constraints."


def mock_call_model(model, context, constraints, condition):
    """Deterministic canned responses. ZERO network access. Treatment canned
    response correctly cites all K constraints; baseline canned response
    only cites about half - these are FAKE/SCRIPTED and carry zero
    evidentiary value about real model behavior."""
    if condition == "treatment":
        body = "[MOCK SCRIPTED RESPONSE] Constraints: " + "; ".join(constraints)
    else:
        half = constraints[: max(1, len(constraints) // 2)]
        body = "[MOCK SCRIPTED RESPONSE] Constraints (partial recall): " + "; ".join(half)
    return body


# --- Real mode --------------------------------------------------------------

def real_call_model(model, context, task_prompt, api_key):
    body = json.dumps({
        "model": model,
        "max_tokens": 512,
        "messages": [
            {"role": "user", "content": context + "\n\n" + task_prompt},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data.get("content", [])
    return "".join(p.get("text", "") for p in parts if p.get("type") == "text")


def real_summarizer(conversation, api_key, model):
    return real_call_model(
        model, conversation, "Please summarize this conversation concisely.", api_key
    )


# --- Main run ----------------------------------------------------------------

def run(args):
    mock = args.mock
    k = args.k
    n = args.n

    if not mock and not os.environ.get("ANTHROPIC_API_KEY"):
        print(
            "ERROR: ANTHROPIC_API_KEY is not set. Set it, or pass --mock to "
            "run the full pipeline with zero network access and canned "
            "responses.",
            file=sys.stderr,
        )
        sys.exit(1)

    constraints = build_synthetic_fixture(k)
    conversation = build_conversation(constraints)

    if mock:
        print("=== MOCK MODE: zero network access, all responses are scripted/fake ===")
    else:
        total_calls = len(MODELS) * 2 * n
        est = total_calls * ROUGH_COST_PER_CALL_USD
        print(f"=== REAL MODE: about to make {total_calls} live API calls ===")
        print(f"Rough order-of-magnitude estimated cost: ~${est:.2f} USD (not a guarantee)")

    results = {
        "mode": "mock" if mock else "real",
        "k": k,
        "n": n,
        "constraints": constraints,
        "models": {},
    }

    for model in MODELS:
        print(f"\n--- model: {model} ---")
        baseline_rates = []
        treatment_rates = []

        for i in range(n):
            if mock:
                summarizer = mock_summarizer
                baseline_ctx = build_baseline_context(conversation, summarizer)
                treatment_ctx = build_treatment_context(conversation, constraints, summarizer)

                baseline_answer = mock_call_model(model, baseline_ctx, constraints, "baseline")
                treatment_answer = mock_call_model(model, treatment_ctx, constraints, "treatment")
            else:
                api_key = os.environ["ANTHROPIC_API_KEY"]
                summarizer = lambda conv: real_summarizer(conv, api_key, model)
                baseline_ctx = build_baseline_context(conversation, summarizer)
                treatment_ctx = build_treatment_context(conversation, constraints, summarizer)

                baseline_answer = real_call_model(model, baseline_ctx, TASK_PROMPT, api_key)
                treatment_answer = real_call_model(model, treatment_ctx, TASK_PROMPT, api_key)

            b_hits = score_retention(baseline_answer, constraints)
            t_hits = score_retention(treatment_answer, constraints)
            baseline_rates.append(b_hits / k)
            treatment_rates.append(t_hits / k)

            label = "MOCK" if mock else "REAL"
            print(f"[{label}] run {i+1}/{n}: baseline={b_hits}/{k}  treatment={t_hits}/{k}")

        b_avg = sum(baseline_rates) / n
        t_avg = sum(treatment_rates) / n
        results["models"][model] = {
            "baseline_retention_rate": b_avg,
            "treatment_retention_rate": t_avg,
            "delta": t_avg - b_avg,
            "baseline_runs": baseline_rates,
            "treatment_runs": treatment_rates,
        }

    out_dir = os.path.dirname(os.path.abspath(__file__))
    results_json_path = os.path.join(out_dir, "results.json")
    results_md_path = os.path.join(out_dir, "results.md")

    with open(results_json_path, "w") as f:
        json.dump(results, f, indent=2)

    write_results_md(results, results_md_path)

    print(f"\nWrote {results_json_path}")
    print(f"Wrote {results_md_path}")


def write_results_md(results, path):
    mode = results["mode"]
    heading = "MOCK RESULTS (scripted/fake, zero evidentiary value)" if mode == "mock" else "REAL RESULTS"
    lines = [f"# breadcrumbs benchmark results — {heading}", ""]
    if mode == "mock":
        lines.append(
            "**These numbers come from canned, scripted responses with zero "
            "network access. They exercise the scoring pipeline only and say "
            "nothing about real model behavior.**"
        )
    else:
        lines.append("Live API results. See methodology caveats in the README.")
    lines.append("")
    lines.append(f"K={results['k']} constraints, N={results['n']} repeats per condition.")
    lines.append("")
    lines.append("| Model | Baseline retention | Treatment retention | Delta |")
    lines.append("|---|---|---|---|")
    for model, r in results["models"].items():
        lines.append(
            f"| {model} | {r['baseline_retention_rate']:.2f} | "
            f"{r['treatment_retention_rate']:.2f} | {r['delta']:+.2f} |"
        )
    lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="breadcrumbs compaction-strategy benchmark")
    parser.add_argument("--k", type=int, default=8, help="number of constraints (default 8)")
    parser.add_argument("--n", type=int, default=5, help="repeats per condition (default 5)")
    parser.add_argument("--mock", action="store_true", help="run with zero network access, canned responses")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
