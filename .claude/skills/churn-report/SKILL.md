---
name: churn-report
description: Calculate and display a formatted churn report for a given period using the engine in this repo.
---

Generate a churn report for this SaaS project by running the calculation engine directly.

## Steps

1. If the user provided a period in their message (e.g. "2024-Q4", "2024-01", "2024"), use it. Otherwise ask: "Which period? (YYYY, YYYY-QN, or YYYY-MM)"

2. Run the calculation by executing this Python snippet from the repo root:

```python
import sys
sys.path.insert(0, 'engine')
from churn import calculate_churn, explain_customer
r = calculate_churn('<PERIOD>')
print(f"period={r.period}")
print(f"active_at_start={r.active_at_start}")
print(f"churned_count={r.churned_count}")
print(f"logo_churn_rate={r.logo_churn_rate}")
print(f"mrr_at_start={r.mrr_at_start}")
print(f"lost_mrr={r.lost_mrr}")
print(f"revenue_churn_rate={r.revenue_churn_rate}")
print(f"definition_version={r.definition_version}")
```

3. Present the results as a clean markdown report in this format:

```
## Churn Report — <PERIOD>
Definition: <definition_version>

| Metric              | Value       |
|---------------------|-------------|
| Active at start     | <n>         |
| Churned             | <n>         |
| Logo churn rate     | <X.XX%>     |
| MRR at start        | $<amount>   |
| Lost MRR            | $<amount>   |
| Revenue churn rate  | <X.XX%>     |
```

4. After the table, add one sentence of plain-English interpretation — e.g. whether the rate is high, low, or typical for SaaS benchmarks (roughly: <2% monthly logo churn is healthy, 2–5% is elevated, >5% is critical).
