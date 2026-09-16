# PLACEHOLDERS.md

Every placeholder in this template, what it is, where to get it, and every file
it appears in. Paths are complete — nothing here is truncated.

**64 placeholders** in the base install. `extras/` carries **23** more; they are listed at the end, counted separately, and only matter if you copy that piece in.

Two checks. Both must come back empty when the install is finished:

```bash
grep -rn "YOUR_" . --exclude-dir=.git --exclude-dir=extras --exclude=PLACEHOLDERS.md --exclude=START-HERE.md
grep -rn "YOUR_" core/ | grep -v core/config/systems.md
```

`python3 tests/ci_checks.py placeholders` confirms this file against the tree:
the count in the header, the count in SETUP.md, every row's paths, and that
no placeholder in the tree is missing a row. CI runs it on every push.

The second one matters: `core/rules/` must contain **no placeholders at all**.
The only file inside `core/` that is ever edited is `core/config/systems.md`.
If a name or a number turns up in `core/rules/` or `core/config/`, something was
pasted in that should not have been. `tests/ci_checks.py core-rules` checks for
that too: the owners' names and numbers live in `client/`, never in `core/`.

---

## Identity

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_AGENT_EMOJI` | One emoji the agent signs with. | You choose it. | `client/identity/IDENTITY.md` <br> `client/identity/USER.md` |
| `YOUR_AGENT_ID` | Lowercase id used in config and session keys. | You choose it. Lowercase, no spaces. | `client/scripts/ventas_report_check.py` |
| `YOUR_AGENT_NAME` | The agent's name. Appears in every reply. | You choose it. | `client/identity/IDENTITY.md` <br> `client/identity/SOUL.md` <br> `client/identity/USER.md` |
| `YOUR_AGENT_WHATSAPP` | The agent's own WhatsApp number, if it gets a separate line. | The number you dedicate to it. Optional. | `client/identity/MEMORY.md` |
| `YOUR_BUSINESS_NAME` | Trading name of the business. | The owner. | `client/identity/MEMORY.md` <br> `client/identity/SOUL.md` <br> `client/identity/USER.md` <br> `extras/agents/ad-architect/AGENTS.md` <br> `extras/agents/industry-researcher/AGENTS.md` <br> `extras/agents/operator/AGENTS.md` <br> `extras/agents/researcher/AGENTS.md` |
| `YOUR_CITY` | City the business operates from. | The owner. | `client/identity/MEMORY.md` <br> `client/identity/USER.md` |
| `YOUR_STATE` | State or region. | The owner. | `client/identity/MEMORY.md` <br> `client/identity/USER.md` |
| `YOUR_TIMEZONE` | IANA timezone, e.g. America/New_York. | `date +%Z` on the machine, or timeanddate.com. | `client/identity/USER.md` |

## Owner, contacts and authority

The two owners, Coach Lalo and Mateo Arbelaez, are named in
`client/identity/OWNER.md`. Their WhatsApp numbers and emails are placeholders,
filled in per install, together with any staff contact.

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_DIRECT_CHAT_LANGUAGE` | Language for 1:1 chat with the owner. | The owner. | `client/identity/USER.md` |
| `YOUR_GROUP_CHAT_LANGUAGE` | Language for group chats. | The owner. | `client/identity/USER.md` |
| `YOUR_OWNER_EMAIL` | Coach Lalo's email. | Coach Lalo. | `client/identity/MEMORY.md` <br> `client/identity/OWNER.md` <br> `client/identity/USER.md` <br> `client/operating/HEARTBEAT.md` |
| `YOUR_OWNER_WHATSAPP` | Coach Lalo's WhatsApp number, E.164 (e.g. +13055550100). This number is an owner to the agent. | Coach Lalo's phone. Confirm it in the room. | `SETUP.md` <br> `client/identity/MEMORY.md` <br> `client/identity/OWNER.md` <br> `client/identity/USER.md` <br> `client/memory/decisions.jsonl` <br> `client/operating/AGENTS.md` |
| `YOUR_OWNER_2_WHATSAPP` | Mateo's WhatsApp number, E.164. This number is an owner to the agent. | Mateo's phone. Confirm it in the room. | `SETUP.md` <br> `client/identity/MEMORY.md` <br> `client/identity/OWNER.md` <br> `client/identity/USER.md` <br> `client/memory/decisions.jsonl` <br> `client/operating/AGENTS.md` |
| `YOUR_OWNER_2_EMAIL` | Mateo's email. | Mateo. | `client/identity/MEMORY.md` <br> `client/identity/OWNER.md` <br> `client/identity/USER.md` <br> `client/operating/HEARTBEAT.md` |
| `YOUR_SECONDARY_CONTACT_NAME` | A staff member who may give the agent work. Not an owner. | The owners. Optional. | `client/identity/OWNER.md` <br> `client/identity/USER.md` |
| `YOUR_SECONDARY_CONTACT_SCOPE` | What they decide without asking an owner. | The owners. Be specific. | `client/identity/OWNER.md` <br> `client/identity/USER.md` |
| `YOUR_SECONDARY_CONTACT_WHATSAPP` | Their WhatsApp, E.164. | Them. | `client/identity/OWNER.md` <br> `client/identity/USER.md` |

