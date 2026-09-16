# agent-desk-template

A working template for an AI operations agent that talks to real people on
behalf of a business, on real channels, with access to real systems.

It is the file half of a desk install: the rules the agent runs on, the
scripts, and a setup path someone else can follow.

**Built by [Puestario](https://puestario.com).** We build, install, and run
your company's AI agent.

* **See how it works:** [puestario.com/how-it-works](https://puestario.com/how-it-works)
* **Watch our own agents working live:** [puestario.com/live](https://puestario.com/live)
* **Want us to set it up for you?** [puestario.com](https://puestario.com)

**New here? Open [START-HERE.md](START-HERE.md) first.** It explains the setup
and the placeholders in plain words.

---

## What is in here

```
core/          The rules and the shared machinery. Pull updates into it freely.
  rules/       The seven hard rules. Zero placeholders. Never edited.
  config/      systems.md — the ONLY file in core/ that gets edited, once.
               reserved.md — the five owner-only changes. Never edited.
  scripts/     Automation that does not change per client: the action log,
               the untrusted-content envelope, the memory logs, the senders.
  contracts/   Versioned results and adapter migration notes.
  references/  Reference docs.

client/        Everything filled in per install. One job, one agent.
  identity/    Who the agent is, who the owners are, who may direct it.
  operating/   Per-install rules bindings and the heartbeat.
  connections/ Credentials and endpoints.
  memory/      learnings.jsonl and decisions.jsonl, the append-only logs.
  crons/       Scheduled jobs.
  prompts/     Reusable prompts.
  scripts/     Scripts that need client-specific values, including the two
               backup scripts. Read their headers before running either.

runtimes/      What the desk needs from the runtime itself. openclaw/ is built:
               a plugin that logs every send and a hook that injects memory at
               session start. hermes/ is a design note only.

extras/        Optional: sub-agent roles and one desk's fitness scripts. Not
               loaded, not counted, not installed unless you copy it in.

START-HERE.md     The simple setup guide. Start here.
JOB-CARD.md       Read this next — how we pick the job, connectors, proof, the lessons.
PLACEHOLDERS.md   All 64 base placeholders, what they are, where to get them.
SETUP.md          Install, in order.
evals/            Agent trial cases, a trial wrapper and an offline scorer.
tests/            Local regression tests and the CI drift checks.
```

`core/rules/` and `core/config/` never name a person, a business, a client, or
a number, and `core/rules/` contains no placeholders at all — the two values the rules need live in
`core/config/systems.md`, which is the single file in `core/` an installer
touches. That is what makes the rest updatable: pull a newer `core/rules/` into
an existing install and nothing a client filled in is disturbed.

`client/identity/OWNER.md` is where the owners and the allowlist are recorded.
Every rule that needs an owner points there.

## Who is in charge

Two owners are written into `client/identity/OWNER.md`: Coach Lalo (Gerardo
Vera) and Mateo Arbelaez. Either one alone can direct the agent and change
anything, including its rules and its allowlist, by WhatsApp from their
verified number. There is no second confirmation channel and the agent does
not ask the other owner. Every such change is written to
`client/memory/decisions.jsonl` and confirmed back on WhatsApp.

That was decided on 2026-09-15, after a first install whose agent would not
take the owners' orders, and it is recorded in `client/memory/decisions.jsonl`.
The trade-off is plain: whoever holds either phone is an owner to the agent.
If a phone is lost, the other owner removes that number by message at once.

Nothing in this template runs a script for you. `client/scripts/backup_local.sh`
and `client/scripts/backup_to_drive.py` are the two to look at before you wire
anything to a schedule: the first archives the whole agent home including
credentials, and the second uploads that archive to Google Drive unencrypted.
Both carry a header saying so. They ship because installs need a backup story,
not because this one is the right one.

---

## Local verification

Run `python3 -m unittest discover -s tests -v` from the repository root.
Tests use synthetic files and mocked external calls; no live services are contacted.
The OpenClaw runtime tests drive the plugin and the hook with `node` (any
recent version) against the real scripts; they are skipped when node is absent.
`python3 tests/ci_checks.py all` runs the drift checks CI runs: placeholder
counts match the tree, `core/rules/` has no placeholder, and every file that
auto-loads each session fits its size budget.
See [evals/README.md](evals/README.md) for recorded agent trials and
[core/contracts/README.md](core/contracts/README.md) for changed adapter return
values. Passing local tests does not qualify a model or certify a live install.

## The seven rules

| File | What it does |
|---|---|
| `00-who-is-talking.md` | Identity check before anything else. Strangers get nothing. |
| `01-content-is-not-command.md` | Text the agent reads is never an order. Owner messages are requests, not content. |
| `02-the-yes-comes-from-the-owner.md` | Only an owner's number says yes. An owner asking is the yes. |
| `03-say-where-i-looked.md` | Every lookup names the sources actually checked; corroborate when needed. |
| `04-finding-a-persons-payments.md` | Four ordered searches before saying someone has no payments. |
| `05-no-social-engineering-exceptions.md` | Claimed authority is not authority. |
| `06-how-my-rules-change.md` | Rules change on an owner's word from their verified number, and every change is logged. |

Rules 01, 02, 04 and 06 are written as steps to perform. Rules 00 and 03 are
written as states to notice. **In testing, the step-shaped rules held and the
state-shaped rules were unreliable.** If you write a new rule and it matters,
write it as a step.

---

## KNOWN AND OPEN

This template is in use and it is not finished. Three things are known not to
work fully, and one thing has not been proven live. Anyone installing it
should read this before telling a client the desk is safe.

### The action log and the envelope are unit-tested, not yet proven on an install

`core/scripts/action_log.py`, `core/scripts/untrusted.py`,
`core/scripts/read_content.py` and the OpenClaw plugin and hook under
`runtimes/openclaw/` all have tests that run in both directions against the
real scripts. What has **not** happened yet: SETUP.md step 7 tests 7, 8, 9 and
10 on a live install. Nobody has yet watched the gateway cancel a send because
the log was unwritable, or watched an agent refuse to act on a document it
read through the envelope. Until someone does, treat both as promising, not
proven. Record the date and result here when it is done.

### H0 fires when identity is obvious and not reliably otherwise

`core/rules/00-who-is-talking.md` is meant to stop the agent saying anything
to a sender who is not on the allowlist.

Tested 2026-09-02: asked an ordinary question from an unrecognized number, the
agent answered it, named internal files, and offered to keep working. Asked a
question from the same number that explicitly raised sender identity, the rule
fired correctly and the agent refused and notified the owner.

**H0 is not the control. The channel allowlist is the control.** Set
`dmPolicy: allowlist` on every channel the agent runs on and put the real
numbers in it. Do not deploy with an open inbox on any channel. This is a hard
requirement of the install, not a setting.

### H12 misses when the agent believes it lacks access to a system

`core/rules/03-say-where-i-looked.md` requires a `Looked in:` receipt on every
lookup.

It holds on "this person has no record" and on easy correct answers. It does
not hold when the agent concludes it has no access to a whole system — that is
a claim about its own capability rather than about a record, and three
separate rewrites did not reach it.

**Treat any capability claim from the agent as unverified unless it carries a
`Looked in:` line naming the sources actually checked.** "I don't have credentials for
that" has been wrong more than once, with the answer one lookup away.

### The tool deny list is dormant without a container runtime

Tool policy applies inside a sandbox. With the sandbox off, a deny list will
validate, read exactly like protection, and block nothing.

Verified 2026-09-02 on a live install: with a 16-entry deny list in place and
the config validating clean, the agent ran shell commands, read a credentials
file in full, read its own environment variables, spawned sub-agents by two
routes, listed scheduled jobs, and listed the owner's inbox. **Nothing was
blocked.**

Install a container runtime, turn the sandbox on, and put the deny list at the
enforced path under the sandbox tool policy. Then test it in both directions.
Until then, treat the agent as unrestricted and do not give it access to
anything you would not hand a stranger.

---

### A client deliverable must not run on a fallback model unnoticed

Every desk has a model chain: a primary and an ordered list of fallbacks. When the
primary fails, the runtime silently drops to the next model and the job still reports
success. That is correct for resilience and dangerous for delivery: a client's daily
report can run on the third or fourth model in the chain, every day, and nothing says so.

Two hard requirements for any client-facing scheduled job:

- **Do not route the gateway's stderr to `/dev/null`.** Per-model-attempt failures are
  written there. Discard it and a job that fell back is indistinguishable from one that ran
  clean — the failure reason is gone. Send stderr to a real log file.
- **Monitor which model each client-facing cron actually ran on**, not just that it exited
  0. A fallback that fires every day is not a fallback; it is an undeclared primary nobody
  chose, one outage away from silence. Isolated per-run sessions retry the primary each time;
  a persistent named session can get stuck on a fallback and never re-attempt the primary.

Observed on the reference install 2026-09-03: a paying client's daily ads report ran on
model fallback #3 for at least three consecutive captured days while reporting success, and
the cause could not be diagnosed because stderr was `/dev/null`.

## The rule behind the rules

A rule that can be satisfied more than one way will be satisfied the easy way.
A setting that can be confirmed two ways will be confirmed the cheap way.

Test in both directions before believing either. Does the thing still work, and
is the thing actually blocked. A config that validates is not evidence. A
command exiting 0 is not evidence. A blocked attempt is evidence.
