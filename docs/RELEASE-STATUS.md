# Managed pilot status

**0.2.0-pilot — developer review and controlled testing. Not yet qualified for client handover.**

## Implemented

- An installer that copies reviewed programs and writes all seven workspace instruction files.
- Verified sender/account/conversation context from the pinned OpenClaw plugin.
- Independent administrator authority, temporary Setup, staff and group grants, private notes, reminders and bounded reports.
- Protected tools and outbound checks. No general shell, browser, cross-chat, payment or customer-email tool.
- Scoped Sheets read/write, Calendar read, Stripe charge read and GHL contact read.
- Local sign-in; credentials outside shared instructions. They are restricted files, not a promised Keychain integration.
- Encrypted offline recovery snapshots, optional explicit-folder Drive upload, hash checks and paused restore.
- Generic examples and checks that refuse example administrator numbers during normal installation.

## Evidence

The automated workflow runs on Linux and macOS with Python 3.11 and 3.13. It requires Node, installs checksum-verified age 1.3.2, checks source/docs and runs the regression suite. See the [actual workflow results](https://github.com/Puestario/Puestario-v1-agent-for-generic-company/actions/workflows/tests.yml); a badge describes those code checks only.

Local release results and isolated runtime validation are recorded in the GitHub prerelease notes. An offline fixture is never accepted as evidence for a live company.

## Still required on a real Mac

The complete [acceptance checklist](ACCEPTANCE.md): live WhatsApp routing and delivery, both administrator phones, actual provider/model and fallback, real app scopes, Docker execution, private data isolation, restart/power recovery and an encrypted recovery drill.

The prepared 30-minute visit remains a target, not measured evidence. Apple Business Manager alone is not device management. Model/API charges, phone, hardware, MDM, storage and app licenses must be agreed separately.

## Limits

- WhatsApp text only. Telegram, voice and media support are not installed.
- Actual group membership must be reviewed by the operator; it is not automatically monitored.
- Calendar: next 50 events. Stripe: at most 100 charges from the last 24 hours. GHL: at most 100 contacts in one location. Partial results are labeled.
- Sheets writes replace only the configured full range and use read-back. Do not grant a wider range than needed.
- Reports are small outputs from one approved source, not full finance reconciliation or a complete company knowledge system.
- Backup requires a stopped gateway. The optional Drive uploader does not create a nightly backup schedule.
- Local OS administrators remain trusted. Separate machines do not by themselves guarantee data isolation.
- No combined vendor spending cap, automatic fleet rollout, customer messaging or money movement.
- Do not upgrade the pinned runtime without fresh compatibility tests.

## Español

El código tiene pruebas automáticas, pero falta la prueba completa con Mac, teléfono y aplicaciones reales. Las copias se cifran y la recuperación queda pausada. No se incluyen pagos, mensajes a clientes, control general de la computadora ni Telegram. Una prueba automática aprobada no significa que una instalación real esté lista.
