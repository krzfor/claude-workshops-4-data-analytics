import pandas as pd
import numpy as np
from datetime import date, timedelta
import random
import os

random.seed(42)
np.random.seed(42)

PLANS = {"starter": 49, "pro": 149, "enterprise": 499}
PLAN_NAMES = list(PLANS.keys())
PLAN_WEIGHTS = [0.5, 0.35, 0.15]

# Mislabelled variants found in real exports — engine must normalise these
PLAN_NOISE = {
    "starter":    ["Starter", "STARTER", "starter_v1"],
    "pro":        ["Pro", "PRO", "pro "],
    "enterprise": ["Enterprise", "ENTERPRISE", "enterprise_v2"],
}

START_MIN = date(2022, 1, 1)
START_MAX = date(2024, 6, 30)
DATA_CEILING = date(2025, 3, 31)

# Source systems — legacy exports carry a UTC+2 timezone offset on end_date
SOURCE_SYSTEMS = ["crm", "crm", "crm", "crm", "crm", "crm", "crm", "billing", "billing", "legacy"]

records = []
for i in range(1, 501):
    plan = random.choices(PLAN_NAMES, weights=PLAN_WEIGHTS)[0]
    mrr = PLANS[plan] + random.randint(-5, 5)

    start_offset = random.randint(0, (START_MAX - START_MIN).days)
    start_date = START_MIN + timedelta(days=start_offset)

    churned = random.random() < 0.35
    end_date = None
    churn_reason = None

    if churned:
        tenure = random.randint(30, 730)
        end_date = min(start_date + timedelta(days=tenure), DATA_CEILING)
        churn_reason = random.choices(
            ["voluntary", "involuntary", None], weights=[0.6, 0.3, 0.1]
        )[0]

    source = random.choice(SOURCE_SYSTEMS)

    # Legacy source: dates exported in UTC+2 — end_date is shifted +1 day
    if source == "legacy" and end_date is not None:
        end_date = min(end_date + timedelta(days=1), DATA_CEILING)

    # Mislabelled plan names (~3% of rows)
    display_plan = plan
    if random.random() < 0.03:
        display_plan = random.choice(PLAN_NOISE[plan])

    records.append({
        "customer_id": f"C{i:04d}",
        "plan": display_plan,
        "mrr": mrr,
        "start_date": start_date,
        "end_date": end_date,
        "churn_reason": churn_reason,
        "source_system": source,
    })

# realistic noise: 10 duplicate rows
for _ in range(10):
    records.append(random.choice(records).copy())

# realistic noise: 5 rows with missing mrr
for idx in random.sample(range(len(records)), 5):
    records[idx]["mrr"] = None

df = pd.DataFrame(records)

out = os.path.join(os.path.dirname(__file__), "subscriptions.csv")
df.to_csv(out, index=False)
print(f"Generated {len(df)} rows -> {out}")
print(f"  source breakdown: {df['source_system'].value_counts().to_dict()}")
print(f"  plan noise rows:  {df['plan'].str.contains('[A-Z _]', regex=True).sum()}")
