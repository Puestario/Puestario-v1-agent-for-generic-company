#!/bin/bash
# Auto-refresh Zapier MCP OAuth token and update OpenClaw config
# Requires: CREDS_FILE and OPENCLAW_CONFIG set via env or defaults below

CREDS_FILE="${CREDS_FILE:-$HOME/.mcporter/credentials.json}"
OPENCLAW_CONFIG="${OPENCLAW_CONFIG:-$HOME/.openclaw/openclaw.json}"

REFRESH_TOKEN=$(python3 -c "
import json, sys
with open('$CREDS_FILE') as f:
    data = json.load(f)
entry = list(data['entries'].values())[0]
print(entry['tokens']['refresh_token'])
")

if [ -z "$REFRESH_TOKEN" ]; then
  echo "ERROR: Could not read refresh token from $CREDS_FILE"
  exit 1
fi

RESPONSE=$(curl -s -X POST "https://mcp.zapier.com/api/v1/oauth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=refresh_token" \
  --data-urlencode "refresh_token=$REFRESH_TOKEN")

NEW_ACCESS=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['access_token'])")
NEW_REFRESH=$(echo "$RESPONSE" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['refresh_token'])")

if [ -z "$NEW_ACCESS" ]; then
  echo "ERROR: Token refresh failed. Response: $RESPONSE"
  exit 1
fi

python3 -c "
import json
with open('$CREDS_FILE') as f:
    data = json.load(f)
entry = list(data['entries'].values())[0]
entry['tokens']['access_token'] = '$NEW_ACCESS'
entry['tokens']['refresh_token'] = '$NEW_REFRESH'
import datetime
entry['updatedAt'] = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')
with open('$CREDS_FILE', 'w') as f:
    json.dump(data, f, indent=2)
print('Credentials updated.')
"

python3 -c "
import json
try:
    with open('$OPENCLAW_CONFIG') as f:
        data = json.load(f)
    servers = data.get('mcp', {}).get('servers', {})
    if 'zapier' in servers:
        if 'headers' not in servers['zapier']:
            servers['zapier']['headers'] = {}
        servers['zapier']['headers']['Authorization'] = 'Bearer $NEW_ACCESS'
    with open('$OPENCLAW_CONFIG', 'w') as f:
        json.dump(data, f, indent=2)
    print('OpenClaw config updated.')
except Exception as e:
    print(f'Config update skipped: {e}')
"

echo "Zapier token refreshed at $(date)"
