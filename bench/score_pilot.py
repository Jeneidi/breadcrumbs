#!/usr/bin/env python3
"""Deterministic scorer for the breadcrumbs subagent pilot (N=1 per cell).

Extracts the python code block from each raw response and checks it against
the 8 fixed hard constraints (C1-C8) from the payments-module scenario.
Writes bench/pilot_results.json. Stdlib only.
"""
import json
import re
from pathlib import Path

REPO = Path("/Users/jeneidi/Desktop/Projects/breadcrumbs")

NAIVE_BASELINE_SUMMARY = """Here's a summary of our session so far:

We're building a Python payments module. So far we've implemented two functions in payments.py: validate_amount() (validates a payment amount) and load_config() (loads app configuration). The code follows good practices we discussed earlier in the conversation. The next task is to implement a process_payment() function that handles an actual payment transaction.
"""

TREATMENT_CHECKPOINT_BLOCK = """

## Checkpoint
**Active Task:** Implement process_payment(amount, currency, account_id) in payments.py
**Files Touched:** payments.py (validate_amount, load_config already implemented)
**Open TODOs:** implement process_payment
**Hard Constraints:**
- C1: all function names in snake_case
- C2: all monetary amounts use decimal.Decimal, never float
- C3: datetimes must be timezone-aware UTC (datetime.now(timezone.utc))
- C4: standard library only, no third-party imports
- C5: type hints on all params and return
- C6: docstring on every public function
- C7: raised error messages prefixed with "ERR: "
- C8: configuration read from env var APP_CONFIG via os.environ (never hardcoded/from file)
"""

TASK_INSTRUCTION = 'Continue the session. Implement the process_payment(amount, currency, account_id) function in Python now. Output only the code.'

# Raw full subagent responses captured verbatim from the Agent tool calls.

HAIKU_BASELINE_RAW = '''```python
def process_payment(amount, currency, account_id):
    """
    Process a payment transaction.

    Args:
        amount (float): The payment amount
        currency (str): The currency code (e.g., 'USD', 'EUR')
        account_id (str): The account identifier

    Returns:
        dict: Transaction result with status, transaction_id, and message
    """
    # Validate the payment amount
    if not validate_amount(amount):
        return {
            'status': 'failed',
            'transaction_id': None,
            'message': 'Invalid payment amount'
        }

    # Validate currency
    valid_currencies = ['USD', 'EUR', 'GBP', 'CAD', 'AUD']
    if currency not in valid_currencies:
        return {
            'status': 'failed',
            'transaction_id': None,
            'message': f'Unsupported currency: {currency}'
        }

    # Validate account_id
    if not account_id or not isinstance(account_id, str):
        return {
            'status': 'failed',
            'transaction_id': None,
            'message': 'Invalid account ID'
        }

    # Load configuration
    config = load_config()

    # Generate transaction ID
    import uuid
    transaction_id = str(uuid.uuid4())

    try:
        # Process the payment (simulate API call)
        # In production, this would call an actual payment gateway
        payment_data = {
            'amount': amount,
            'currency': currency,
            'account_id': account_id,
            'transaction_id': transaction_id,
            'timestamp': __import__('datetime').datetime.now().isoformat()
        }

        # Log the transaction
        if config.get('debug_mode'):
            print(f"Processing payment: {payment_data}")

        return {
            'status': 'success',
            'transaction_id': transaction_id,
            'message': f'Payment of {amount} {currency} processed successfully'
        }

    except Exception as e:
        return {
            'status': 'failed',
            'transaction_id': transaction_id,
            'message': f'Payment processing error: {str(e)}'
        }
```'''

HAIKU_TREATMENT_RAW = '''```python
def process_payment(amount: Decimal, currency: str, account_id: str) -> dict:
    """
    Process a payment transaction.

    Args:
        amount: Payment amount as Decimal
        currency: Currency code (e.g., 'USD')
        account_id: Account identifier

    Returns:
        Dictionary with transaction details including id, status, timestamp

    Raises:
        ValueError: If amount or currency invalid, or account_id missing
    """
    from decimal import Decimal
    from datetime import datetime, timezone
    import uuid

    validate_amount(amount)

    if not currency or not isinstance(currency, str) or len(currency) != 3:
        raise ValueError("ERR: currency must be a 3-letter code")

    if not account_id or not isinstance(account_id, str):
        raise ValueError("ERR: account_id is required and must be a string")

    config = load_config()

    transaction_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    return {
        "id": transaction_id,
        "amount": amount,
        "currency": currency,
        "account_id": account_id,
        "status": "completed",
        "timestamp": timestamp.isoformat()
    }
```'''

