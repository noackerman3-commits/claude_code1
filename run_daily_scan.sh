#!/bin/bash
# Daily rental scan wrapper - runs at 14:00 Jerusalem time (11:00 UTC)
# Captures all environment variables needed for proxy and playwright

export PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
export PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:36713}"
export HEX_CACERTS_PATH="${HEX_CACERTS_PATH:-/root/.ccr/ca-bundle.crt}"
export REQUESTS_CA_BUNDLE="${HEX_CACERTS_PATH:-/root/.ccr/ca-bundle.crt}"

PROJECT_DIR="/home/user/claude_code1"
LOG_FILE="$PROJECT_DIR/logs/daily_scan.log"
mkdir -p "$PROJECT_DIR/logs" "$PROJECT_DIR/data"

echo "=== Daily scan started at $(date) ===" >> "$LOG_FILE"
cd "$PROJECT_DIR" && /usr/local/bin/python3 run_scrape_now.py >> "$LOG_FILE" 2>&1
echo "=== Daily scan finished at $(date) ===" >> "$LOG_FILE"
