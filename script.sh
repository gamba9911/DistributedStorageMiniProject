#!/usr/bin/env bash
set -euo pipefail

N="${1:-6}"
BASE_PORT="${DSM_BASE_PORT:-6000}"
HOST="${DSM_HOST:-127.0.0.1}"
PYTHON_BIN="${PYTHON_BIN:-python}"

echo "Starting DSM with N=$N nodes (ports $BASE_PORT..$((BASE_PORT + N - 1)))"

# Start nodes
for ((i=0; i<N; i++)); do
  PORT=$((BASE_PORT + i))
  echo "  Node $i -> $HOST:$PORT"
  "$PYTHON_BIN" node.py --id "$i" --port "$PORT" &
done

# Export so the lead knows how many nodes exist
export DSM_NODES="$N"
export DSM_BASE_PORT="$BASE_PORT"
export DSM_HOST="$HOST"
echo "Starting lead node (Web API on port 5000)..."
$PYTHON_BIN demo.py &

echo ""
echo "========================================"
echo "🚀 All nodes running in background!"
echo "Lead/API available at: http://localhost:5000/"
echo ""
echo "Use Postman to:"
echo "  POST -> http://localhost:5000/store"
echo "  GET  -> http://localhost:5000/retrieve/<object_id>"
echo "  GET  -> http://localhost:5000/placement/<object_id>"
echo "========================================"
echo ""
