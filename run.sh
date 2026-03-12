#!/bin/bash
# SPARK v2 — Run Script
# Starts the FastAPI server with drive system and chat UI
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Set PYTHONPATH so imports work
export PYTHONPATH="$SCRIPT_DIR:$PYTHONPATH"

# Database location
export SPARK_DB_PATH="${SPARK_DB_PATH:-$SCRIPT_DIR/spark_data/spark.db}"
mkdir -p "$(dirname "$SPARK_DB_PATH")"

# Port
PORT="${SPARK_PORT:-8080}"

echo "╔══════════════════════════════════════════════════════╗"
echo "║            SPARK v2 — Sophia Live Server             ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Database: $SPARK_DB_PATH"
echo "║  Server:   http://0.0.0.0:$PORT"
echo "║  Chat UI:  http://localhost:$PORT"
echo "║                                                      ║"
echo "║  Press Ctrl+C to stop                                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

exec python3.10  -m uvicorn src.runtime.spark_server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level info