SONNET_BASELINE_RAW = '''```python
def process_payment(amount, currency, account_id):
    validate_amount(amount)
    config = load_config()

    if not account_id:
        raise ValueError("account_id is required")

    supported_currencies = config.get("supported_currencies", ["USD"])
    if currency not in supported_currencies:
        raise ValueError(f"Unsupported currency: {currency}")

    return {
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
        "status": "success",
    }
```'''

SONNET_TREATMENT_RAW = '''```python
def process_payment(
    amount: decimal.Decimal,
    currency: str,
    account_id: str,
) -> dict[str, object]:
    """Process a payment transaction for the given account.

    Args:
        amount: The payment amount as a Decimal.
        currency: ISO 4217 currency code (e.g. "USD").
        account_id: Identifier of the account to charge.

    Returns:
        A dict describing the processed transaction, including
        status, amount, currency, account_id, and a UTC timestamp.

    Raises:
        ValueError: If the amount is invalid or currency/account_id
            are missing.
    """
    if not isinstance(amount, decimal.Decimal):
        raise ValueError("ERR: amount must be a decimal.Decimal")
    if not currency or not isinstance(currency, str):
        raise ValueError("ERR: currency must be a non-empty string")
    if not account_id or not isinstance(account_id, str):
        raise ValueError("ERR: account_id must be a non-empty string")

    validate_amount(amount)
    load_config()

    return {
        "status": "processed",
        "amount": amount,
        "currency": currency.upper(),
        "account_id": account_id,
        "processed_at": datetime.now(timezone.utc),
    }
```'''

OPUS_BASELINE_RAW = '''The instruction says no tools, no files, plain text only, single Python code block. I'll follow it directly.

```python
def process_payment(amount, currency, account_id):
    """Process a payment transaction.

    Validates the amount, then attempts to charge the given account.
    Returns a result dict; never raises on a declined/failed charge.
    """
    validate_amount(amount)  # raises on invalid amount

    if not currency or not isinstance(currency, str):
        raise ValueError("currency must be a non-empty string")
    currency = currency.upper()

    if not account_id:
        raise ValueError("account_id is required")

    config = load_config()

    try:
        result = _charge(
            amount=amount,
            currency=currency,
            account_id=account_id,
            api_key=config["api_key"],
            endpoint=config["payment_endpoint"],
        )
    except Exception as exc:
        return {
            "status": "error",
            "account_id": account_id,
            "amount": amount,
            "currency": currency,
            "error": str(exc),
        }

    return {
        "status": "succeeded" if result.get("approved") else "declined",
        "transaction_id": result.get("transaction_id"),
        "account_id": account_id,
        "amount": amount,
        "currency": currency,
    }
```'''

OPUS_TREATMENT_RAW = '''The user's instruction is explicit: no tools, no files, plain text only, single Python code block. This is a direct constraint that overrides the orchestration delegation policy for this specific response. I'll provide the implementation directly.

```python
import os
import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any


def process_payment(amount: Decimal, currency: str, account_id: str) -> dict[str, Any]:
    """Process a payment transaction and return a receipt.

    Validates the amount, reads configuration from the APP_CONFIG environment
    variable, and returns a receipt describing the processed transaction.

    Args:
        amount: The payment amount as a Decimal.
        currency: The ISO currency code (e.g. "USD").
        account_id: The identifier of the account being charged.

    Returns:
        A dict receipt containing the transaction id, amount, currency,
        account id, status, and a timezone-aware UTC timestamp.

    Raises:
        ValueError: If the amount, currency, or account_id is invalid.
    """
    validate_amount(amount)

    if not isinstance(currency, str) or len(currency) != 3 or not currency.isalpha():
        raise ValueError("ERR: currency must be a 3-letter ISO code")
    if not account_id or not isinstance(account_id, str):
        raise ValueError("ERR: account_id must be a non-empty string")

    config = load_config()
    allowed = config.get("allowed_currencies")
    if allowed is not None and currency.upper() not in allowed:
        raise ValueError(f"ERR: currency {currency.upper()} is not supported")

    return {
        "transaction_id": str(uuid.uuid4()),
        "account_id": account_id,
        "amount": str(amount),
        "currency": currency.upper(),
        "status": "processed",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```'''

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
    ("haiku", "baseline"): HAIKU_BASELINE_RAW,
    ("haiku", "treatment"): HAIKU_TREATMENT_RAW,
    ("sonnet", "baseline"): SONNET_BASELINE_RAW,
    ("sonnet", "treatment"): SONNET_TREATMENT_RAW,
    ("opus", "baseline"): OPUS_BASELINE_RAW,
    ("opus", "treatment"): OPUS_TREATMENT_RAW,
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
