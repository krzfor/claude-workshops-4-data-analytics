---
name: reconcile
description: Scaffold a reconciliation table comparing the v1.0 churn definition against up to four alternative definitions. This is Challenge 6 from the scenario brief.
---

Build a reconciliation table that shows how different churn definitions handle each edge case. This is the artifact that "wins the room" — it makes disagreements concrete and forces a decision.

## Steps

1. Read `definition.md` to get the current edge cases and the v1.0 decisions.

2. Ask the user which alternative definitions to compare against. Offer these defaults if they don't specify:
   - **Def A** — Logo churn, but downgrades count as full churn
   - **Def B** — Revenue churn only, 30-day reactivation grace window
   - **Def C** — Logo churn, end_date == period_start counts as churned (opposite boundary)
   - **Def D** — Cohort-based: churned / customers who ever existed (not just active at start)

3. For each edge case row from `definition.md`, determine what each definition returns. Use these edge case rows as a starting point — add more if the user's chosen definitions introduce new ones:
   - Customer starts and churns in the same period
   - Customer downgrades (MRR decreases, no cancellation)
   - end_date equals period_start exactly
   - Duplicate rows for the same customer
   - Missing MRR value
   - Null churn_reason
   - Customer reactivates within 30 days of churning

4. Write the reconciliation table to a new file `reconciliation.md` in the repo root using this format:

```markdown
# Churn Definition Reconciliation

| Edge case | v1.0 (ours) | Def A | Def B | Def C | Def D |
|-----------|-------------|-------|-------|-------|-------|
| ...       | ...         | ...   | ...   | ...   | ...   |

## Differences that change the number most

List the 2–3 edge cases where definitions diverge most, and estimate the directional impact on the final rate (higher / lower).

## Recommendation

Which definition should win and why. One paragraph.
```

5. Report back with a summary of the largest divergences found.
