# Knowledge Base — Vault Files

This folder holds detailed context files that are too large for MEMORY.md.
The agent loads these on demand when needed for a specific task.

## Naming Convention
All vault files follow the pattern: `vault-{topic}.md`

## Recommended Vault Files to Create

| File | Purpose |
|------|---------|
| `vault-staff-permissions.md` | Staff names, WhatsApp numbers, allowed actions |
| `vault-reporting-rules.md` | Report format, what to include, what to skip |
| `vault-writing-standards.md` | Brand voice, tone, words to avoid, style rules |
| `vault-business-context.md` | Business strategy, owner story, offer details |
| `vault-client-roster.md` | Active clients, programs, status |
| `vault-systems-connected.md` | Tool configs, integration notes |

## How to Add a Vault File
Tell your agent: "Save [topic] to the vault" — it will create the file and add a pointer to MEMORY.md.

## How the Agent Uses Vault Files
The agent reads vault files on demand. Example triggers:
- "Before generating any report, load vault-reporting-rules.md"
- "When generating content, load vault-writing-standards.md"
- "When a staff member messages, load vault-staff-permissions.md"
