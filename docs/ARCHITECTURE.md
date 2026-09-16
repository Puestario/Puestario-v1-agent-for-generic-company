# Open the agent

[Español](es/ARQUITECTURA.md) · [Interactive version](https://puestario.com/agent-guide)

![A message passes through permission checks to approved tools. Company files are private; recovery copies are encrypted.](assets/agent-map-en.svg)

## Follow one request

1. **A person asks:** “Read today's sales.”
2. **OpenClaw receives the message:** it supplies the actual sender and chat.
3. **Puestario checks permission:** an unknown person or unapproved source is blocked.
4. **Online AI helps choose an allowed action.** It receives the context needed for the request; it cannot invent the sender's identity or grant itself access.
5. **A protected tool reads the approved source.** Access is checked in code. The reply is checked before delivery too.

The picture is a teaching map. It does not connect to a real agent.

## The three places

| Place | What belongs there |
|---|---|
| Public GitHub repo | Reusable code, fake examples, instructions and tests |
| Private company folder on the Mac | Programs, generated instructions, sign-ins, permissions, notes, jobs and records |
| Separate recovery storage | Encrypted backup; keep its private key somewhere else |

`managed/install.py` builds the company folder. `managed/runtime.py` writes its seven instruction files and OpenClaw settings. `managed/control.py` checks people and operations. `managed/adapters.py` talks to approved apps. `managed/backup.py` encrypts and restores.

The operator chooses each administrator during setup. The agent's shared instruction files do not contain their phone numbers, private notes or passwords. Staff do not get a general file browser or terminal.

The Mac is local; the model and connected apps may be online. Read [the limits](RELEASE-STATUS.md) before planning the job.
