// No model-supplied field is used as the identity or conversation route.
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { createHash, randomUUID } from "node:crypto";

export const operations = ["status", "resources.list", "resource.read", "resource.write", "note.save", "note.list",
  "job.add", "job.list", "job.remove", "job.reschedule", "setup.open", "setup.close", "desk.pause", "desk.resume",
  "person.put", "person.remove", "group.put", "group.remove", "founder.add", "founder.remove",
  "company.update", "resource.put", "resource.remove", "connection.check"];

export function route(value) {
  if (typeof value !== "string") throw new Error("Missing trusted route");
  value = value.replace(/^whatsapp:/, "");
  if (value.endsWith("@s.whatsapp.net")) value = "+" + value.slice(0, -15);
  if (!/^\+[1-9]\d{7,14}$/.test(value) && !/^\d{5,30}(?:-\d+)?@g\.us$/.test(value)) throw new Error("Unknown route format");
  return value;
}

export function toolActor(ctx) {
  const delivery = ctx.deliveryContext;
  if (ctx.messageChannel !== "whatsapp" || delivery?.channel !== "whatsapp" ||
      !ctx.agentAccountId || delivery.accountId !== ctx.agentAccountId || !ctx.sessionId) {
    throw new Error("Trusted WhatsApp account and session are required");
  }
  return {channel: "whatsapp", account: ctx.agentAccountId,
    sender: route(ctx.requesterSenderId), conversation: route(delivery.to)};
}

export function invoke(config, action, envelope = {}) {
  return new Promise((resolve, reject) => {
    const child = spawn(config.python, ["-m", "managed.cli", "--root", config.root, action],
      {cwd: config.release, stdio: ["pipe", "pipe", "pipe"], env: {...process.env, PYTHONPATH: config.release}});
    let output = "", size = 0;
    const timer = setTimeout(() => { child.kill(); reject(new Error("Desk operation timed out; check status before retrying")); }, 120000);
    child.stdout.on("data", chunk => {
      size += chunk.length;
      if (size > 2500000) { child.kill(); reject(new Error("Result too large")); }
      else output += chunk;
    });
    child.stderr.resume(); // Private provider errors must never enter a model transcript.
    child.on("error", () => { clearTimeout(timer); reject(new Error("Protected desk service is unavailable")); });
    child.on("close", () => {
      clearTimeout(timer);
      try {
        const result = JSON.parse(output);
        if (!result.ok) reject(new Error(result.error || "Desk operation failed"));
        else resolve(result.result);
      } catch (error) { reject(error instanceof SyntaxError ? new Error("Desk operation had no verified result") : error); }
    });
    child.stdin.on("error", () => {});
    child.stdin.end(JSON.stringify(envelope));
  });
}

const hash = content => createHash("sha256").update(content).digest("hex");

