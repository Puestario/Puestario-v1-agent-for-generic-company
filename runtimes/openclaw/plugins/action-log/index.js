// OpenClaw plugin entry: every outbound message on every channel writes an
// action-log line before delivery, and is cancelled when it cannot.
// Logic lives in hooks.js so it can be tested without OpenClaw.
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createActionLogHooks } from "./hooks.js";

export default definePluginEntry({
  id: "action-log",
  name: "Action log",
  description: "Hash-chained receipt before every send; cancels the send when the receipt cannot be written.",
  register(api) {
    let hooks = null;
    const resolve = (event) => {
      if (!hooks) {
        hooks = createActionLogHooks({
          pluginConfig: event?.context?.pluginConfig ?? api?.pluginConfig ?? {},
          env: process.env,
          log: api?.logger ?? console,
        });
      }
      return hooks;
    };
    // Low priority: run after any hook that rewrites content, so the hash is
    // of the bytes that actually go out. A cancel from an earlier hook means
    // nothing is sent and nothing needs logging.
    api.on("message_sending", (event, ctx) => resolve(event).messageSending(event, ctx), { priority: -1000 });
    api.on("message_sent", (event, ctx) => resolve(event).messageSent(event, ctx));
  },
});
