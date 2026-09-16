# Report a security concern privately

Email **info@puestario.com** with the subject **Security report — Agent Desk**. This is Puestario's existing business contact; no dedicated response-time guarantee is offered by this pilot.

Include the public release/commit, affected component, expected behavior and a minimal example with fictional data. Do not email passwords, live tokens, client records, chat histories or recovery keys. If sensitive material is needed, ask for a secure transfer method first.

Do not open a public issue for an unpatched vulnerability. We will investigate, agree on a disclosure plan where possible, and publish a fix or limitation. No bounty or specific response deadline is promised.

## Scope and supported versions

Only the latest tagged managed pilot is maintained. Earlier prompt-based versions remain in history for reference and should not be used as the current installation guide. The pilot has not completed a real Mac/phone/business-app acceptance run.

The model cannot supply its own sender identity. The host checks the sender, permissions and destination. General shell, browser and payment tools are absent. Administrators can manage approved people from verified private chat; local OS administrators remain trusted and can change the machine.

Credentials are stored in restricted local files outside the model workspace. This implementation does **not** claim all tokens live in macOS Keychain. Encryption at rest on the Mac depends on the operator enabling FileVault. Backups use age encryption; retain the private recovery key elsewhere.

Prompt instructions do not prove isolation. Test the actual pinned runtime, container, app scopes and blocked operations using [ACCEPTANCE.md](docs/ACCEPTANCE.md).

## Preventing accidental publication

The company folder must live outside the checkout. CI checks common token formats, unexpected phone/email values and private file paths in tracked content and fetched history. This is a targeted check, not a complete secret-detection service or security audit. Review every diff before pushing.

If a credential is published, revoke/rotate it immediately, then coordinate history cleanup. Deleting its current file alone does not remove old commits, forks or copies.

## Español

Envía un correo a **info@puestario.com** con el asunto **Reporte de seguridad — Agent Desk**. Describe el problema con datos inventados. No adjuntes claves, conversaciones, datos de clientes ni llaves de recuperación. No publiques una vulnerabilidad sin corregir en un issue público.
