#!/usr/bin/env bash
# run_all.sh - All-in-One Local Service Runner for Examiner Evaluation

echo "======================================================"
echo " Starting NHIOT Pipeline Services (All-in-One Mode)"
echo "======================================================"

# Function to clean up background processes on exit
cleanup() {
    echo ""
    echo "[!] Stopping all background services..."
    kill $(jobs -p) 2>/dev/null
    echo "[+] All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Activate virtual environment if present
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "[1/3] Launching Server Audit Daemon..."
python3 -m NHIOTSub.server_subscriber &
SERVER_PID=$!

echo "[2/3] Launching IoT Subscriber Daemon..."
python3 -m NHIOTSub.main &
IOT_PID=$!

echo "[3/3] Launching Examiner Web Dashboard..."
python3 web_dashboard.py &
WEB_PID=$!

echo "======================================================"
echo " All services running! (Server PID: $SERVER_PID, IoT PID: $IOT_PID, Web PID: $WEB_PID)"
echo " Examiner Web Portal: http://localhost:8000"
echo " Press Ctrl+C to stop all daemons."
echo "======================================================"

# Keep running and waiting for background jobs
wait

