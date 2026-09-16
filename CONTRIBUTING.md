# Help improve the desk

Start with an issue for a bug or a small, clear proposal. Use fictional company information. For vulnerabilities, use [the private security contact](SECURITY.md).

1. Fork the repo and create a branch.
2. Keep the change focused. Explain the user problem and the new behavior.
3. Add meaningful tests for permissions, recovery or new app behavior. Test both allowed and denied requests.
4. Run the checks in [README.md](README.md). Node and real age encryption must be available; skipped encryption tests are not release evidence.
5. Update English and Spanish instructions when the behavior changes.
6. Open a pull request with what changed, how it was tested, and what is still unproven.

Never commit live company configuration, tokens, private memory, chat logs, backup archives or recovery keys. Keep paid-client agreements and private support evidence outside this repository.

Contributions are provided under this repository's MIT license. Only submit material you have the right to contribute; retain dependency notices. This does not grant rights to use Puestario branding as an endorsement.

## Releases and the website guide

Follow [the release checklist](docs/RELEASING.md). A website illustration is not automatically updated when code changes. Refresh its reviewed source snapshot, file explanations and version before claiming it shows a new release.

## Español

Abre un issue con datos inventados, crea una rama y envía un pull request. Explica el cambio y sus pruebas. Actualiza ambos idiomas. Nunca subas información de un cliente. Los problemas de seguridad se reportan por privado.
