# Start here

[Español](docs/es/EMPIEZA-AQUI.md)

## 1. What are we building?

A helper for one company's staff. They ask on WhatsApp. The software checks who is asking, uses an approved tool, and sends back the result.

The Mac holds the setup. Online AI helps understand requests. Only the data needed for those requests is sent to the chosen provider. A Mac in the office does not make the whole system offline.

[Open the picture](docs/ARCHITECTURE.md) · [Explore the agent](https://puestario.com/agent-guide)

## 2. What do I need?

- A dedicated Mac and an operator account that staff do not share.
- A dedicated WhatsApp account and verified administrator numbers.
- Two trusted administrators. They can belong to your company; no Puestario founder is preloaded.
- Approved model and business-app accounts, with the needed access.
- The software versions in [the installer guide](docs/MANAGED-INSTALL.md).
- A safe place for the recovery key, separate from the Mac and backup copies.

In the code, administrators are called `founders`. That is a role name, not a requirement to hire or grant access to Puestario.

The paid services, hardware, phone, AI usage, storage and device management are not included in the free code. Agree on each cost before installing. Setup time has not been measured on a clean Mac yet.

## 3. Fill in one form

Copy [company.example.json](managed/company.example.json) into a private folder outside this repo. Name the private copy `company.json`.

Change the company name, agent name, time zone, model and both administrator names/numbers. Verify each number with its actual owner. The example numbers are fictional; a normal install refuses them. The `--staging` option is only for fake offline tests and cannot become Ready.

There are no passwords in this form. Sign-ins happen later, through the local terminal or the provider's browser page. Do not put keys into chat or instruction files.

## 4. Follow one installation path

Follow [the complete installer guide](docs/MANAGED-INSTALL.md) in order:

1. Download a reviewed release and prepare the software.
2. Run the installer with your private form. It copies the required programs and generates the seven instruction files.
3. Connect the model and phone in the new company's isolated profile.
4. Open Setup from an administrator's private chat. Connect one approved app.
5. Add approved people, test the first job, and test what must be blocked.
6. Make an encrypted backup and prove you can restore it. Restored work stays paused.
7. Record all acceptance results, close Setup and check Ready.

If a check fails, stop and fix it. A green code test or a successful install command is not proof that the phone, app permissions or container are working.

## 5. What stays private?

The company folder contains sign-ins, notes, messages, permissions and records. Keep it outside GitHub. Backups are encrypted `.age` files; the private recovery key is stored separately. Never upload a real company folder or a support log into an issue.

[Report a security problem privately](SECURITY.md) · [What this pilot still needs](docs/RELEASE-STATUS.md)
