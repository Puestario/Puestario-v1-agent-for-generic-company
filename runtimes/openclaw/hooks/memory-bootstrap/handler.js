// OpenClaw internal hook: on agent:bootstrap, run memory_log.py brief and add
// the result to the bootstrap files as MEMORY.md (one of the eight names
// OpenClaw accepts for bootstrap files).
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export const BRIEF_RELATIVE_PATH = path.join("client", "memory", ".brief", "MEMORY.md");
export const SCRIPT_RELATIVE_PATH = path.join("core", "scripts", "memory_log.py");

export function buildBrief(workspaceDir, { exec = spawnSync, env = process.env } = {}) {
  const script = path.join(workspaceDir, SCRIPT_RELATIVE_PATH);
  const python = env.ACTION_LOG_PYTHON || "python3";
  let result;
  try {
    result = exec(python, [script, "brief"], { cwd: workspaceDir, env, encoding: "utf8", timeout: 10000 });
  } catch (error) {
    result = { status: null, stdout: "", stderr: String(error?.message ?? error) };
  }
  const ok = result?.status === 0 && String(result.stdout ?? "").trim().length > 0;
  const content = ok
    ? String(result.stdout)
    : "# Memory brief unavailable\n\n"
      + `core/scripts/memory_log.py brief did not run (exit ${result?.status ?? "none"}). `
      + "Say so in the first reply; do not act as if the brief was read.\n";
  const outPath = path.join(workspaceDir, BRIEF_RELATIVE_PATH);
  try {
    fs.mkdirSync(path.dirname(outPath), { recursive: true });
    fs.writeFileSync(outPath, content, { mode: 0o600 });
  } catch {
    // The injected content is what matters; the on-disk copy is a convenience.
  }
  return { name: "MEMORY.md", path: outPath, content, missing: false, ok };
}

const handler = async (event) => {
  if (event?.type !== "agent" || event?.action !== "bootstrap") return;
  const context = event.context;
  if (!context?.workspaceDir || !Array.isArray(context.bootstrapFiles)) return;
  const file = buildBrief(context.workspaceDir);
  context.bootstrapFiles.push({ name: file.name, path: file.path, content: file.content, missing: false });
};

export default handler;
