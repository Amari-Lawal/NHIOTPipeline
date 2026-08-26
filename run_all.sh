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
    rm -f .tunnel.log
    echo "[+] All services stopped."
    exit 0
}
trap cleanup SIGINT SIGTERM EXIT

# Determine python executable
if [ -f "venv/bin/python3" ]; then
    PYTHON_BIN="venv/bin/python3"
elif [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_BIN="$VIRTUAL_ENV/bin/python3"
else
    PYTHON_BIN="python3"
fi

echo "[1/4] Launching Server Audit Daemon..."
$PYTHON_BIN -m NHIOTSub.server_subscriber &
SERVER_PID=$!

echo "[2/4] Launching IoT Subscriber Daemon..."
$PYTHON_BIN -m NHIOTSub.main &
IOT_PID=$!

echo "[3/4] Launching Examiner Web Dashboard..."
$PYTHON_BIN web_dashboard.py &
WEB_PID=$!

# Locate ngrok binary
if command -v ngrok &> /dev/null; then
    NGROK_BIN="ngrok"
elif [ -x "$HOME/.local/bin/ngrok" ]; then
    NGROK_BIN="$HOME/.local/bin/ngrok"
else
    NGROK_BIN=""
fi

if [ -n "$NGROK_BIN" ]; then
    # Load .env if present
    if [ -f .env ]; then
        set -a
        source .env
        set +a
    fi
    NGROK_DOMAIN="${NGROK_DOMAIN:-delay-gusty-purity.ngrok-free.dev}"
    if [ -n "$NGROK_AUTHTOKEN" ]; then
        $NGROK_BIN config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
    fi

    echo "[4/4] Launching ngrok Tunnel on Port 7000 (URL: https://${NGROK_DOMAIN})..."
    rm -f .tunnel.log .tunnel_url
    $NGROK_BIN http 7000 --url "https://${NGROK_DOMAIN}" --log=stdout > .tunnel.log 2>&1 &
    TUNNEL_PID=$!
    echo "https://${NGROK_DOMAIN}" > .tunnel_url

    echo ""
    echo "======================================================"
    echo " 🚀 PUBLIC NGROK DASHBOARD URL: https://${NGROK_DOMAIN}"
    echo " (Saved to .tunnel_url for quick reference: cat .tunnel_url)"
    echo "======================================================"
    echo ""
elif command -v cloudflared &> /dev/null; then
    echo "[4/4] Launching Cloudflare Quick Tunnel on Port 7000..."
    rm -f .tunnel.log .tunnel_url
    cloudflared tunnel --url http://localhost:7000 2>&1 | tee .tunnel.log &
    TUNNEL_PID=$!

    # Helper subshell to capture and highlight the URL as soon as Cloudflare connects
    (
        for i in {1..30}; do
            if [ -f .tunnel.log ]; then
                URL=$(grep -o 'https://[-a-zA-Z0-9]\+\.trycloudflare\.com' .tunnel.log | head -n 1)
                if [ -n "$URL" ]; then
                    echo "$URL" > .tunnel_url
                    echo ""
                    echo "======================================================"
                    echo " 🚀 PUBLIC CLOUDFLARE DASHBOARD URL: $URL"
                    echo " (Saved to .tunnel_url for quick reference: cat .tunnel_url)"
                    echo "======================================================"
                    echo ""
                    break
                fi
            fi
            sleep 0.5
        done
    ) &
else
    echo "[!] Tunnel binary (ngrok / cloudflared) not found. Tunnel skipped."
    TUNNEL_PID="N/A"
fi

echo "======================================================"
echo " All services running! (Server PID: $SERVER_PID, IoT PID: $IOT_PID, Web PID: $WEB_PID, Tunnel PID: $TUNNEL_PID)"
echo " Local Web Portal: http://localhost:7000"
echo " Live logs streaming below..."
echo " Press Ctrl+C to stop all daemons."
echo "======================================================"

# Keep running and waiting for background jobs
wait

