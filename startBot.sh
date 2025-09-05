#!/bin/bash
# start-dev.sh

# Start your webhook listener in background
python3 main.py &
WEBHOOK_PID=$!

# Start localtunnel
lt --port 8000 --subdomain pr-doc-bot

# Cleanup when you press Ctrl+C
trap "kill $WEBHOOK_PID" EXIT
