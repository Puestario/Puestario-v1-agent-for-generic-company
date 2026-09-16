# runtimes/hermes — not built

The desk runs on OpenClaw. Nothing here is installed or tested. This note
records what a Hermes runtime folder would contain, from Hermes Agent's public
docs as of September 2026, so the decision to add one later starts from facts.

Same repo, not a second one: `core/` and `client/` are runtime-neutral; only
this folder would differ.

| Need | OpenClaw (built, `runtimes/openclaw/`) | Hermes (not built) |
|---|---|---|
| Action line before every send | plugin hook `message_sending`, cancels on failure | plugin hook `pre_tool_call` on `send_message` (returns `{action: "block"}`), or a shell hook in `config.yaml` under `hooks.pre_tool_call` with `fail_closed: true`; outcome via `post_tool_call`. Both call the same `action_log.py record` / `outcome`. |
| State directory | `OPENCLAW_STATE_DIR` | `HERMES_HOME` (default `~/.hermes`; `action_log.py` already honours it) |
| Session start brief | internal hook `agent:bootstrap` injects `MEMORY.md` | `pre_llm_call` plugin hook returning `{context: ...}`, or the brief pasted into `$HERMES_HOME/SOUL.md` by a build step |
| Identity and rules | bootstrap files from the workspace | `$HERMES_HOME/SOUL.md` is loaded verbatim as slot 1 of the system prompt; it must be **built** from `client/identity/*.md` + `core/rules/*.md` + `client/operating/AGENTS.md` by a script, and rebuilt on every change |
| Scheduled checks | HEARTBEAT.md | `hermes cron create` jobs in `$HERMES_HOME/cron/jobs.json`; the job's `deliver:` target sends the output, not the agent |
| Allowlist | `channels.<channel>.allowFrom` in `openclaw.json` | `gateway.platforms.<platform>.allow_from` in `config.yaml`, or `*_ALLOWED_USERS` env vars |

Open questions to settle before building: whether Hermes' WhatsApp toolset
routes through `send_message` or its own tool names (the hook must match all of
them), and whether the SOUL.md size limit fits the seven rules plus identity.
