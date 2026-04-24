import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

import churn
from main import app

client = TestClient(app)

SAMPLE_ROWS = [
    # active all year, no churn
    {"customer_id": "C001", "plan": "pro", "mrr": 149, "start_date": "2023-01-01", "end_date": None, "churn_reason": None},
    # active at Q1 start, churns mid-Q1
    {"customer_id": "C002", "plan": "starter", "mrr": 49, "start_date": "2023-06-01", "end_date": "2024-02-15", "churn_reason": "voluntary"},
    # starts mid-Q1 — not active at period start
    {"customer_id": "C003", "plan": "enterprise", "mrr": 499, "start_date": "2024-02-01", "end_date": None, "churn_reason": None},
]


def _make_df(rows):
    df = pd.DataFrame(rows)
    df["start_date"] = pd.to_datetime(df["start_date"]).dt.date
    df["end_date"] = df["end_date"].apply(
        lambda v: pd.to_datetime(v).date() if pd.notna(v) and v is not None else None
    )
    return df


def _patch():
    return patch.object(churn, "_load", return_value=_make_df(SAMPLE_ROWS))


# ---------------------------------------------------------------------------
# GET /churn
# ---------------------------------------------------------------------------

def test_churn_returns_200():
    with _patch():
        r = client.get("/churn", params={"period": "2024-Q1"})
    assert r.status_code == 200


def test_churn_response_shape():
    with _patch():
        body = client.get("/churn", params={"period": "2024-Q1"}).json()
    expected_keys = {
        "period", "period_start", "period_end",
        "active_at_start", "churned_count",
        "logo_churn_rate", "logo_churn_pct",
        "mrr_at_start", "lost_mrr",
        "revenue_churn_rate", "revenue_churn_pct",
        "definition_version",
    }
    assert expected_keys == set(body.keys())


def test_churn_values():
    with _patch():
        body = client.get("/churn", params={"period": "2024-Q1"}).json()
    # C001 + C002 active at 2024-01-01; C002 churns 2024-02-15
    assert body["active_at_start"] == 2
    assert body["churned_count"] == 1
    assert body["logo_churn_pct"] == "50.00%"
    assert body["mrr_at_start"] == pytest.approx(198.0)
    assert body["lost_mrr"] == pytest.approx(49.0)


def test_churn_carries_definition_version():
    with _patch():
        body = client.get("/churn", params={"period": "2024-Q1"}).json()
    assert body["definition_version"] == churn.DEFINITION_VERSION


def test_churn_dates_are_iso_strings():
    with _patch():
        body = client.get("/churn", params={"period": "2024-Q1"}).json()
    assert body["period_start"] == "2024-01-01"
    assert body["period_end"] == "2024-03-31"


def test_churn_bad_period_returns_400():
    with _patch():
        r = client.get("/churn", params={"period": "not-a-period"})
    assert r.status_code == 400


def test_churn_bad_quarter_returns_400():
    with _patch():
        r = client.get("/churn", params={"period": "2024-Q9"})
    assert r.status_code == 400


def test_churn_monthly_period():
    with _patch():
        r = client.get("/churn", params={"period": "2024-02"})
    assert r.status_code == 200
    body = r.json()
    assert body["period_start"] == "2024-02-01"
    assert body["period_end"] == "2024-02-29"  # 2024 is a leap year


def test_churn_annual_period():
    with _patch():
        r = client.get("/churn", params={"period": "2024"})
    assert r.status_code == 200
    assert r.json()["period_end"] == "2024-12-31"


# ---------------------------------------------------------------------------
# GET /churn/explain
# ---------------------------------------------------------------------------

def test_explain_churned_customer():
    with _patch():
        body = client.get("/churn/explain", params={"customer_id": "C002", "period": "2024-Q1"}).json()
    assert body["counted_as_churned"] is True
    assert body["definition_version"] == churn.DEFINITION_VERSION


def test_explain_active_customer():
    with _patch():
        body = client.get("/churn/explain", params={"customer_id": "C001", "period": "2024-Q1"}).json()
    assert body["counted_as_churned"] is False


def test_explain_unknown_customer_returns_200_not_404():
    with _patch():
        r = client.get("/churn/explain", params={"customer_id": "CXXX", "period": "2024-Q1"})
    # "not found" is a valid explanation, not an HTTP error
    assert r.status_code == 200
    assert r.json()["counted_as_churned"] is False


def test_explain_response_carries_customer_dates():
    with _patch():
        body = client.get("/churn/explain", params={"customer_id": "C002", "period": "2024-Q1"}).json()
    assert body["start_date"] == "2023-06-01"
    assert body["end_date"] == "2024-02-15"
    assert body["plan"] == "starter"
    assert body["mrr"] == pytest.approx(49.0)


def test_explain_bad_period_returns_400():
    with _patch():
        r = client.get("/churn/explain", params={"customer_id": "C001", "period": "bad"})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# GET /definitions
# ---------------------------------------------------------------------------

def test_definitions_returns_200():
    r = client.get("/definitions")
    assert r.status_code == 200


def test_definitions_shape():
    body = client.get("/definitions").json()
    assert "definition_version" in body
    assert "logo_churn_formula" in body
    assert "revenue_churn_formula" in body
    assert "edge_cases" in body
    assert isinstance(body["edge_cases"], list)
    assert len(body["edge_cases"]) > 0


def test_definitions_version_matches_engine():
    body = client.get("/definitions").json()
    assert body["definition_version"] == churn.DEFINITION_VERSION
