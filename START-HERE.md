# Start Here: Set Up Your Agent Desk

This is the simple guide. Read it first. The full guide is [SETUP.md](SETUP.md).

**Built by [Puestario](https://puestario.com)**, by Coach Lalo (Gerardo Vera) and Mateo Arbelaez.

| Want to... | Go here |
|---|---|
| See how it works | [puestario.com/how-it-works](https://puestario.com/how-it-works) |
| Watch our own agents work live | [puestario.com/live](https://puestario.com/live) |
| Have us set it up for you | [puestario.com](https://puestario.com) |

---

## 1. What this is

This repo holds everything an AI agent needs to work one desk inside a business.

The agent talks to your team on WhatsApp. It does one job for them. It follows seven hard rules.

The repo has three main parts:

| Folder | What it is | Do you edit it? |
|---|---|---|
| `core/` | The rules and the shared scripts. | No. Only one file: `core/config/systems.md`. |
| `client/` | Your business info: who the agent is, who the owners are, your tools. | Yes. This is where you fill things in. |
| `runtimes/` | The parts that plug the agent into OpenClaw. | No. You just turn them on. |

`extras/` is optional. Skip it on your first install.

---

## 2. What you need before you start

1. **A computer that stays on all day.** A Mac mini or a small PC works.
2. **OpenClaw installed.** This template is built for OpenClaw.
3. **A WhatsApp number** the agent will use.
4. **Both owners' phones with you.** You will test with them.
5. **Logins for the tools the agent will use.** Only the ones its job needs. For example your CRM, your payment system, or your ad account.
6. **About 90 minutes** if your logins are ready.

---

## 3. What a placeholder is

A placeholder is a blank you fill in.

Every placeholder starts with `YOUR_` and is written in capital letters. You swap each one for your real info.

**Before:**

```
- **WhatsApp:** YOUR_OWNER_WHATSAPP
- **Company:** YOUR_BUSINESS_NAME
```

**After:**

```
- **WhatsApp:** +13055550100
- **Company:** Acme Freight
```

**Five rules for placeholders:**

1. **Replace the whole thing**, including the `YOUR_` part.
2. **Phone numbers:** plus sign, country code, then the number. No spaces. Like `+13055550100`.
3. **Never type a name, number or email into `core/rules/`.** Those files stay clean.
4. **Passwords and keys:** keep them in OpenClaw's secret storage when you can. A file full of live keys is easy to leak.
5. **Not using a tool?** Delete that tool's section from `client/connections/TOOLS.md`. Do not leave the blank sitting there.

**Where to learn what each one means:** [PLACEHOLDERS.md](PLACEHOLDERS.md) lists all 64. For each one it tells you what it is, where to find it, and which files it lives in.

**Installing this for your own business?** Also change the owner names (Coach Lalo, Gerardo Vera, Mateo, Mateo Arbelaez) to your owners in `client/identity/OWNER.md`, `USER.md` and `MEMORY.md`.

---

## 4. Fill these in first

These matter most. If one is wrong, the agent works for the wrong person.

| Placeholder | What to put in | File |
|---|---|---|
| `YOUR_OWNER_WHATSAPP` | Owner 1's WhatsApp number. **This number is the boss of the agent.** | `client/identity/OWNER.md` and others |
| `YOUR_OWNER_2_WHATSAPP` | Owner 2's WhatsApp number. **Also the boss.** | `client/identity/OWNER.md` and others |
| `YOUR_OWNER_EMAIL` | Owner 1's email. | `client/identity/` |
| `YOUR_OWNER_2_EMAIL` | Owner 2's email. | `client/identity/` |
| `YOUR_BUSINESS_NAME` | The business name. | `client/identity/` |
| `YOUR_AGENT_NAME` | The name you give the agent. | `client/identity/` |
| `YOUR_TIMEZONE` | Your time zone, like `America/New_York`. | `client/identity/USER.md` |
| `YOUR_PAYMENT_SYSTEM` | What takes your money, like Stripe. | `core/config/systems.md` |
| `YOUR_CRM_SYSTEM` | What holds your contacts, like GoHighLevel. | `core/config/systems.md` |
| `YOUR_PRIMARY_MODEL` | The AI model the agent runs on. Check it is a current model. | `client/operating/AGENTS.md` |

---

## 5. Find every blank you have left

Run this from the folder. It shows every placeholder still waiting:

```bash
grep -rn "YOUR_" . --exclude-dir=.git --exclude-dir=extras --exclude=PLACEHOLDERS.md --exclude=START-HERE.md
```

When it shows nothing, every blank is filled.

---

## 6. Set it up in 8 steps

Do them in order. Do not move on until each check passes. Every step has more detail in [SETUP.md](SETUP.md).

**Step 1. Copy the files.**
Copy the `core` and `client` folders into the agent's workspace.
*Check:* `core/rules/` has 7 files.

**Step 2. Set the owners and lock the inbox.**
Put both owners' real WhatsApp numbers in `client/identity/OWNER.md`.
Then open OpenClaw's `openclaw.json` and set WhatsApp to only take messages from those numbers:

```
channels.whatsapp.dmPolicy  : allowlist
channels.whatsapp.allowFrom : [ the owner numbers, plus every number in OWNER.md ]
```

*Check:* Each owner texts the agent and gets a reply. Then someone not on the list texts it and gets **nothing**.

**Step 3. Name your two systems.**
In `core/config/systems.md`, fill in your payment system and your CRM.
*Check:* `grep -rn "YOUR_" core/` only shows `core/config/systems.md`.

**Step 4. Fill in the client files.** Go in this order:

1. `client/identity/`: who the agent is, the owners, the business
2. `client/connections/TOOLS.md`: your tool logins
3. `client/operating/`: the daily rules and check ins
4. `client/knowledge-base/`: make the 3 files the agent is told to load (`vault-staff-permissions.md`, `vault-reporting-rules.md`, `vault-writing-standards.md`). Or delete the lines that load them. They do not come with this repo.
5. `client/crons/`, `client/prompts/`, `client/scripts/`

*Check:* the command in part 5 above shows nothing.

**Step 5. Put the agent in a box.**
Install a container runtime and turn OpenClaw's sandbox on. Put the list of blocked tools under the **sandbox** tool policy.
*Check:* Ask the agent to run a command, read a file outside its folder, and read an owner's inbox. All three must **fail**. If they work, the box is not on.

**Step 6. Plug it into OpenClaw.**
Run the commands in SETUP.md step 6. They turn on the send log and the memory at session start.
*Check:* `openclaw config validate` passes.

**Step 7. Run the 10 tests.**
They are in SETUP.md step 7. Each takes about a minute.
*Check:* all 10 pass. **Any fail means stop and fix it** before the agent talks to a real client.

**Step 8. Hand it over.**
Give the owners the test results, a plain list of what the agent can and cannot reach, and the KNOWN AND OPEN part of [README.md](README.md).

---

## 7. Safety musts. Do not skip these.

1. **Never leave an inbox open.** Every channel gets an allowlist.
2. **The sandbox must be on.** Without it, the blocked tools list blocks nothing.
3. **Whoever holds an owner's phone is the boss.** If a phone is lost, the other owner texts the agent to remove that number right away.
4. **Read the two backup scripts before you use them.** They copy passwords, and one uploads them to Google Drive without encryption.
5. **Never put real numbers, emails, or keys in a public copy of this repo.** Fill them in only on the agent's own computer.

---

## 8. Check the repo still works

Run these from the repo folder:

```bash
python3 -m unittest discover -s tests -v
python3 tests/ci_checks.py all
```

Both should pass. Passing tests do not prove a live install is safe. Only the 10 tests in step 7 do that.

---

## Need help?

We build, install, and run AI agents for businesses.

* See how it works: [puestario.com/how-it-works](https://puestario.com/how-it-works)
* Watch it live: [puestario.com/live](https://puestario.com/live)
* Talk to us: [puestario.com](https://puestario.com)
