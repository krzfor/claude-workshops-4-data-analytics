"""
MCP server for the Churn Engine semantic layer.

Tools exposed:
  get_metric          — churn rate for a period
  list_definitions    — active definition, formulas, edge-case decisions
  explain_calculation — why a specific customer is (or isn't) counted
  compare_periods     — delta between two periods

Run standalone:
  cd engine && python mcp_server.py

Register in Claude Code (.claude/settings.json):
  {
    "mcpServers": {
      "churn-engine": {
        "command": "python",
        "args": ["engine/mcp_server.py"],
        "cwd": "<repo-root>"
      }
    }
  }
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from churn import DEFINITION_VERSION, calculate_churn, explain_customer, parse_period
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Churn Engine")


@mcp.tool()
def get_metric(period: str) -> str:
    """
    Calculate logo and revenue churn for a period.

    period: YYYY  (annual), YYYY-QN  (quarterly), or YYYY-MM  (monthly).
    Returns JSON with logo_churn_pct, revenue_churn_pct, active_at_start,
    churned_count, mrr_at_start, lost_mrr, and definition_version.
    """
    try:
        r = calculate_churn(period)
    except ValueError as e:
        return json.dumps({"error": str(e)})

    return json.dumps({
        "period":             r.period,
        "period_start":       str(r.period_start),
        "period_end":         str(r.period_end),
        "logo_churn_pct":     f"{r.logo_churn_rate * 100:.2f}%",
        "revenue_churn_pct":  f"{r.revenue_churn_rate * 100:.2f}%",
        "active_at_start":    r.active_at_start,
        "churned_count":      r.churned_count,
        "mrr_at_start":       r.mrr_at_start,
        "lost_mrr":           r.lost_mrr,
        "definition_version": r.definition_version,
    }, indent=2)


@mcp.tool()
def list_definitions() -> str:
    """
    Return the active metric definition, formulas, and every edge-case decision.
    Use this before interpreting any metric result to understand what the numbers mean.
    """
    return json.dumps({
        "definition_version": DEFINITION_VERSION,
        "logo_churn": {
            "formula":     "churned_customers / active_at_period_start",
            "active":      "start_date <= period_start AND (end_date IS NULL OR end_date > period_start)",
            "churned":     "end_date IS NOT NULL AND period_start <= end_date <= period_end",
        },
        "revenue_churn": {
            "formula":     "lost_mrr / mrr_at_period_start",
            "note":        "Customers with null MRR are excluded from both numerator and denominator",
        },
        "period_formats": ["YYYY (annual)", "YYYY-QN (quarterly)", "YYYY-MM (monthly)"],
        "edge_case_decisions": [
            "Downgrades: not logo churn; MRR delta captured in revenue churn only",
            "end_date == period_start: customer was active at start — NOT counted as churned",
            "Starts and churns in same period: excluded from denominator entirely",
            "Duplicate rows: deduplicated by customer_id (last row wins) before calculation",
            "Missing MRR: included in logo churn; excluded from revenue churn",
            "Null churn_reason: counted as churned regardless — reason is metadata, not a gate",
        ],
    }, indent=2)


@mcp.tool()
def explain_calculation(customer_id: str, period: str) -> str:
    """
    Explain in plain English why a specific customer is (or is not) counted as
    churned for the given period.

    customer_id: e.g. C0042
    period:      YYYY, YYYY-QN, or YYYY-MM
    """
    try:
        e = explain_customer(customer_id, period)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    return json.dumps({
        "customer_id":        e.customer_id,
        "period":             e.period,
        "counted_as_churned": e.counted_as_churned,
        "reason":             e.reason,
        "plan":               e.plan,
        "mrr":                e.mrr,
        "start_date":         str(e.start_date) if e.start_date else None,
        "end_date":           str(e.end_date)   if e.end_date   else None,
        "definition_version": e.definition_version,
    }, indent=2)


@mcp.tool()
def compare_periods(period_a: str, period_b: str) -> str:
    """
    Compare churn metrics between two periods and surface the delta.
    Useful for questions like "why was Q3 worse than Q2?"

    period_a: the baseline period (e.g. "2024-Q2")
    period_b: the comparison period (e.g. "2024-Q3")
    """
    try:
        a = calculate_churn(period_a)
        b = calculate_churn(period_b)
    except ValueError as exc:
        return json.dumps({"error": str(exc)})

    logo_delta    = b.logo_churn_rate    - a.logo_churn_rate
    revenue_delta = b.revenue_churn_rate - a.revenue_churn_rate
    mrr_delta     = b.mrr_at_start       - a.mrr_at_start

    def fmt(rate: float) -> str:
        return f"{rate * 100:.2f}%"

    def direction(delta: float) -> str:
        if delta > 0.001:  return "worse"
        if delta < -0.001: return "better"
        return "flat"

    return json.dumps({
        "baseline":  period_a,
        "comparison": period_b,
        "logo_churn": {
            "baseline":   fmt(a.logo_churn_rate),
            "comparison": fmt(b.logo_churn_rate),
            "delta_ppt":  f"{logo_delta * 100:+.2f}pp",
            "direction":  direction(logo_delta),
        },
        "revenue_churn": {
            "baseline":   fmt(a.revenue_churn_rate),
            "comparison": fmt(b.revenue_churn_rate),
            "delta_ppt":  f"{revenue_delta * 100:+.2f}pp",
            "direction":  direction(revenue_delta),
        },
        "mrr_at_start": {
            "baseline":   f"${a.mrr_at_start:,.0f}",
            "comparison": f"${b.mrr_at_start:,.0f}",
            "delta":      f"${mrr_delta:+,.0f}",
        },
        "definition_version": DEFINITION_VERSION,
    }, indent=2)


if __name__ == "__main__":
    mcp.run()
