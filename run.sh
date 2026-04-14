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
if [ -n "${HR_CONFIG_STORAGE:-}" ]; then
    export SPARK_RUNTIME_DIR="${SPARK_RUNTIME_DIR:-${HR_CONFIG_STORAGE}/tmp/spark}"
    export SPARK_SEED_DB_PATH="${SPARK_SEED_DB_PATH:-${HR_CONFIG_STORAGE}/scripts/spark/seed/spark.db}"
else
    export SPARK_RUNTIME_DIR="${SPARK_RUNTIME_DIR:-$SCRIPT_DIR/spark_data}"
    export SPARK_SEED_DB_PATH="${SPARK_SEED_DB_PATH:-$SCRIPT_DIR/data/spark.db}"
fi
export SPARK_DB_PATH="${SPARK_DB_PATH:-$SPARK_RUNTIME_DIR/spark.db}"
mkdir -p "$(dirname "$SPARK_DB_PATH")"

if [ ! -f "$SPARK_DB_PATH" ] && [ -f "$SPARK_SEED_DB_PATH" ]; then
    cp "$SPARK_SEED_DB_PATH" "$SPARK_DB_PATH"
    echo "Seeded database from $SPARK_SEED_DB_PATH"
fi

# Port
PORT="${SPARK_PORT:-8588}"
SQLITE_WEB_PORT="${SPARK_SQLITE_WEB_PORT:-8589}"
LOG_LEVEL="${SPARK_LOG_LEVEL:-warning}"

echo "╔══════════════════════════════════════════════════════╗"
echo "║            SPARK v2 — Sophia Live Server             ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║  Database: $SPARK_DB_PATH"
echo "║  Server:   http://0.0.0.0:$PORT"
echo "║  Chat UI:  http://localhost:$PORT"
echo "║  SQLite:   http://localhost:$SQLITE_WEB_PORT"
echo "║                                                      ║"
echo "║  Press Ctrl+C to stop                                ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

if command -v sqlite_web >/dev/null 2>&1; then
    sqlite_web \
        --host 0.0.0.0 \
        --port "$SQLITE_WEB_PORT" \
        --no-browser \
        --quiet \
        --read-only \
        "$SPARK_DB_PATH" \
        >/tmp/spark-sqlite-web.log 2>&1 &
else
    echo "sqlite_web is not installed; database inspector disabled"
fi

exec python3.10  -m uvicorn src.runtime.spark_server:app \
    --host 0.0.0.0 \
    --port "$PORT" \
    --log-level "$LOG_LEVEL"
