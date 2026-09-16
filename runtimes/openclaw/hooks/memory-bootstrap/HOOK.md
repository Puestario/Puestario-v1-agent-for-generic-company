---
name: memory-bootstrap
description: "Inject the memory brief (active decisions and current learnings) at session start"
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "events": ["agent:bootstrap"],
        "requires": { "bins": ["python3"], "config": ["workspace.dir"] },
      },
  }
---

# Memory bootstrap

Runs `python3 <workspace>/core/scripts/memory_log.py brief` on every
`agent:bootstrap` and injects the result as a `MEMORY.md` bootstrap file, so
the decisions in force and the current learnings are in front of the agent
before its first reply. This is the runtime half of AGENTS.md section 0.

If the script fails, a short notice is injected instead, and the agent is
expected to say so in its first reply rather than pretend it read the brief.

The brief is also written to `<workspace>/client/memory/.brief/MEMORY.md`
(gitignored) so an installer can read exactly what the agent was given.

Enable it with `openclaw hooks enable memory-bootstrap` after linking this
folder as a managed hook directory (see `runtimes/openclaw/README.md`).
