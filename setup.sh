#!/usr/bin/env bash
# One-command setup for the Churn Engine.
# Works on Mac, Linux, and Git Bash / WSL on Windows.
set -euo pipefail

REQUIRED_MAJOR=3
REQUIRED_MINOR=10

# ── 1. Find Python ──────────────────────────────────────────────────────────
PYTHON=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)

if [[ -z "$PYTHON" ]]; then
    echo "ERROR: Python not found. Install Python $REQUIRED_MAJOR.$REQUIRED_MINOR+ from https://www.python.org/downloads/"
    exit 1
fi

VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)

if (( MAJOR < REQUIRED_MAJOR || (MAJOR == REQUIRED_MAJOR && MINOR < REQUIRED_MINOR) )); then
    echo "ERROR: Python $REQUIRED_MAJOR.$REQUIRED_MINOR+ required, found $VERSION"
    echo "       Download: https://www.python.org/downloads/"
    exit 1
fi

echo "Python $VERSION found."

# ── 2. Virtual environment ───────────────────────────────────────────────────
if [[ ! -d ".venv" ]]; then
    echo "Creating virtual environment at .venv/ ..."
    "$PYTHON" -m venv .venv
fi

# Activate
if [[ -f ".venv/Scripts/activate" ]]; then
    source .venv/Scripts/activate   # Git Bash on Windows
else
    source .venv/bin/activate
fi

echo "Virtual environment active."

# ── 3. Install dependencies ──────────────────────────────────────────────────
echo "Installing dependencies from engine/requirements.txt ..."
pip install --quiet --upgrade pip
pip install --quiet -r engine/requirements.txt

echo "Dependencies installed."

# ── 4. Generate synthetic dataset ───────────────────────────────────────────
if [[ ! -f "data/subscriptions.csv" ]]; then
    echo "Generating synthetic dataset ..."
    python data/generate.py
    echo "Dataset generated at data/subscriptions.csv"
else
    echo "Dataset already exists at data/subscriptions.csv (skipping generation)"
fi

# ── 5. Smoke test ────────────────────────────────────────────────────────────
echo ""
echo "Running smoke test ..."
python -m pytest engine/tests/ -q --tb=short 2>&1 | tail -5

echo ""
echo "Setup complete."
echo ""
echo "Next steps:"
echo "  source .venv/bin/activate          # activate the venv (if not active)"
echo "  cd engine && uvicorn main:app --reload   # start the REST API"
echo "  python engine/mcp_server.py        # start the MCP server"
echo "  open presentation.html             # open the slideshow in a browser"
