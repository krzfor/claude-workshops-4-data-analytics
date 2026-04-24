# Environment Setup

## Prerequisites

| Dependency | Minimum | Notes |
|---|---|---|
| Python | 3.10 | 3.11 or 3.12 recommended; pydantic v2 + pandas 2 behave best here |
| pip | bundled with Python | upgrade with `pip install --upgrade pip` if needed |
| Node / npm | **not required** | `presentation.html` is standalone — no build step |
| Docker | not required | everything runs locally via pip |

**Verify your Python version:**
```bash
python --version   # or: python3 --version
```

---

## Quick start (one command)

```bash
bash setup.sh
```

This script will:
1. Check Python ≥ 3.10 is available
2. Create a virtual environment at `.venv/`
3. Install all pip dependencies from `engine/requirements.txt`
4. Generate the synthetic dataset at `data/subscriptions.csv`

---

## Manual setup (step by step)

**1. Create and activate a virtual environment:**
```bash
python -m venv .venv

# Mac / Linux / Git Bash on Windows:
source .venv/bin/activate

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (CMD):
.venv\Scripts\activate.bat
```

**2. Install Python dependencies:**
```bash
pip install -r engine/requirements.txt
```

**3. Generate the synthetic dataset:**
```bash
python data/generate.py
```
This produces `data/subscriptions.csv` (510 rows, seed=42 — deterministic).

---

## Python packages installed

| Package | Version | Purpose |
|---|---|---|
| fastapi | ≥0.110.0 | REST API framework |
| uvicorn[standard] | ≥0.29.0 | ASGI server |
| pandas | ≥2.0.0 | data manipulation in the calculation engine |
| pydantic | ≥2.0.0 | request/response validation |
| pytest | ≥8.0.0 | test runner (48 tests) |
| httpx | ≥0.27.0 | async HTTP client used by FastAPI TestClient |
| mcp | ≥1.0.0 | Model Context Protocol — MCP server |

---

## Verify the setup

Run the full test suite (should show 48 tests passing + scorecard report):
```bash
python -m pytest engine/tests/ -v -s
```

Expected output at the end:
```
====================================================
  CHURN ENGINE — SCORECARD REPORT
====================================================
  Accuracy              100%  (6/6 golden questions)
  Refusal accuracy      100%  (5/5 invalid inputs rejected)
  False-confidence rate 0%   (0/5 traps triggered)
====================================================
  No false-confidence failures. Engine is safe to trust.
====================================================
```

---

## Start the services

**REST API:**
```bash
cd engine && uvicorn main:app --reload
```
Swagger UI at `http://localhost:8000/docs`

**MCP server:**
```bash
python engine/mcp_server.py
```
Register in `.claude/settings.json` — the full config block is in the `engine/mcp_server.py` file header.

**Presentation:**
Double-click `presentation.html` — opens in any browser, no server needed.

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'mcp'`**
The `mcp` package requires Python 3.10+. Confirm version and reinstall:
```bash
python --version
pip install "mcp>=1.0.0"
```

**`FileNotFoundError: data/subscriptions.csv`**
The CSV is not committed — generate it:
```bash
python data/generate.py
```

**Tests fail with import errors**
Make sure you're running pytest from the repo root, not from inside `engine/`:
```bash
# correct:
python -m pytest engine/tests/ -v -s

# wrong (will break sys.path):
cd engine && pytest tests/
```
