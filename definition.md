# Churn Metric Definition — v1.0

## Definition

**Logo churn rate** for a period is the number of customers whose subscription ended during that period divided by the number of customers active at the start of that period.

**Revenue churn rate** for a period is the sum of MRR lost from churned customers divided by the total MRR of customers active at the start of that period.

```
logo_churn_rate   = churned_customers / active_at_period_start
revenue_churn_rate = lost_mrr / mrr_at_period_start
```

---

## Key Terms

**Active at period start** — a customer whose `start_date` is on or before the first day of the period AND whose `end_date` is either null or strictly after the first day of the period.

**Churned during period** — a customer whose `end_date` falls within `[period_start, period_end]` (inclusive on both ends).

**Period** — one of:
- Monthly: `YYYY-MM` → first to last calendar day of that month
- Quarterly: `YYYY-QN` → Q1=Jan–Mar, Q2=Apr–Jun, Q3=Jul–Sep, Q4=Oct–Dec
- Annual: `YYYY` → Jan 1 – Dec 31

---

## Edge Cases & Boundary Decisions

| Situation | Decision | Rationale |
|---|---|---|
| Customer starts and churns within the same period | Not counted in denominator (not active at period start) | They never completed a full period |
| Customer downgrades (plan change, lower MRR) | Not counted as churned for logo churn; MRR delta counted for revenue churn | A downgrade is retention, not loss |
| `end_date` equals `period_start` exactly | Not churned in this period — they were active at start by one day | Favour counting customers, not losing them on boundary math |
| Duplicate rows (same customer_id + dates) | Deduplicated before calculation; only one row per customer_id is kept (last seen) | Data pipeline noise should not inflate denominators |
| Missing `mrr` | Customer included in logo churn; excluded from revenue churn denominator and numerator | We cannot impute revenue; we can count a customer |
| Churn reason null | Counted as churned regardless — reason is metadata, not a gate | Absence of reason ≠ absence of churn |

---

## Boundary Examples

Concrete input → output pairs that pin the definition's behavior at its edges. These are executable contracts — the scorecard and tests assert each one.

**Example 1 — Standard churn (expected: counted)**
```
customer_id=C001, start_date=2023-06-01, end_date=2024-02-15, mrr=149
period = 2024-Q1  (2024-01-01 to 2024-03-31)

active_at_start? YES  — start_date(2023-06-01) ≤ 2024-01-01, end_date(2024-02-15) > 2024-01-01
churned?         YES  — end_date(2024-02-15) within [2024-01-01, 2024-03-31]
logo churn:      counted   revenue churn: $149 lost
```

**Example 2 — Boundary date: end_date equals period_start (expected: NOT churned)**
```
customer_id=C002, start_date=2023-01-01, end_date=2024-01-01, mrr=149
period = 2024-Q1  (2024-01-01 to 2024-03-31)

active_at_start? NO   — end_date(2024-01-01) is NOT strictly > period_start(2024-01-01)
churned?         N/A  — not in denominator, cannot be in numerator
logo churn:      not counted   (this customer churned in the previous period)
```

**Example 3 — Starts and churns within same period (expected: NOT in denominator)**
```
customer_id=C003, start_date=2024-02-01, end_date=2024-03-15, mrr=49
period = 2024-Q1  (2024-01-01 to 2024-03-31)

active_at_start? NO   — start_date(2024-02-01) > period_start(2024-01-01)
churned?         N/A  — not in denominator
logo churn:      not counted   (never completed a full period)
```

**Example 4 — Active all period, never churns (expected: in denominator only)**
```
customer_id=C004, start_date=2022-03-01, end_date=null, mrr=499
period = 2024-Q1

active_at_start? YES  — start_date ≤ period_start, end_date is null
churned?         NO   — end_date is null
logo churn:      in denominator only   (retained customer)
```

**Example 5 — Missing MRR (expected: counted in logo, excluded from revenue)**
```
customer_id=C005, start_date=2023-01-01, end_date=2024-02-01, mrr=null
period = 2024-Q1

logo churn:    counted as churned (end_date within period)
revenue churn: excluded from both lost_mrr and mrr_at_start
               (cannot impute revenue; presence in logo is unaffected)
```

**Example 6 — Duplicate rows (expected: deduplicated to one)**
```
customer_id=C006, start_date=2023-01-01, end_date=2024-02-01 — appears twice
period = 2024-Q1

dedup: last row wins → treated as one customer
logo churn:    churned_count += 1  (not +=2)
               active_at_start += 1  (not +=2)
```

---

## What This Definition Does NOT Settle

These are open disagreements documented for the record:

- **Revised promised date vs. original committed date** — not applicable to SaaS but noted for cross-domain alignment.
- **Reactivations** — a customer who churns and re-subscribes within 30 calendar days: v1.0 counts the churn event. A "reactivation grace window" is deferred to v1.1.
- **Trial conversions** — free-trial customers are excluded from the denominator entirely (no `mrr` at start of trial). Paid-only scope.

---

## Definition Version

`definition_version: v1.0`
`effective_date: 2026-04-24`
