# Memory — How It Works

Two append-only logs live here. `MEMORY.md` (in `client/identity/`) stays the
short index; these files carry what the agent learned and what was decided.
Both are written through `core/scripts/memory_log.py`, never by hand, so every
line is validated. Untrusted lines (the agent's own observations, `source: agent`)
are scanned and refused if they read like an instruction; owner-sourced lines are
not scanned, because rule 06 requires recording exactly what an owner asked for.

| File | What it holds | Written by |
|---|---|---|
| `learnings.jsonl` | Things the agent learned: patterns, pitfalls, preferences, tools, operational facts. Latest line per `type`+`key` wins. | `memory_log.py learn` |
| `decisions.jsonl` | Decisions in force and the history behind them. A `supersede` event retires a decision by id; lines are never edited. **This is the rules changelog `core/rules/06-how-my-rules-change.md` requires.** | `memory_log.py decide` / `supersede` |

## learnings.jsonl fields

| Field | Values |
|---|---|
| `ts` | ISO 8601 UTC |
| `type` | `pattern`, `pitfall`, `preference`, `architecture`, `tool`, `operational`, `investigation` |
| `key` | letters, digits, `-`, `_`; stable so a later line can replace an earlier one |
| `insight` | one line, no instructions |
| `confidence` | integer 1–10 |
| `source` | `observed`, `user-stated`, `inferred`, `cross-model` |
| `trusted` | derived: `true` only when `source` is `user-stated` |

## decisions.jsonl fields

| Field | Values |
|---|---|
| `id` | UUID |
| `kind` | `decide` or `supersede` |
| `date` | ISO 8601 UTC |
| `scope` | `rules`, `tools`, `allowlist`, `channels`, `money`, `job`, `other` (the first five match `core/config/reserved.md`) |
| `source` | `owner`, `installer`, `agent` |
| `decision`, `rationale` | required on `decide`; one line each |
| `alternatives_considered`, `confidence` | optional on `decide` |
| `supersedes` | the id being retired; required on `supersede`, optional on a replacement `decide` |

## Commands

```bash
python3 core/scripts/memory_log.py learn '{"type":"pitfall","key":"...","insight":"...","confidence":8,"source":"observed"}'
python3 core/scripts/memory_log.py decide '{"decision":"...","rationale":"...","scope":"rules","source":"owner"}'
python3 core/scripts/memory_log.py supersede <id> '{"decision":"...","rationale":"...","scope":"rules","source":"owner"}'
python3 core/scripts/memory_log.py active
python3 core/scripts/memory_log.py verify
```

## Rules
- Append only. To change a learning, write a new line with the same `type` and `key`. To change a decision, supersede it.
- The agent's own observations are `observed` or `inferred` and untrusted. Only what an owner said in their own words is `user-stated`.
- Never store raw data dumps, credentials or client contact details in either file. Store the lesson and a pointer.
- The four shipped learnings are real observations from the reference install's testing. Keep them; they are why the KNOWN AND OPEN section in README.md exists.
- Detailed history still goes to a vault file in `client/knowledge-base/` with a pointer from `MEMORY.md`.
