# Zapier MCP Integration

## Status
Connect via Zapier MCP server (native OpenClaw integration).

## Setup
1. Get your Zapier MCP OAuth token from zapier.com/mcp
2. Add to OpenClaw config:
   ```json
   {
     "mcp": {
       "servers": {
         "zapier": {
           "baseUrl": "https://mcp.zapier.com/api/v1/connect",
           "transport": "streamable-http",
           "headers": {
             "Authorization": "Bearer YOUR_ZAPIER_OAUTH_TOKEN"
           }
         }
       }
     }
   }
   ```
3. Set up auto-refresh cron job using `core/scripts/zapier-token-refresh.sh`
   - Token expires every 60 min; refresh every 50 min to stay ahead
   - Store credentials at `~/.mcporter/credentials.json`

## Token Auto-Refresh
Cron job runs every 50 minutes via `core/scripts/zapier-token-refresh.sh`.
The script reads the refresh token from credentials, calls Zapier's token endpoint,
and updates both the credentials file and OpenClaw config automatically.

## Available MCP Tools
- `discover_zapier_actions` — search 9,000+ app actions
- `enable_zapier_action` — add an action to the MCP server
- `list_enabled_zapier_actions` — see what's active
- `execute_zapier_read_action` — run a read/fetch action
- `execute_zapier_write_action` — run a write/create/send action

## Recommended Apps to Enable
Customize this list based on your stack:
- Gmail — for email automation
- Google Sheets — for data logging
- GoHighLevel / LeadConnector — for CRM
- Trainerize / your fitness platform — for client management
- Slack — for team notifications
