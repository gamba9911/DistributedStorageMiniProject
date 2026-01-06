#!/usr/bin/env bash
PYTHON_BIN="python"

echo "Starting storage nodes..."
for i in 0 1 2 3 4 5; do
    PORT=$((6000 + i))
    echo "  Node $i → port $PORT"
    $PYTHON_BIN node.py --id $i --port $PORT &
done

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
echo "💡 To stop all processes:"
echo "   pkill -f node.py"
echo "   pkill -f demo.py"
echo "========================================"
