from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from churn import (
    DEFINITION_VERSION,
    ChurnResult,
    CustomerExplanation,
    calculate_churn,
    explain_customer,
    parse_period,
)

app = FastAPI(title="Churn Engine", version="1.0.0")


class ChurnResponse(BaseModel):
    period: str
    period_start: date
    period_end: date
    active_at_start: int
    churned_count: int
    logo_churn_rate: float
    logo_churn_pct: str
    mrr_at_start: float
    lost_mrr: float
    revenue_churn_rate: float
    revenue_churn_pct: str
    definition_version: str


class ExplainResponse(BaseModel):
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


class DefinitionResponse(BaseModel):
    definition_version: str
    description: str
    logo_churn_formula: str
    revenue_churn_formula: str
    period_formats: list[str]
    edge_cases: list[str]


@app.get("/churn", response_model=ChurnResponse)
def get_churn(
    period: str = Query(..., description="YYYY, YYYY-QN, or YYYY-MM", examples=["2024-Q4"])
):
    """Return logo and revenue churn rates for the given period."""
    try:
        result: ChurnResult = calculate_churn(period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ChurnResponse(
        period=result.period,
        period_start=result.period_start,
        period_end=result.period_end,
        active_at_start=result.active_at_start,
        churned_count=result.churned_count,
        logo_churn_rate=result.logo_churn_rate,
        logo_churn_pct=f"{result.logo_churn_rate * 100:.2f}%",
        mrr_at_start=result.mrr_at_start,
        lost_mrr=result.lost_mrr,
        revenue_churn_rate=result.revenue_churn_rate,
        revenue_churn_pct=f"{result.revenue_churn_rate * 100:.2f}%",
        definition_version=result.definition_version,
    )


@app.get("/churn/explain", response_model=ExplainResponse)
def get_explain(
    customer_id: str = Query(..., description="Customer ID, e.g. C0042"),
    period: str = Query(..., description="YYYY, YYYY-QN, or YYYY-MM", examples=["2024-Q4"]),
):
    """Explain why a customer is (or is not) counted as churned for the period."""
    try:
        result: CustomerExplanation = explain_customer(customer_id, period)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ExplainResponse(**result.__dict__)


@app.get("/definitions", response_model=DefinitionResponse)
def get_definitions():
    """Return the active metric definition and its assumptions."""
    return DefinitionResponse(
        definition_version=DEFINITION_VERSION,
        description=(
            "Logo churn = customers whose subscription ended in the period / "
            "customers active at period start. "
            "Revenue churn = MRR lost from churned customers / "
            "total MRR of customers active at period start."
        ),
        logo_churn_formula="churned_customers / active_at_period_start",
        revenue_churn_formula="lost_mrr / mrr_at_period_start",
        period_formats=["YYYY (annual)", "YYYY-QN (quarterly)", "YYYY-MM (monthly)"],
        edge_cases=[
            "Downgrades are NOT counted as logo churn; MRR delta is counted in revenue churn.",
            "Customer starting and churning in the same period: excluded from denominator.",
            "end_date == period_start: customer was active at start, not churned this period.",
            "Duplicate rows are deduplicated by customer_id (last row wins).",
            "Missing MRR: customer included in logo churn, excluded from revenue churn.",
            "Null churn_reason does not block churn classification.",
        ],
    )
