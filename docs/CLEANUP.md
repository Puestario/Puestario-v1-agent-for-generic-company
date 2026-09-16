# Moving to the managed pilot

The initial public template used `core/` and `client/`. Release 0.2.0-pilot replaces that path with `managed/` and the two OpenClaw plugins.

## What changed?

- One private company form replaces scattered placeholders.
- The installer creates the workspace OpenClaw actually reads.
- Permission decisions run in protected code, not only in prompts.
- Real company state stays outside the source checkout.
- The unencrypted backup scripts and preloaded founder decisions are removed from the active tree.
- Optional fitness scripts, generic role prompts and unrelated reference documents are no longer part of the installation.

Old public commits still exist. This change does not rewrite history or erase copies. No private repository history is imported.

## Existing installations

Do not run `init` over an existing company. Do not copy old credential files, memory logs or owner lists into the new repo.

Stop and review the existing desk, take an approved encrypted recovery copy, create a separate managed installation, reconnect each approved service, and complete every acceptance test. Decide manually what business information should be migrated. Keep the old desk stopped while reviewing phone/session identity to avoid duplicate replies.

This release does not automatically convert an old `core/` + `client/` deployment. Changing Git branches does not migrate a live company.

## Español

La versión nueva usa `managed/`. El instalador crea una carpeta privada aparte. No ejecutes `init` sobre una empresa existente ni copies claves o recuerdos antiguos al repo. Prepara una copia cifrada, crea una instalación separada y repite todas las pruebas. No hay migración automática.
