"""
Scorecard — eval harness for the Churn Engine.

Three quality metrics reported at the end of the run:
  Accuracy              correct answers on the golden set
  Refusal accuracy      correct refusals on inputs the engine can't answer
  False-confidence rate confident-and-wrong answers (the dangerous failure mode)

Run:
  python -m pytest engine/tests/test_scorecard.py -v -s
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import churn
from churn import calculate_churn, explain_customer, parse_period

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _df(rows):
    df = pd.DataFrame(rows)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = df["end_date"].apply(
        lambda v: pd.to_datetime(v).date() if pd.notna(v) and v is not None else None
    )
    return df


def _patch(rows):
    return patch.object(churn, "_load", return_value=_df(rows))


# ---------------------------------------------------------------------------
# GOLDEN SET — questions with known expected answers
# ---------------------------------------------------------------------------

GOLDEN = [
    {
        "id": "G01",
        "description": "Standard quarter: 2 active, 1 churns mid-period",
        "rows": [
            {"customer_id": "C001", "plan": "pro",     "mrr": 149, "start_date": "2023-01-01", "end_date": None,         "churn_reason": None},
            {"customer_id": "C002", "plan": "starter", "mrr": 49,  "start_date": "2023-06-01", "end_date": "2024-02-15", "churn_reason": "voluntary"},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 2, "churned_count": 1, "logo_churn_rate": 0.5},
    },
    {
        "id": "G02",
        "description": "Zero churn: all customers active, nobody leaves",
        "rows": [
            {"customer_id": "C001", "plan": "pro",     "mrr": 149, "start_date": "2023-01-01", "end_date": None, "churn_reason": None},
            {"customer_id": "C002", "plan": "starter", "mrr": 49,  "start_date": "2023-06-01", "end_date": None, "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 2, "churned_count": 0, "logo_churn_rate": 0.0},
    },
    {
        "id": "G03",
        "description": "Annual period parses correctly and spans full year",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-06-01", "churn_reason": "voluntary"},
        ],
        "period": "2024",
        "expect": {"active_at_start": 1, "churned_count": 1, "logo_churn_rate": 1.0},
    },
    {
        "id": "G04",
        "description": "Monthly period: February leap year parses correctly",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-02-15", "churn_reason": "voluntary"},
        ],
        "period": "2024-02",
        "expect": {"active_at_start": 1, "churned_count": 1},
    },
    {
        "id": "G05",
        "description": "definition_version is always present in every result",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": None, "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"definition_version": churn.DEFINITION_VERSION},
    },
    {
        "id": "G06",
        "description": "Revenue churn excludes customers with missing MRR from both sides",
        "rows": [
            {"customer_id": "C001", "plan": "pro",     "mrr": None, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
            {"customer_id": "C002", "plan": "starter", "mrr": 49,   "start_date": "2023-01-01", "end_date": None,         "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 2, "churned_count": 1, "mrr_at_start": 49.0, "lost_mrr": 0.0},
    },
]


@pytest.mark.parametrize("case", GOLDEN, ids=[c["id"] for c in GOLDEN])
def test_golden(case):
    with _patch(case["rows"]):
        result = calculate_churn(case["period"])
    for key, expected in case["expect"].items():
        actual = getattr(result, key)
        if isinstance(expected, float):
            assert abs(actual - expected) < 1e-6, f"{case['id']} {key}: got {actual}, expected {expected}"
        else:
            assert actual == expected, f"{case['id']} {key}: got {actual}, expected {expected}"


# ---------------------------------------------------------------------------
# REFUSE SET — inputs the engine must reject, not silently mangle
# ---------------------------------------------------------------------------

REFUSE = [
    {"id": "R01", "description": "Reversed period format",      "period": "Q1-2024"},
    {"id": "R02", "description": "Invalid quarter number",      "period": "2024-Q9"},
    {"id": "R03", "description": "Quarter zero",                "period": "2024-Q0"},
    {"id": "R04", "description": "Free-text period",            "period": "last_quarter"},
    {"id": "R05", "description": "Month 13 does not exist",     "period": "2024-13"},
]


@pytest.mark.parametrize("case", REFUSE, ids=[c["id"] for c in REFUSE])
def test_refuse(case):
    with pytest.raises((ValueError, Exception)):
        parse_period(case["period"])


# ---------------------------------------------------------------------------
# FALSE-CONFIDENCE TRAPS
# Inputs where a naive / broken implementation returns a plausible-sounding
# but wrong answer.  These are the cases that "get people fired."
# ---------------------------------------------------------------------------

FALSE_CONFIDENCE = [
    {
        "id": "FC01",
        "description": "Duplicate rows must NOT inflate the churned count",
        "trap": "Naive engine counts both rows → churned_count=2; correct is 1",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 1, "churned_count": 1},
    },
    {
        "id": "FC02",
        "description": "end_date == period_start must NOT be counted as churned",
        "trap": "Naive engine treats end_date=period_start as 'left this period' → rate inflated",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-01-01", "churn_reason": "voluntary"},
            {"customer_id": "C002", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": None,         "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 1, "churned_count": 0, "logo_churn_rate": 0.0},
    },
    {
        "id": "FC03",
        "description": "Customer who starts and churns same period must NOT appear in denominator",
        "trap": "Naive engine adds them to active_at_start → denominator inflated → rate diluted",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2024-02-01", "end_date": "2024-03-01", "churn_reason": "voluntary"},
            {"customer_id": "C002", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": None,         "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 1, "churned_count": 0},
    },
    {
        "id": "FC04",
        "description": "Missing MRR customer must NOT crash the revenue calculation",
        "trap": "Naive engine tries mrr.sum() on None → TypeError or NaN silently treated as 0",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": None, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
        ],
        "period": "2024-Q1",
        "expect": {"churned_count": 1, "lost_mrr": 0.0, "mrr_at_start": 0.0},
    },
    {
        "id": "FC05",
        "description": "Logo churn must still count MRR-null customers even though revenue churn excludes them",
        "trap": "Naive engine drops null-MRR rows entirely → logo count too low",
        "rows": [
            {"customer_id": "C001", "plan": "pro", "mrr": None, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
            {"customer_id": "C002", "plan": "pro", "mrr": None, "start_date": "2023-01-01", "end_date": None,         "churn_reason": None},
        ],
        "period": "2024-Q1",
        "expect": {"active_at_start": 2, "churned_count": 1, "logo_churn_rate": 0.5},
    },
]


@pytest.mark.parametrize("case", FALSE_CONFIDENCE, ids=[c["id"] for c in FALSE_CONFIDENCE])
def test_false_confidence(case):
    with _patch(case["rows"]):
        result = calculate_churn(case["period"])
    for key, expected in case["expect"].items():
        actual = getattr(result, key)
        if isinstance(expected, float):
            assert abs(actual - expected) < 1e-6, (
                f"{case['id']} FALSE-CONFIDENCE TRAP TRIGGERED — {case['trap']}\n"
                f"  {key}: got {actual}, expected {expected}"
            )
        else:
            assert actual == expected, (
                f"{case['id']} FALSE-CONFIDENCE TRAP TRIGGERED — {case['trap']}\n"
                f"  {key}: got {actual}, expected {expected}"
            )


# ---------------------------------------------------------------------------
# SCORECARD REPORT — printed at the end of the run with -s flag
# ---------------------------------------------------------------------------

def _run_golden():
    passed = 0
    for case in GOLDEN:
        try:
            with _patch(case["rows"]):
                result = calculate_churn(case["period"])
            ok = all(
                abs(getattr(result, k) - v) < 1e-6 if isinstance(v, float) else getattr(result, k) == v
                for k, v in case["expect"].items()
            )
            if ok:
                passed += 1
        except Exception:
            pass
    return passed, len(GOLDEN)


def _run_refuse():
    passed = 0
    for case in REFUSE:
        try:
            parse_period(case["period"])
        except (ValueError, Exception):
            passed += 1
    return passed, len(REFUSE)


def _run_fc():
    wrong = 0
    total = len(FALSE_CONFIDENCE)
    for case in FALSE_CONFIDENCE:
        try:
            with _patch(case["rows"]):
                result = calculate_churn(case["period"])
            for k, v in case["expect"].items():
                actual = getattr(result, k)
                if isinstance(v, float):
                    if abs(actual - v) >= 1e-6:
                        wrong += 1
                        break
                else:
                    if actual != v:
                        wrong += 1
                        break
        except Exception:
            wrong += 1
    return wrong, total


def test_scorecard_report(capsys):
    g_pass, g_total = _run_golden()
    r_pass, r_total = _run_refuse()
    fc_wrong, fc_total = _run_fc()

    accuracy         = g_pass / g_total
    refusal_accuracy = r_pass / r_total
    fc_rate          = fc_wrong / fc_total

    with capsys.disabled():
        print("\n")
        print("=" * 52)
        print("  CHURN ENGINE — SCORECARD REPORT")
        print("=" * 52)
        print(f"  Accuracy              {accuracy:.0%}  ({g_pass}/{g_total} golden questions)")
        print(f"  Refusal accuracy      {refusal_accuracy:.0%}  ({r_pass}/{r_total} invalid inputs rejected)")
        print(f"  False-confidence rate {fc_rate:.0%}  ({fc_wrong}/{fc_total} traps triggered)")
        print("=" * 52)
        if fc_rate > 0:
            print("  WARNING: false-confidence failures detected.")
            print("  Confident-and-wrong answers are the dangerous failure mode.")
        else:
            print("  No false-confidence failures. Engine is safe to trust.")
        print("=" * 52)
        print()

    assert accuracy == 1.0,         f"Accuracy below 100%: {g_pass}/{g_total}"
    assert refusal_accuracy == 1.0, f"Refusal accuracy below 100%: {r_pass}/{r_total}"
    assert fc_rate == 0.0,          f"False-confidence traps triggered: {fc_wrong}/{fc_total}"
