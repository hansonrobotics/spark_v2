#!/bin/bash
# SPARK v2 — Standalone Installer
# Run: chmod +x install.sh && ./install.sh
set -e

echo "╔══════════════════════════════════════════════════════╗"
echo "║         SPARK v2 — Installer for Sophia             ║"
echo "║         Hanson Robotics, March 2026                  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Check Python
echo "[1/5] Checking Python..."
if command -v python3 &>/dev/null; then
    PY=$(command -v python3)
    PY_VER=$($PY --version 2>&1 | grep -oP '\d+\.\d+')
    echo "  Found: $PY ($PY_VER)"
    # Check version >= 3.11
    PY_MAJOR=$(echo $PY_VER | cut -d. -f1)
    PY_MINOR=$(echo $PY_VER | cut -d. -f2)
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
        echo "  WARNING: Python 3.11+ recommended (found $PY_VER)"
        echo "  The system may work on 3.9+ but is tested on 3.11+"
    fi
else
    echo "  ERROR: Python 3 not found. Install with: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi

# Create virtual environment
echo ""
echo "[2/5] Creating virtual environment..."
if [ ! -d "venv" ]; then
    $PY -m venv venv
    echo "  Created: venv/"
else
    echo "  Already exists: venv/"
fi
source venv/bin/activate

# Install dependencies
echo ""
echo "[3/5] Installing Python dependencies..."
pip install --upgrade pip -q
pip install fastapi uvicorn[standard] httpx aiosqlite -q
echo "  Installed: fastapi, uvicorn, httpx, aiosqlite"

# Optional: Anthropic SDK for LLM calls
echo ""
echo "[4/5] Optional: Anthropic API client..."
pip install anthropic -q 2>/dev/null && echo "  Installed: anthropic" || echo "  Skipped (not critical for testing)"

# Create data directory
echo ""
echo "[5/5] Creating data directory..."
mkdir -p spark_data
echo "  Created: spark_data/ (persistent TKG database will be stored here)"

# Verify
echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║              Installation Complete!                  ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║                                                      ║"
echo "║  To start SPARK:                                     ║"
echo "║    ./run.sh                                          ║"
echo "║                                                      ║"
echo "║  Then open:                                          ║"
echo "║    http://localhost:8080                              ║"
echo "║                                                      ║"
echo "║  Optional: Set API key for LLM responses:            ║"
echo "║    export ANTHROPIC_API_KEY=sk-ant-...                ║"
echo "║                                                      ║"
echo "║  For Vytas: read docs/DEVELOPMENT_PLAN.md            ║"
echo "║                                                      ║"
echo "╚══════════════════════════════════════════════════════╝"