## Systems the rules name

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_CRM_SYSTEM` | CRM name, e.g. GoHighLevel. | Whatever holds the contacts. | `JOB-CARD.md` <br> `SETUP.md` <br> `core/config/systems.md` |
| `YOUR_PAYMENT_SYSTEM` | Payment system name, e.g. Stripe. | Whatever actually takes the money. | `JOB-CARD.md` <br> `SETUP.md` <br> `core/config/systems.md` |

## Models

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_FALLBACK_MODELS` | Ordered fallback model ids. | Same list. Verify every one. | `client/operating/AGENTS.md` |
| `YOUR_PRIMARY_MODEL` | Model id the agent runs on. | The provider's CURRENT model list. Verify it resolves. | `client/operating/AGENTS.md` |

## Schedule

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_CONTENT_BRIEF_TIME` | Time the daily content brief runs. | The owner. | `client/crons/content-cadence.md` |
| `YOUR_DAILY_REPORT_TIME` | Time the daily report heartbeat runs. | The owner. | `client/operating/AGENTS.md` |
| `YOUR_QUIET_HOURS_END` | End of quiet hours. | The owner. | `client/operating/HEARTBEAT.md` |
| `YOUR_QUIET_HOURS_START` | Start of quiet hours. Agent stays silent. | The owner. | `client/operating/HEARTBEAT.md` |
| `YOUR_RECURRING_EVENTS` | Calendar events the agent watches for. | The owner's calendar. | `client/operating/HEARTBEAT.md` |
| `YOUR_WEEKLY_REPORT_TIME` | Time the weekly report cron runs. | The owner. | `client/crons/content-cadence.md` |

## Ad platforms

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_GOOGLE_ADS_ACCOUNT_ID` | Google Ads account id, 10 digits. | Google Ads → top-right account picker. | `client/connections/TOOLS.md` |
| `YOUR_GOOGLE_ADS_CLIENT_ID` | OAuth client id. | Google Cloud Console → Credentials → OAuth client. | `client/connections/TOOLS.md` |
| `YOUR_GOOGLE_ADS_CLIENT_SECRET` | OAuth client secret. | Same screen as the client id. | `client/connections/TOOLS.md` |
| `YOUR_GOOGLE_ADS_DEVELOPER_TOKEN` | Developer token for the Ads API. | Google Ads API Center. Needs approval, allow days. | `client/connections/TOOLS.md` |
| `YOUR_GOOGLE_ADS_MANAGER_ID` | Manager (MCC) account id above it. | Google Ads Manager account, top right. | `client/connections/TOOLS.md` |
| `YOUR_GOOGLE_ADS_REFRESH_TOKEN` | Long-lived OAuth refresh token. | Generated once via the OAuth consent flow. | `client/connections/TOOLS.md` |
| `YOUR_META_ACCESS_TOKEN` | Meta Ads long-lived access token. | Meta Business → System Users → Generate token. | `client/connections/TOOLS.md` |
| `YOUR_META_ACCOUNT_ID` | Meta ad account, act_… . | Meta Ads Manager, account picker top-left. | `client/connections/TOOLS.md` |
| `YOUR_META_ACCOUNT_NAME` | Label for the ad account. | You choose it. | `client/connections/TOOLS.md` |

