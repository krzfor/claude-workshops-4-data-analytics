# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## First-time setup

**At the start of every new session, display this block to the user:**

```
Fresh environment? Run this once:
  bash setup.sh

This installs all Python dependencies, creates a .venv/, and generates the dataset.
Full details in SETUP.md. Requires Python 3.10+.
```

If `data/subscriptions.csv` is missing or `.venv/` does not exist, remind the user to run `bash setup.sh` before anything else.

## What this is

Workshop scenario: a SaaS churn metric engine. The scenario premise is "40 dashboards, one metric, four answers" — the goal is to produce a single authoritative churn calculation with a versioned definition, replacing ad-hoc dashboard logic. See `04-data-analytics.md` for the full brief and `definition.md` for the active metric definition (v1.0).

## Conventions taught to Claude

- **Never change calculation logic without updating `definition.md` and bumping `DEFINITION_VERSION` together.** Use `/bump-definition` to do both atomically.
- **Never add a new edge-case decision without a corresponding false-confidence trap in `test_scorecard.py`.** Prose in `definition.md` is not enough — the trap makes it executable.
- **Deduplication belongs in the calculation layer, not the load layer.** This lets tests mock `_load()` freely while still exercising dedup. Do not move it back to `_load()`.
- **All test data is provided via `_patch()` / `patch.object(churn, "_load", ...)`.** Tests never read from `data/subscriptions.csv` — that file is for the running engine only.
- **Skills vs commands distinction:** skills (`.claude/skills/`) capture multi-step workflows that require judgment; commands are one-shot playbook runs. `/bump-definition` is a skill because it requires asking what changed and verifying consistency. A simple `pytest` run is a command.

## Commands

**Generate synthetic data:**
```bash
python data/generate.py
```

**Run all tests:**
```bash
python -m pytest engine/tests/ -v -s
```

**Run a single test file:**
```bash
python -m pytest engine/tests/test_churn.py -v    # calculation logic (14)
python -m pytest engine/tests/test_api.py -v       # HTTP layer (17)
python -m pytest engine/tests/test_scorecard.py -v -s  # scorecard report (17)
```

**Run a single test:**
```bash
python -m pytest engine/tests/test_churn.py::test_logo_churn_basic -v
```

**Start the API server** (run from `engine/`):
```bash
cd engine
uvicorn main:app --reload
```
Interactive docs at `http://localhost:8000/docs`.

**First-time environment setup** (installs deps, creates `.venv/`, generates dataset):
```bash
bash setup.sh
```
Full dependency details (Python version, package table, troubleshooting) in `SETUP.md`.

## Architecture

The codebase has three layers:

**`data/`** — data generation only. `generate.py` produces `subscriptions.csv` with intentional noise: duplicates, null MRR, mislabelled plan names (`Pro`, `STARTER`, `starter_v1`), and a `source_system` column where `legacy` rows have a +1 day UTC+2 timezone artifact on `end_date`. Re-running regenerates deterministically (seed=42). `_load()` in `churn.py` normalises all of this before any calculation.

**`engine/churn.py`** — pure calculation logic with no HTTP concerns. Two public functions: `calculate_churn(period)` and `explain_customer(customer_id, period)`. Both call `_dedup(_load())` at entry — deduplication happens at calculation time, not at load time, so tests can mock `_load` and still exercise the dedup path. `parse_period()` accepts `YYYY`, `YYYY-QN`, and `YYYY-MM` formats.

**`engine/main.py`** — thin FastAPI layer. Three endpoints: `GET /churn`, `GET /churn/explain`, `GET /definitions`. Responses always include `definition_version` so results are traceable to the exact definition that produced them.

**`engine/mcp_server.py`** — MCP server exposing four tools: `get_metric`, `list_definitions`, `explain_calculation`, `compare_periods`. Run with `python engine/mcp_server.py`. Registration config is in the file header. Requires `mcp>=1.0.0`.

**`presentation.html`** — standalone 8-slide slideshow. Opens directly in a browser (no server). All chart data is hardcoded from a one-time engine run — if the dataset is regenerated, re-run the calculation and update the hardcoded values in the two `Chart(...)` calls at the bottom of the file. Navigate with arrow keys or on-screen buttons.

**`definition.md`** — the metric definition is the source of truth. Every edge case decision (boundary dates, missing MRR, duplicates) is documented there with rationale. When changing calculation logic, update `definition.md` and bump `DEFINITION_VERSION` in `churn.py` together.

## Custom skills

Three project-level skills are available (`.claude/skills/`). Invoke them with a slash command:

| Skill | Command | What it does |
|---|---|---|
| churn-report | `/churn-report` | Runs the calculation engine for a period and outputs a formatted report with a benchmark interpretation |
| reconcile | `/reconcile` | Scaffolds a reconciliation table comparing v1.0 against up to four alternative definitions — the artifact for Challenge 6 |
| bump-definition | `/bump-definition` | Updates `DEFINITION_VERSION` in `churn.py` and `definition.md` together, with a changelog entry, keeping them in sync |

## Key invariants

- **Deduplication**: `_dedup()` keeps the last row per `customer_id`. This must run before any calculation to prevent duplicate rows from inflating denominators.
- **Boundary rule**: a customer whose `end_date` equals `period_start` is considered active at period start (not churned). This is intentional — see `definition.md`.
- **Missing MRR**: customers with null MRR count toward logo churn but are excluded from revenue churn numerator and denominator. Tests in `test_missing_mrr_excluded_from_revenue` cover this.
- **`definition_version`** is defined once in `churn.py` (`DEFINITION_VERSION = "v1.0"`) and flows through to every response. Do not hardcode it elsewhere.
- **Data cleaning** happens in `_load()`, not in calculation functions. Plan names are normalised (strip + lower + drop `_vN` suffix). Legacy-source `end_date` values are shifted back by 1 day to undo the UTC+2 export artifact. Tests mock `_load()` so they are unaffected by these transformations.
- **Scorecard thresholds**: accuracy and refusal accuracy must be 100%; false-confidence rate must be 0%. Any regression that breaks an edge-case invariant will trip a false-confidence trap before it reaches production.
