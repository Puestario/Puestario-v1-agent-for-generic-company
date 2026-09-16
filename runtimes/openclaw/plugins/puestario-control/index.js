import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { createBridge, invoke } from "./bridge.js";
import { randomUUID } from "node:crypto";

// Stable across registration/inspection within this process; a new gateway closes Setup.
const boot = `${process.pid}:${randomUUID()}`;

export default definePluginEntry({
  id: "puestario-control", name: "Puestario managed desk",
  register(api) {
    const config = api.pluginConfig, bridge = createBridge(config);
    api.registerTool(ctx => bridge.tool(ctx), {name: "puestario"});
    api.registerCommand({name: "desk", description: "Puestario owner controls", acceptsArgs: true,
      requireAuth: true, handler: ctx => bridge.command(ctx)});
    api.on("before_agent_run", (event, ctx) => bridge.beforeRun(event, ctx));
    api.on("llm_output", (event, ctx) => bridge.output(event, ctx));
    api.on("before_tool_call", event => bridge.beforeTool(event));
    api.on("message_sending", (event, ctx) => bridge.sending(event, ctx), {priority: 1000});
    // Keep run receipts until transport has finished. agent_end can precede delivery.
    let timer, busy = false;
    api.registerService({id: "puestario-scheduler", async start() {
      await invoke(config, "startup", {boot});
      await invoke(config, "acknowledge", {config: api.config});
      timer = setInterval(async () => {
        if (busy) return;
        busy = true;
        try { await invoke(config, "tick"); }
        catch { api.logger.warn("Puestario scheduler needs an operator check; no automatic replay of uncertain sends"); }
        finally { busy = false; }
      }, 15000);
      timer.unref();
    }, stop() { clearInterval(timer); }});
  }
});