## CRM and payments

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_CALENDAR_ID` | CRM calendar id for appointment pulls. | GHL → Calendars → settings. | `client/connections/TOOLS.md` |
| `YOUR_CALENDAR_NAME` | Label for that calendar. | You choose it. | `client/connections/TOOLS.md` |
| `YOUR_GHL_API_KEY_1` | CRM API key. | GHL → Settings → Business Profile → API Key. | `client/connections/TOOLS.md` |
| `YOUR_GHL_LOCATION_ID_1` | CRM sub-account / location id. | GHL → Settings → Business Profile. | `client/connections/TOOLS.md` |
| `YOUR_GHL_SUBACCOUNT_1_NAME` | Label for the sub-account. | You choose it. | `client/connections/TOOLS.md` |
| `YOUR_STRIPE_SECRET_KEY` | Payment secret key, sk_live_… . | Stripe → Developers → API keys. | `client/connections/TOOLS.md` |

## Automation

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_APIFY_TOKEN` | Apify API token. | Apify Console → Settings → Integrations. | `client/connections/TOOLS.md` |
| `YOUR_APIFY_USERNAME` | Apify account username. | Apify Console → Settings → Account. | `client/connections/TOOLS.md` |
| `YOUR_MAKE_API_KEY` | Make.com API key. | Make → Profile → API → Add token. | `client/connections/TOOLS.md` |
| `YOUR_MAKE_ORG_ID` | Make organisation id. | Make URL when viewing the organisation. | `client/connections/TOOLS.md` |
| `YOUR_MAKE_REGION` | Make region host, e.g. us2.make.com. | The domain you log in to. | `client/connections/TOOLS.md` |
| `YOUR_MAKE_TEAM_ID` | Make team id. | Make URL when viewing the team. | `client/connections/TOOLS.md` |
| `YOUR_ZAPIER_OAUTH_TOKEN` | Zapier MCP OAuth token. Expires in about 60 minutes. | Zapier MCP connect page. A cron refreshes it. | `client/connections/zapier-README.md` |

## Research and content

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_CONSENSUS_API_KEY` | Consensus research API key. | Consensus account → API. | `client/connections/TOOLS.md` |
| `YOUR_HASHTAGS` | Hashtags the social prompt searches. | The owner. | `client/prompts/social-engagement.md` |
| `YOUR_NICHE` | The specific niche within that industry. | The owner. | `client/prompts/social-engagement.md` <br> `extras/agents/ad-architect/AGENTS.md` |
| `YOUR_PLATFORM` | Social platform the prompt runs on. | The owner. | `client/prompts/social-engagement.md` |

## Community and tasks

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_ASANA_PAT` | Asana personal access token. | Asana → Settings → Apps → Developer apps. | `client/connections/TOOLS.md` |
| `YOUR_ASANA_PROJECT_GID` | Asana project id. | Asana URL when viewing the project. | `client/connections/TOOLS.md` |
| `YOUR_ASANA_WORKSPACE_GID` | Asana workspace id. | Asana URL when viewing the workspace. | `client/connections/TOOLS.md` |
| `YOUR_GROUP_ID` | Chat group id a script posts into. | The channel's group id, e.g. from a directory lookup. | `client/scripts/ventas_report_check.py` |

