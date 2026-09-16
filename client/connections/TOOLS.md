# TOOLS.md - Connected Services

## OpenClaw MCP Tools
Available by default — no config needed:
- web_search, web_fetch, browser
- nodes, cron, message, gateway
- calendar, gmail, drive, docs, sheets, slides (requires Google auth)

---

## Meta Ads (Facebook/Instagram)

### Credentials
- Account Name: YOUR_META_ACCOUNT_NAME
- Account ID: YOUR_META_ACCOUNT_ID  (format: act_XXXXXXXXXXXXXXXXX)
- Access Token: YOUR_META_ACCESS_TOKEN
- API Version: v19.0
- Base URL: https://graph.facebook.com/v19.0/act_YOUR_META_ACCOUNT_ID

### Usage
- Always pass access_token as query param
- Campaigns: GET /campaigns?fields=name,status,objective,daily_budget,lifetime_budget
- Insights: GET /insights?fields=spend,impressions,clicks,ctr,cpc,actions&date_preset=last_7d

---

## GoHighLevel (GHL)

### Sub-Account 1 — YOUR_GHL_SUBACCOUNT_1_NAME
- API Key: YOUR_GHL_API_KEY_1
- Location ID: YOUR_GHL_LOCATION_ID_1
- Base URL: https://services.leadconnectorhq.com
- Auth header: `Authorization: Bearer YOUR_GHL_API_KEY_1`
- Version header: `Version: 2021-07-28`

### Calendar IDs (for appointment pulls)
- YOUR_CALENDAR_NAME: YOUR_CALENDAR_ID

---

## Stripe

### Credentials
- Secret Key: YOUR_STRIPE_SECRET_KEY  (format: sk_live_...)
- Base URL: https://api.stripe.com/v1
- Auth: HTTP Basic with secret key as username

### Common endpoints
- Charges: GET /v1/charges
- Customers: GET /v1/customers
- Subscriptions: GET /v1/subscriptions

---

## Make.com

### Account
- Region: YOUR_MAKE_REGION  (e.g. us2.make.com)
- Organization ID: YOUR_MAKE_ORG_ID
- Team ID: YOUR_MAKE_TEAM_ID
- API Key: YOUR_MAKE_API_KEY
- Base URL: https://YOUR_MAKE_REGION.make.com/api/v2
- Auth header: `Authorization: Token YOUR_MAKE_API_KEY`

---

## Zapier MCP

### Setup
- MCP server: https://mcp.zapier.com/api/v1/connect
- Transport: streamable-http
- Auth: Bearer token (OAuth — see client/connections/zapier-README.md for refresh setup)

---

## Google Ads

### Credentials
- Developer Token: YOUR_GOOGLE_ADS_DEVELOPER_TOKEN
- Client ID: YOUR_GOOGLE_ADS_CLIENT_ID
- Client Secret: YOUR_GOOGLE_ADS_CLIENT_SECRET
- Refresh Token: YOUR_GOOGLE_ADS_REFRESH_TOKEN
- Main Account ID: YOUR_GOOGLE_ADS_ACCOUNT_ID
- Manager Account ID: YOUR_GOOGLE_ADS_MANAGER_ID

---

## Asana

### Credentials
- Personal Access Token: YOUR_ASANA_PAT
- Auth header: `Authorization: Bearer YOUR_ASANA_PAT`
- Base URL: https://app.asana.com/api/1.0
- Workspace GID: YOUR_ASANA_WORKSPACE_GID
- Main project GID: YOUR_ASANA_PROJECT_GID

---

## Apify

### Credentials
- API Token: YOUR_APIFY_TOKEN
- Username: YOUR_APIFY_USERNAME
- Base URL: https://api.apify.com/v2
- Auth header: `Authorization: Bearer YOUR_APIFY_TOKEN`

---

## Consensus (research API)

### Credentials
- API Key: YOUR_CONSENSUS_API_KEY
- Base URL: https://api.consensus.app/v1
- Auth header: `Authorization: Bearer YOUR_CONSENSUS_API_KEY`

### Usage
- Search peer-reviewed studies by topic/query
- Use for health/wellness/science content research
