import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from churn import calculate_churn, explain_customer, parse_period

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_df(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = df["end_date"].apply(
        lambda v: pd.to_datetime(v).date() if pd.notna(v) and v is not None else None
    )
    return df


def _patch(rows):
    """Context manager: replace _load() with a fixed DataFrame."""
    import churn
    return patch.object(churn, "_load", return_value=_make_df(rows))


# ---------------------------------------------------------------------------
# parse_period
# ---------------------------------------------------------------------------

def test_parse_annual():
    assert parse_period("2024") == (date(2024, 1, 1), date(2024, 12, 31))

def test_parse_quarterly():
    assert parse_period("2024-Q1") == (date(2024, 1, 1), date(2024, 3, 31))
    assert parse_period("2024-Q4") == (date(2024, 10, 1), date(2024, 12, 31))

def test_parse_monthly():
    assert parse_period("2024-02") == (date(2024, 2, 1), date(2024, 2, 29))  # leap year

def test_parse_invalid_quarter():
    with pytest.raises(ValueError):
        parse_period("2024-Q5")

def test_parse_invalid_format():
    with pytest.raises(ValueError):
        parse_period("not-a-date")


# ---------------------------------------------------------------------------
# calculate_churn — happy paths
# ---------------------------------------------------------------------------

BASE_ROWS = [
    # active all year, does not churn
    {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2024-01-01", "end_date": None, "churn_reason": None},
    # active at start of Q1, churns in Q1
    {"customer_id": "C002", "plan": "starter", "mrr": 49, "start_date": "2023-06-01", "end_date": "2024-02-15", "churn_reason": "voluntary"},
    # starts mid-Q1, churns mid-Q1 → not active at period start
    {"customer_id": "C003", "plan": "starter", "mrr": 49, "start_date": "2024-02-01", "end_date": "2024-03-01", "churn_reason": "involuntary"},
    # churns exactly on period_start → NOT churned this period (edge case)
    {"customer_id": "C004", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-01-01", "churn_reason": "voluntary"},
]

def test_logo_churn_basic():
    with _patch(BASE_ROWS):
        r = calculate_churn("2024-Q1")
    # Active at 2024-01-01: C001 (start<=start, no end), C002 (start<=start, end>start), C004 (end==start → active by edge rule? No — end==period_start means NOT active, see definition)
    # Per definition: active = start_date <= p_start AND (end is None OR end > p_start)
    # C001: start 2024-01-01 <= 2024-01-01, end None → active
    # C002: start 2023-06-01 <= 2024-01-01, end 2024-02-15 > 2024-01-01 → active
    # C003: start 2024-02-01 > 2024-01-01 → NOT active at start
    # C004: start 2023-01-01 <= 2024-01-01, end 2024-01-01 NOT > 2024-01-01 → NOT active
    assert r.active_at_start == 2
    # Churned: end within [2024-01-01, 2024-03-31]
    # C002: end 2024-02-15 → churned
    assert r.churned_count == 1
    assert r.logo_churn_rate == pytest.approx(0.5)

def test_revenue_churn_basic():
    with _patch(BASE_ROWS):
        r = calculate_churn("2024-Q1")
    assert r.mrr_at_start == pytest.approx(149 + 49)  # C001 + C002
    assert r.lost_mrr == pytest.approx(49)             # C002 only
    assert r.revenue_churn_rate == pytest.approx(49 / 198)

def test_zero_active():
    rows = [
        {"customer_id": "C001", "plan": "starter", "mrr": 49, "start_date": "2025-06-01", "end_date": None, "churn_reason": None},
    ]
    with _patch(rows):
        r = calculate_churn("2024-Q1")
    assert r.active_at_start == 0
    assert r.logo_churn_rate == 0.0
    assert r.revenue_churn_rate == 0.0

def test_missing_mrr_excluded_from_revenue():
    rows = [
        {"customer_id": "C001", "plan": "pro", "mrr": None, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
        {"customer_id": "C002", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": None, "churn_reason": None},
    ]
    with _patch(rows):
        r = calculate_churn("2024-Q1")
    assert r.active_at_start == 2   # both active
    assert r.churned_count == 1     # C001 churned (logo)
    assert r.logo_churn_rate == pytest.approx(0.5)
    assert r.mrr_at_start == pytest.approx(149)   # C001 excluded from revenue denominator
    assert r.lost_mrr == pytest.approx(0.0)        # C001 excluded from revenue numerator

def test_deduplication():
    rows = [
        {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
        {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": "2024-02-01", "churn_reason": "voluntary"},
    ]
    with _patch(rows):
        r = calculate_churn("2024-Q1")
    assert r.active_at_start == 1  # duplicate removed


# ---------------------------------------------------------------------------
# explain_customer
# ---------------------------------------------------------------------------

def test_explain_churned():
    with _patch(BASE_ROWS):
        e = explain_customer("C002", "2024-Q1")
    assert e.counted_as_churned is True
    assert "churned" in e.reason.lower()

def test_explain_active():
    with _patch(BASE_ROWS):
        e = explain_customer("C001", "2024-Q1")
    assert e.counted_as_churned is False

def test_explain_not_found():
    with _patch(BASE_ROWS):
        e = explain_customer("C999", "2024-Q1")
    assert e.counted_as_churned is False
    assert "not found" in e.reason.lower()

def test_explain_started_after_period():
    with _patch(BASE_ROWS):
        e = explain_customer("C003", "2024-Q1")
    assert e.counted_as_churned is False
    assert "not active" in e.reason.lower()