export function createBridge(config, call = invoke) {
  const contexts = new Map(), runs = new Map(), permits = new Map();
  const snapshot = () => JSON.parse(readFileSync(`${config.root}/control.json`, "utf8"));
  const permitKey = (account, to, text) => `${account}:${route(to)}:${hash(text)}`;
  const allowedRun = (state, run, to, now) => run && run.expires > now &&
    (run.epoch === (state.access_epoch || 0) || (run.ownerPrivate && state.founders[run.actor.sender]?.active && to === run.actor.sender)) &&
    run.actor.conversation === to && (state.founders[run.actor.sender]?.active || state.people[run.actor.sender]?.active) &&
    (!state.groups[to] || state.founders[run.actor.sender]?.active || state.groups[to].members.includes(run.actor.sender));
  return {
    tool(ctx) {
      let actor;
      try { actor = toolActor(ctx); contexts.set(`${ctx.sessionId}:${actor.sender}`, {actor, session: ctx.sessionId, ctx}); }
      catch { return null; }
      return {
        name: "puestario", label: "Puestario desk",
        description: "Use approved business resources, private notes, reminders and founder settings. " +
          "Never pass credentials or identity. resources.list shows allowed resources. " +
          "resource.read: {resource}; resource.write: {resource,rows} fills the EXACT configured sheet range. " +
          "note.save: {name,text}; note.list: {}. job.add: {text,to?,resource?,schedule:{at:ISO date OR daily:HH:MM OR every_minutes:number}}; " +
          "job.remove/reschedule: {id,schedule?}. person.put: {name,number,resources:{resourceName:[read,write]},tester?}; person.remove: {number}. " +
          "group.put: {id,name,members:[numbers],resources:{resourceName:[read]}}; group.remove:{id}. " +
          "setup.open:{minutes}; setup.close:{} requires installer evidence. company.update:{company_name?,agent_name?,language?,timezone?,model?,fallbacks?,instructions?}. " +
          "resource.put:{name,resource:{kind,connection,spreadsheet_id?,range?,calendar_id?,location_id?,writable?}}; resource.remove:{name}; connection.check:{resource}. " +
          "founder.add:{name,number}; founder.remove:{number}. status/desk.pause/desk.resume:{}. " +
          "App connections are entered locally. After access changes send /new to start with fresh permissions.",
        parameters: {type: "object", additionalProperties: false, required: ["operation", "args"], properties: {
          operation: {type: "string", enum: operations}, args: {type: "object"}, expected_revision: {type: "integer", minimum: 1}}},
        async execute(toolCallId, params) {
          try {
            const active = ctx.getRuntimeConfig?.() ?? ctx.runtimeConfig ?? ctx.config;
            if (active) await call(config, "acknowledge", {config: active});
            if (Object.keys(params).some(key => !["operation", "args", "expected_revision"].includes(key)) || !operations.includes(params.operation)) throw new Error("Unknown operation or field");
            const result = await call(config, "request", {actor, session_id: ctx.sessionId,
              operation: params.operation, args: params.args, expected_revision: params.expected_revision,
              request_id: `${ctx.sessionId}:${toolCallId}`});
            const refreshed = ctx.getRuntimeConfig?.();
            if (refreshed) {
              const applied = await call(config, "acknowledge", {config: refreshed});
              if (Object.hasOwn(result, "settings_applied")) result.settings_applied = applied.settings_applied;
            }
            return {content: [{type: "text", text: JSON.stringify(result)}], details: {ok: true}};
          } catch (error) { return {content: [{type: "text", text: error.message}], isError: true, details: {ok: false}}; }
        }
      };
    },
    async beforeRun(event, ctx) {
      try {
        const saved = contexts.get(`${ctx.sessionId}:${route(event.senderId)}`);
        if (!saved || event.channelId !== "whatsapp" || saved.actor.account !== event.accountId || !ctx.runId) throw new Error("Trusted sender context unavailable");
        const active = saved.ctx.getRuntimeConfig?.() ?? saved.ctx.runtimeConfig ?? saved.ctx.config;
        if (active) await call(config, "acknowledge", {config: active});
        const result = await call(config, "session-gate", {actor: saved.actor, session_id: ctx.sessionId,
          has_history: Array.isArray(event.messages) && event.messages.some(message =>
            !(message?.role === "custom" && message.customType === "openclaw.runtime-context" && message.details?.source === "openclaw-runtime-context"))});
        runs.set(ctx.runId, {actor: saved.actor, epoch: result.epoch, ownerPrivate: result.owner_private, expires: Date.now()+3600000});
        for (const [key,value] of runs) if (value.expires < Date.now()) runs.delete(key);
        // Tool factories are recreated for active contexts. Bound memory without granting stale routes.
        while (contexts.size > 4096) contexts.delete(contexts.keys().next().value);
        return {outcome: "pass"};
      } catch (error) { return {outcome: "block", reason: error.message, message: error.message}; }
    },
    async command(ctx) {
      try {
        if (!ctx.isAuthorizedSender || ctx.channel !== "whatsapp" || !ctx.accountId) throw new Error("Verified WhatsApp sender required");
        if (ctx.config) await call(config, "acknowledge", {config: ctx.config});
        const actor = {channel: "whatsapp", account: ctx.accountId, sender: route(ctx.senderId), conversation: route(ctx.from)};
        const input = (ctx.args || "status").trim();
        const envelope = input === "status" ? {operation:"status",args:{}} :
          /^open(?: \d+)?$/.test(input) ? {operation:"setup.open",args:{minutes:Number(input.split(" ")[1] || 15)}} :
          input === "close" ? {operation:"setup.close",args:{}} : JSON.parse(input);
        if (!operations.includes(envelope.operation) || Object.keys(envelope).some(k => !["operation","args","expected_revision"].includes(k))) throw new Error("Use /desk status, /desk open 15, /desk close, or an operation JSON object");
        const result = await call(config, "request", {actor, ...envelope, request_id: randomUUID(), direct_command: true});
        const text = JSON.stringify(result, null, 2);
        permits.set(permitKey(ctx.accountId, actor.conversation, text), {expires:Date.now()+30000, commandOwner:actor.sender});
        return {text};
      } catch (error) {
        // A generic error never includes app data or credentials. The outbound gate may still block it.
        return {text: `Puestario: ${error.message}`};
      }
    },
    sending(event, ctx) {
      try {
        // Atomic snapshot: do not take Python's file lock while its scheduler waits for transport.
        const state = snapshot(), to = route(event.to), now = Date.now();
        if (ctx.channelId !== "whatsapp" || ctx.accountId !== state.account_id) throw new Error();
        const founder = state.founders[to]?.active;
        const testDestination = state.setup?.until * 1000 > now && (state.people[to]?.tester || state.groups[to]);
        if (!founder && (state.paused || state.gateway_pending || (!state.ready && !testDestination))) throw new Error();
        if (!(founder || state.people[to]?.active || state.groups[to])) throw new Error();
        const key = permitKey(ctx.accountId, to, event.content);
        const permit = permits.get(key);
        if (permit?.expires > now && (permit.commandOwner ?
            state.founders[permit.commandOwner]?.active && to === permit.commandOwner : allowedRun(state, permit.run, to, now))) return;
        const run = runs.get(ctx.runId);
        if (allowedRun(state, run, to, now)) return;
        // Protected scheduler claimed these exact bytes before calling the transport.
        if (Object.values(state.outbox).some(n => n.status === "sending" && n.to === to && n.text === event.content)) return;
        if (Object.values(state.jobs).some(j => j.to === to && j.runs.some(r => r.status === "sending" && r.sha256 === hash(event.content)))) return;
      } catch { /* fail closed */ }
      return {cancel: true, cancelReason: "puestario_access_check"};
    },
    output(event, ctx) {
      // This runtime's transport hooks can omit runId. Bind exact model-output bytes to
      // the already verified run before transport; never infer identity from reply text.
      const run = runs.get(event.runId ?? ctx.runId);
      if (!run) return;
      for (const text of event.assistantTexts ?? []) {
        if (typeof text !== "string" || text.length > 3500) continue;
        for (const rendered of [text, text.trim(), text.replace(/\[\[reply_to_(?:current|[a-zA-Z0-9_-]+)\]\]/g, "").trim()]) {
          permits.set(permitKey(run.actor.account, run.actor.conversation, rendered), {run,expires:Date.now()+120000});
        }
      }
      for (const [key, value] of permits) if (value.expires < Date.now()) permits.delete(key);
    },
    end(event, ctx) { runs.delete(ctx.runId); },
    beforeTool(event) { if (event.toolName !== "puestario") return {block:true, blockReason:"Only protected Puestario operations are enabled"}; }
  };
}
