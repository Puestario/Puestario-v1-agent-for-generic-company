# runtimes/openclaw — what the desk needs from OpenClaw itself

The rules, scripts and tests in `core/` and `client/` do not depend on a
runtime. This folder holds the two pieces that do, for OpenClaw: a plugin that
makes the action log cover every send, and a hook that puts the memory brief
in front of the agent at session start. SETUP.md step 6 installs them.

Paths never default to a home folder. Everything reads
`OPENCLAW_STATE_DIR` (OpenClaw's own state-directory variable) or an explicit
`ACTION_LOG` / `ACTION_LOG_SCRIPT`, set in the gateway's environment or in
`openclaw.json` under `env.vars`.

## plugins/action-log

An OpenClaw plugin (`openclaw.plugin.json` + `index.js`) that registers two
typed hooks:

| Hook | What it does |
|---|---|
| `message_sending` | Calls `core/scripts/action_log.py record` with the channel, the target and the message bytes on stdin. If the line is not on disk, returns `cancel: true` with reason `action_log_unwritable`. Runs at low priority so it hashes what actually goes out. |
| `message_sent` | Calls `action_log.py outcome` with `sent` or `failed` for the matching receipt. Best effort. |

It covers every channel OpenClaw delivers on (WhatsApp, Telegram, Discord and
the rest), every cron delivery, and every reply, because `message_sending` is
where OpenClaw hands a message to a channel. `core/scripts/whatsapp-send.py`
keeps its own receipt for the desktop path that bypasses the gateway.

**Fail closed means fail closed.** With the plugin enabled and no log path
configured, no message leaves the desk. That is the point. Configure it, test
it in both directions (SETUP.md step 7, test 7), then leave it on.

Logic lives in `hooks.js` with no OpenClaw import; `tests/test_openclaw_plugin.py`
drives it with node against the real `action_log.py`.

## hooks/memory-bootstrap

An internal hook (`HOOK.md` + `handler.js`) on `agent:bootstrap`. It runs
`python3 core/scripts/memory_log.py brief` in the workspace and pushes the
output into the session's bootstrap files as `MEMORY.md`. The agent sees the
decisions in force and the current learnings before its first reply. A copy is
written to `client/memory/.brief/MEMORY.md` so you can read what it was given.

## Install

```bash
# from the workspace, after SETUP.md steps 1-5
openclaw plugins install --link "$PWD/runtimes/openclaw/plugins/action-log"
openclaw config set plugins.entries.action-log.enabled true --strict-json
openclaw config set plugins.entries.action-log.config.script "$PWD/core/scripts/action_log.py"
openclaw config set env.vars.OPENCLAW_STATE_DIR "$HOME/.openclaw"      # or wherever state lives
openclaw config set hooks.internal.load.extraDirs '["'"$PWD"'/runtimes/openclaw/hooks"]' --strict-json
openclaw hooks enable memory-bootstrap
openclaw gateway restart
```

Then: `openclaw plugins inspect action-log --runtime --json` should list both
hooks, and `openclaw hooks list` should show `memory-bootstrap` ready.

## What is not verified

These files follow OpenClaw 2026.5.27's documented plugin and hook contracts
(`docs/plugins/hooks.md`, `docs/automation/hooks.md`, shipped `.d.ts`). The
hook logic is unit-tested against the real scripts. They have **not** been
exercised inside a running gateway yet; SETUP.md step 7 tests 7 and 9 are the
live checks. Two details to confirm on first install: that `event.context.pluginConfig`
carries the plugin config (the env-var route works either way), and that a
managed hook loads from `handler.js` (rename to `handler.ts` if the loader
insists; the file is plain JavaScript).
