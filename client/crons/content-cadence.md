# Content Cadence — Scheduled Cron Jobs

## Active Jobs

### Daily Content Brief
- **Schedule:** Daily at YOUR_CONTENT_BRIEF_TIME (your timezone)
- **Job ID:** [set by cron tool on creation — never invent]
- **What it does:** Runs morning content research brief for the day's posting plan
- **Delivery:** WhatsApp to both owners

### Weekly Report
- **Schedule:** Every Monday at YOUR_WEEKLY_REPORT_TIME
- **Job ID:** [set by cron tool on creation — never invent]
- **What it does:** Aggregates week's performance data — ads, revenue, leads
- **Delivery:** WhatsApp to both owners

### Zapier Token Refresh
- **Schedule:** Every 50 minutes
- **Job ID:** [set by cron tool on creation — never invent]
- **What it does:** Runs core/scripts/zapier-token-refresh.sh to stay ahead of OAuth expiry
- **Delivery:** Silent (logs only)

---

## Adding a New Job

1. Tell the agent to create it — never create cron entries in this file manually
2. Agent calls the cron tool and gets a real job ID
3. Agent verifies with cron list
4. Agent updates this file with the confirmed job ID
5. Never proceed without a confirmed ID from the tool

---

## Retired / Inactive Jobs

Document retired jobs here with the reason, so you don't re-create them accidentally.