## Script values

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_GOOGLE_SPREADSHEET_ID` | Sheet id a script reads. | The long id in the Google Sheets URL. | `client/scripts/ventas_report_check.py` |
| `YOUR_OPENCLAW_HOME` | Absolute path to the OpenClaw home. | Usually ~/.openclaw . | `client/scripts/ventas_report_check.py` |

## Job Card connector categories (JOB-CARD.md)

These name the CATEGORIES of connector a desk touches. Replace each with the desk's
actual service when filling in the Job Card's connector table.

| Placeholder | What it is | Where to get it | Used in |
|---|---|---|---|
| `YOUR_AD_PLATFORM` | The ad platform the desk pulls campaign metrics from. | The ad account the business runs. | `JOB-CARD.md` |
| `YOUR_RESEARCH_API` | The research/source API the desk uses for content. | The research provider's dashboard. | `JOB-CARD.md` |
| `YOUR_AUTOMATION_PLATFORM` | The automation/webhook platform the desk triggers. | The automation tool's account. | `JOB-CARD.md` |
| `YOUR_MESSAGING_CHANNEL` | The channel the desk delivers to people on. | The gateway channel config. | `JOB-CARD.md` |
| `YOUR_EMAIL_ACCOUNT` | The mailbox the desk may read (read-only). | The owner's email account. | `JOB-CARD.md` |

## Extras (optional, not part of the base install)

These appear only under `extras/`. Fill them in where you paste the piece, if you use it at all. See `extras/README.md`.

| Placeholder | What it is | Where to get it | Appears in |
|---|---|---|---|
| `YOUR_OPERATOR_PAPERCLIP_AGENT_ID` | Task-tracker agent id for the operator role. | Your task tracker, agent settings. Optional. | `extras/agents/operator/AGENTS.md` |
| `YOUR_RESEARCHER_PAPERCLIP_AGENT_ID` | Task-tracker agent id for the researcher role. | Same place. Optional. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_BRAND_COLOR` | Brand accent as an RGB tuple. Replace the tuple, not the comment. | The owner's brand guide. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_BRAND_NAME` | Brand name printed on generated images. | The owner. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_CLIENT_TYPE` | The kind of client this business serves. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_INDUSTRY` | Industry the business operates in. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_NICHE_TOPIC_1` | A recurring research topic. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_NICHE_TOPIC_2` | A second recurring research topic. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_NICHE_TOPIC_3` | A third recurring research topic. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_PLATFORM_URL` | Base URL of the coaching platform. Exported as the PLATFORM_URL env var at run time — it is not written into any file. | The platform you log in to. | `extras/fitness/scripts/progress_photos.py` |
| `YOUR_PRIMARY_CLIENT_TYPE_1` | Main client segment. | The owner. | `extras/agents/ad-architect/AGENTS.md` |
| `YOUR_PRIMARY_CLIENT_TYPE_2` | Second client segment. | The owner. | `extras/agents/ad-architect/AGENTS.md` |
| `YOUR_PRIMARY_CLIENT_TYPE_3` | Third client segment. | The owner. | `extras/agents/ad-architect/AGENTS.md` |
| `YOUR_RESEARCH_NICHE` | The subject the researcher role covers. | The owner. | `extras/agents/researcher/AGENTS.md` |
| `YOUR_SKOOL_COMMUNITY_SLUG` | Skool community slug from its URL. | skool.com/<slug>. | `extras/fitness/TOOLS-skool.md` |
| `YOUR_SKOOL_LOGIN_EMAIL` | Skool login email. | The owner. | `extras/fitness/TOOLS-skool.md` |
| `YOUR_SKOOL_LOGIN_PASSWORD` | Skool login password. Prefer secret storage over this file. | The owner. | `extras/fitness/TOOLS-skool.md` |
| `YOUR_AFTER_DATE` | After date on a progress image. | Per run. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_BEFORE_DATE` | Before date on a progress image, e.g. January 1, 2026. | Per run. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_CLIENT_NAME` | Client name printed on a generated image. | Per run. Not a permanent value. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_DEFAULT_CLIENT_ID` | Default client id a script falls back to. | The platform's client record. | `extras/fitness/scripts/progress_photos.py` |
| `YOUR_OUTPUT_DIR` | Absolute path a script writes output to. | You choose it. Must exist. | `extras/fitness/scripts/build_before_after.py` |
| `YOUR_PROGRAM_NAME` | Programme label on a progress image. | Per run. | `extras/fitness/scripts/build_before_after.py` |
