from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

DEFINITION_VERSION = "v1.0"
DATA_PATH = Path(__file__).parent.parent / "data" / "subscriptions.csv"


def _load() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, parse_dates=["start_date", "end_date"])
    df["start_date"] = df["start_date"].dt.date
    df["end_date"] = df["end_date"].apply(
        lambda v: v.date() if pd.notna(v) else None
    )
    # Normalise plan names: strip whitespace, lowercase, drop version suffixes
    df["plan"] = df["plan"].str.strip().str.lower().str.replace(r"_v\d+$", "", regex=True)
    # Correct UTC+2 timezone offset introduced by the legacy export source
    if "source_system" in df.columns:
        legacy = df["source_system"] == "legacy"
        df.loc[legacy, "end_date"] = df.loc[legacy, "end_date"].apply(
            lambda d: d - timedelta(days=1) if d is not None else None
        )
    return df


def _dedup(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates(subset="customer_id", keep="last").reset_index(drop=True)


def parse_period(period: str) -> tuple[date, date]:
    """Return (period_start, period_end) for YYYY, YYYY-QN, or YYYY-MM."""
    period = period.strip().upper()

    if "Q" in period:
        year_str, q_str = period.split("-Q")
        year = int(year_str)
        q = int(q_str)
        if q not in (1, 2, 3, 4):
            raise ValueError(f"Quarter must be 1–4, got {q}")
        month_start = (q - 1) * 3 + 1
        month_end = month_start + 2
        last_day = calendar.monthrange(year, month_end)[1]
        return date(year, month_start, 1), date(year, month_end, last_day)

    parts = period.split("-")
    if len(parts) == 2:
        year, month = int(parts[0]), int(parts[1])
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, 1), date(year, month, last_day)

    if len(parts) == 1:
        year = int(parts[0])
        return date(year, 1, 1), date(year, 12, 31)

    raise ValueError(f"Unrecognised period format: {period!r}")


@dataclass
class ChurnResult:
    period: str
    period_start: date
    period_end: date
    active_at_start: int
    churned_count: int
    logo_churn_rate: float
    mrr_at_start: float
    lost_mrr: float
    revenue_churn_rate: float
    definition_version: str


def calculate_churn(period: str) -> ChurnResult:
    df = _dedup(_load())
    p_start, p_end = parse_period(period)

    active = df[
        (df["start_date"] <= p_start)
        & (df["end_date"].apply(lambda d: d is None or d > p_start))
    ]

    churned = active[
        active["end_date"].apply(lambda d: d is not None and p_start <= d <= p_end)
    ]

    active_count = len(active)
    churned_count = len(churned)
    logo_rate = churned_count / active_count if active_count else 0.0

    # revenue churn — exclude rows with missing mrr
    if "mrr" in active.columns and not active.empty:
        active_rev = active.dropna(subset=["mrr"])
        churned_rev = churned.dropna(subset=["mrr"]) if not churned.empty else churned
        mrr_at_start = float(active_rev["mrr"].sum())
        lost_mrr = float(churned_rev["mrr"].sum()) if not churned_rev.empty else 0.0
    else:
        mrr_at_start = 0.0
        lost_mrr = 0.0
    rev_rate = lost_mrr / mrr_at_start if mrr_at_start else 0.0

    return ChurnResult(
        period=period,
        period_start=p_start,
        period_end=p_end,
        active_at_start=active_count,
        churned_count=churned_count,
        logo_churn_rate=logo_rate,
        mrr_at_start=round(mrr_at_start, 2),
        lost_mrr=round(lost_mrr, 2),
        revenue_churn_rate=rev_rate,
        definition_version=DEFINITION_VERSION,
    )


@dataclass
class CustomerExplanation:
    customer_id: str
    period: str
    period_start: date
    period_end: date
    counted_as_churned: bool
    reason: str
    plan: Optional[str]
    mrr: Optional[float]
    start_date: Optional[date]
    end_date: Optional[date]
    definition_version: str


def explain_customer(customer_id: str, period: str) -> CustomerExplanation:
    df = _dedup(_load())
    p_start, p_end = parse_period(period)

    rows = df[df["customer_id"] == customer_id]
    if rows.empty:
        return CustomerExplanation(
            customer_id=customer_id,
            period=period,
            period_start=p_start,
            period_end=p_end,
            counted_as_churned=False,
            reason="Customer ID not found in dataset.",
            plan=None,
            mrr=None,
            start_date=None,
            end_date=None,
            definition_version=DEFINITION_VERSION,
        )

    row = rows.iloc[0]
    start = row["start_date"]
    end = row["end_date"]
    mrr = None if pd.isna(row["mrr"]) else float(row["mrr"])

    active_at_start = start <= p_start and (end is None or end > p_start)
    churned = end is not None and p_start <= end <= p_end

    if not active_at_start:
        reason = (
            f"Not active at period start ({p_start}): "
            f"start_date={start}, end_date={end}."
        )
    elif churned:
        reason = f"end_date={end} falls within period [{p_start}, {p_end}] → counted as churned."
    else:
        reason = (
            f"Active at period start and did not churn during period "
            f"(end_date={end})."
        )

    return CustomerExplanation(
        customer_id=customer_id,
        period=period,
        period_start=p_start,
        period_end=p_end,
        counted_as_churned=active_at_start and churned,
        reason=reason,
        plan=row["plan"],
        mrr=mrr,
        start_date=start,
        end_date=end,
        definition_version=DEFINITION_VERSION,
    )
