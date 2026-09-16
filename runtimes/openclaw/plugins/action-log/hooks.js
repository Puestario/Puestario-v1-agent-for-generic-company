// Action-log hooks for OpenClaw, kept free of any OpenClaw import so they can
// be unit-tested with plain node. index.js wires them into the plugin SDK.
//
// message_sending: write the action line BEFORE delivery by calling
//   core/scripts/action_log.py record. If the line is not on disk, cancel the
//   send (fail closed). The message text goes to the script on stdin so the
//   log holds its sha256 and byte count, never the text itself.
// message_sent:    write the outcome line (best effort). The action line is
//   the invariant; a missing outcome line is bookkeeping.
//
// Configuration, in order of precedence: plugin config, then the gateway's
// environment. Nothing defaults to a home folder.
//   script   / ACTION_LOG_SCRIPT   absolute path to core/scripts/action_log.py (required)
//   logPath  / ACTION_LOG          the log file (or leave unset and set OPENCLAW_STATE_DIR)
//   python   / ACTION_LOG_PYTHON   interpreter, default "python3"
//   consent  / -                   recorded on every line, default "openclaw:message_sending"
//   timeoutMs                      child budget, default 5000
import { spawnSync } from "node:child_process";
import { createHash } from "node:crypto";

export const CANCEL_REASON = "action_log_unwritable";
const RECEIPT = /^[0-9a-f]{64}$/;
const PENDING_TTL_MS = 10 * 60 * 1000;
const MAX_FIELD = 200;

export function resolveConfig(pluginConfig = {}, env = {}) {
  const pick = (key, envKey, fallback) => {
    const fromConfig = pluginConfig?.[key];
    if (typeof fromConfig === "string" && fromConfig.trim()) return fromConfig.trim();
    if (typeof fromConfig === "number" && Number.isFinite(fromConfig)) return fromConfig;
    const fromEnv = envKey ? env[envKey] : undefined;
    if (typeof fromEnv === "string" && fromEnv.trim()) return fromEnv.trim();
    return fallback;
  };
  return {
    python: pick("python", "ACTION_LOG_PYTHON", "python3"),
    script: pick("script", "ACTION_LOG_SCRIPT", null),
    logPath: pick("logPath", "ACTION_LOG", null),
    consent: pick("consent", null, "openclaw:message_sending"),
    timeoutMs: Number(pick("timeoutMs", null, 5000)) || 5000,
  };
}

function field(value, fallback) {
  const text = String(value ?? "").replace(/[\r\n]+/g, " ").trim();
  return (text || fallback).slice(0, MAX_FIELD);
}

function correlationKey(channel, to, content) {
  return createHash("sha256").update(`${channel}\n${to}\n${content}`).digest("hex");
}

export function createActionLogHooks({ pluginConfig, env = process.env, exec = spawnSync, log = console } = {}) {
  const cfg = resolveConfig(pluginConfig, env);
  const pending = new Map();

  function run(args, input) {
    const childEnv = { ...env };
    if (cfg.logPath) childEnv.ACTION_LOG = cfg.logPath;
    let result;
    try {
      result = exec(cfg.python, [cfg.script, ...args], {
        input, env: childEnv, timeout: cfg.timeoutMs, encoding: "utf8",
      });
    } catch (error) {
      return { status: null, stdout: "", stderr: String(error?.message ?? error) };
    }
    return {
      status: result?.status ?? null,
      stdout: String(result?.stdout ?? "").trim(),
      stderr: String(result?.stderr ?? result?.error?.message ?? "").trim(),
    };
  }

  function prune(now) {
    for (const [key, entry] of pending) if (now - entry.at > PENDING_TTL_MS) pending.delete(key);
  }

  function cancel(detail) {
    log.warn?.(`action-log: send cancelled: ${detail}`);
    return { cancel: true, cancelReason: CANCEL_REASON, metadata: { detail: String(detail).slice(0, MAX_FIELD) } };
  }

  return {
    config: cfg,
    pending,

    messageSending(event, ctx) {
      if (!cfg.script) return cancel("ACTION_LOG_SCRIPT / plugin config `script` is not set");
      const channel = field(ctx?.channelId, "unknown-channel");
      const to = field(event?.to, "unknown-target");
      const content = String(event?.content ?? "");
      const result = run([
        "record", "--action", `${channel}.send`, "--target", to,
        "--payload-class", "message", "--consent", cfg.consent, "--payload-stdin",
      ], content);
      if (result.status !== 0 || !RECEIPT.test(result.stdout)) {
        return cancel(result.stderr || `record exited ${result.status}`);
      }
      const now = Date.now();
      prune(now);
      pending.set(correlationKey(channel, to, content), { receipt: result.stdout, at: now, channel, to });
      return undefined; // no decision: delivery proceeds, and the line is already on disk
    },

    messageSent(event, ctx) {
      const channel = field(ctx?.channelId, "unknown-channel");
      const to = field(event?.to, "unknown-target");
      const content = String(event?.content ?? "");
      let key = correlationKey(channel, to, content);
      let entry = pending.get(key);
      if (!entry) {
        // Content may have been rewritten by a later hook; fall back to the
        // most recent pending receipt for the same channel and target.
        for (const [candidateKey, candidate] of [...pending].reverse()) {
          if (candidate.channel === channel && candidate.to === to) { key = candidateKey; entry = candidate; break; }
        }
      }
      if (!entry) return;
      pending.delete(key);
      const status = event?.success ? "sent" : "failed";
      const result = run(["outcome", "--receipt", entry.receipt, "--status", status]);
      if (result.status !== 0) log.warn?.(`action-log: outcome not recorded: ${result.stderr}`);
    },
  };
}
