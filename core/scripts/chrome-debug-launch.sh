#!/bin/bash
# Launch Chrome with remote debugging enabled
# Useful for browser automation via OpenClaw

pkill -f "Google Chrome" 2>/dev/null
sleep 2
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --profile-directory=Default \
  --no-first-run &
sleep 4
echo "Chrome launched with remote debugging on port 9222"
