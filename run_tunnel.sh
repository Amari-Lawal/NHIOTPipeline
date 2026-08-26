#!/usr/bin/env bash
# run_tunnel.sh - Launch an ngrok Tunnel for the NHIOT Web Dashboard

PORT="${PORT:-7000}"

# Load .env variables if present
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

NGROK_DOMAIN="${NGROK_DOMAIN:-delay-gusty-purity.ngrok-free.dev}"

# Locate ngrok binary
if command -v ngrok &> /dev/null; then
    NGROK_BIN="ngrok"
elif [ -x "$HOME/.local/bin/ngrok" ]; then
    NGROK_BIN="$HOME/.local/bin/ngrok"
else
    echo "[!] ngrok binary not found in PATH or ~/.local/bin/ngrok"
    exit 1
fi

# Ensure authtoken is configured
if [ -n "$NGROK_AUTHTOKEN" ]; then
    $NGROK_BIN config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 || true
fi

echo "======================================================"
echo " 🌐 Starting ngrok Static Public Tunnel on Port ${PORT}"
echo " 🔗 Public URL: https://${NGROK_DOMAIN}"
echo "======================================================"
echo "Press Ctrl+C to stop the tunnel."
echo "======================================================"
echo ""

$NGROK_BIN http "${PORT}" --url "https://${NGROK_DOMAIN}"
