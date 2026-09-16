# Puestario installer guide

Status: implementation candidate. Complete the clean-Mac pilot before installing for a client.

## 1. Prepare once, before the visit

Use one company per Mac and a dedicated Puestario operator macOS account. Staff must not receive that account password, shared remote desktop access or macOS administrator access. Enable FileVault, automatic security updates, screen lock and the agreed MDM controls. Apple Business Manager alone does not apply device policy; connect the chosen MDM. Keep recovery access with Puestario.

Install Git, Python 3.11 or newer, Node 22.22 or newer supported by the pinned runtime, OpenClaw **2026.5.27**, Docker Desktop or an approved Docker-compatible runtime, and age **1.3.2**. Confirm vendor licensing/costs for the client. Use vendor installers and checksums. Do not run an unreviewed remote shell script.

```bash
npm install -g openclaw@2026.5.27
openclaw --version
python3 --version
node --version
docker info
age --version
```

Clone the public source. No GitHub account or token is needed to read it. Choose the exact reviewed commit from the pull request, not the moving default branch. Do not place a GitHub token in company files. Remove persistent GitHub access from a handed-over machine if not needed.

```bash
git clone https://github.com/Puestario/Puestario-v1-agent-for-generic-company.git ~/puestario-source
cd ~/puestario-source
# Enter the full reviewed 40-character commit when prompted.
read -r PUESTARIO_RELEASE
git checkout --detach "$PUESTARIO_RELEASE"
python3 -m unittest discover -s tests -v
python3 tests/ci_checks.py all
python3 tests/public_scan.py --history
docker build -f runtimes/openclaw/Dockerfile.managed -t puestario-sandbox:2026.09.16 .
docker image inspect puestario-sandbox:2026.09.16
```

The Docker base is pinned by content digest. Save the final image ID with the pilot record. The image, Python path, OpenClaw version and release must pass checks again after upgrades.

## 2. Fill one company form

Copy `managed/company.example.json` to a private file outside Git. Replace the example numbers with both administrators’ **independently verified** phone numbers. Use the client's company ID, name, agent name, model, time zone and language. Choose approved model fallbacks or leave the list empty. Never place passwords or private personal facts in company-wide instructions.

Use one unique root outside the checkout, for example `/Users/puestario/Clients/example-office`. The root, protected release and public workspace must not overlap another company's installation.

```bash
python3 -m managed.cli --root /Users/puestario/Clients/example-office init --company /Users/puestario/company.json --revision "$PUESTARIO_RELEASE"
```

This copies reviewed programs into a separate protected release folder, creates private state and renders the read-only agent workspace. It refuses to overwrite an existing company. `--staging` is for synthetic offline fixtures only and cannot pass acceptance. The default private gateway port is 18791; choose a different `--port` only if it is free.

For the remaining commands, work from that company's protected `release` directory. Always supply the exact company root. Never run an unscoped OpenClaw command against a personal/default profile.

## 3. Connect the model and phone

```bash
python3 -m managed.cli --root /Users/puestario/Clients/example-office openclaw models auth add
python3 -m managed.cli --root /Users/puestario/Clients/example-office openclaw channels login --channel whatsapp --account default
python3 -m managed.cli --root /Users/puestario/Clients/example-office apply
python3 -m managed.cli --root /Users/puestario/Clients/example-office openclaw gateway run
```

Complete the supported provider's local sign-in, then scan the QR using the dedicated business phone. Model credentials remain in this company's gateway state. Check that the agent can answer from the actual chosen model; record a fallback separately. Keep the account-recovery and phone/SIM ownership record outside the agent.

The gateway uses loopback and a generated token. Do not expose its port publicly. Add approved remote administration separately through managed device access.

In another terminal, run `doctor` with the same root. The plugin must load with its tool, four hooks, owner command and scheduler. No diagnostic error is acceptable. `openclaw plugins inspect puestario-control --runtime --json` through the scoped wrapper checks registrations. Replies are text-only and limited to 3500 characters; test the actual transport's rendering and reply-tag handling in the pilot.

The plugin compares live runtime settings with the desired settings. Until they match, staff and scheduled work remain paused. Saving a file is not the same as applying it. A restart closes temporary Setup; reopen it from a verified founder DM as needed.

## 4. Connect only the app needed for the first job

Credentials never go into WhatsApp, company instructions, a command argument or model memory.

For Google, enable the relevant APIs in an approved Google project. Use a Desktop OAuth client, the agreed scopes and provider verification where required. Download its client JSON to the protected operator account. The local command opens the browser, uses state plus PKCE, and saves the result outside the agent work area.

```bash
python3 -m managed.cli --root /Users/puestario/Clients/example-office connect-google google-main --client /Users/puestario/google-desktop-client.json --scope sheets-read --scope calendar-read
```

Use `sheets-write` only when the approved job needs edits. For Stripe/GHL, use `connect-token stripe-main` or `connect-token ghl-main`: the local terminal asks for the restricted credential without displaying it. Use a separate account/key per client. A saved credential is reported as **not yet connected** until an actual resource read succeeds. Confirm the returned account is the correct company. GHL needs location-read and contact-read scopes for this check.

In a founder DM, open Setup and configure a named resource. Examples of exact direct commands:

```text
/desk open 15
/desk {"operation":"resource.put","args":{"name":"sales","resource":{"kind":"google-sheets","connection":"google-main","spreadsheet_id":"replace-with-real-sheet-id","range":"Sales!A1:D10","writable":false}}}
/desk {"operation":"connection.check","args":{"resource":"sales"}}
/desk {"operation":"person.put","args":{"name":"Ana","number":"+12025550103","tester":true,"resources":{"sales":["read"]}}}
/desk {"operation":"group.put","args":{"id":"1234567890@g.us","name":"Staff","members":["+12025550103"],"resources":{"sales":["read"]}}}
```

The values above are fictional. Get the real group ID locally with the scoped channel-directory tools and verify its actual membership. Everyone in a group can read posted messages, including people who cannot command the agent. Grant only information approved for **every real member**. Review membership changes operationally; this release does not monitor WhatsApp group membership automatically.

Google Sheets: exact bounded range, reads and optional full-range RAW writes with read-back. Google Calendar: next 50 events, read-only. Stripe: up to 100 charges from the last 24 hours, not a full accounting report. GHL: up to 100 contacts from one location, not full CRM access. Incomplete results are labelled. Additional apps/actions need reviewed adapters.

## 5. Schedule useful work

A person may schedule a reminder only to their own DM. A founder may name an approved person or a group with explicit data grants. Time follows the company time zone. Use one future ISO time, a daily HH:MM, or an interval in minutes. This first release does not accept arbitrary shell cron expressions.

The 15-second scheduler stores jobs outside the model workspace. It rechecks current access before every run. Repeating jobs catch up once after downtime. A possible send with no reliable receipt is marked **unverified** and is not retried automatically; check the recipient before replacing it. This prevents blind duplicate sends. Sent means transport receipt, not read by a person. A report too large for one message is blocked; narrow the resource.

Changing access invalidates existing sessions. Send `/new` in affected chats before continuing. This protects against old model history retaining removed access. Old messages already delivered to phones, or requests already handed to an external service, cannot be recalled by changing access.

## 6. Startup and outages

`service-file` generates a company-specific LaunchAgent plist. Review it, place it in the dedicated operator's `~/Library/LaunchAgents/`, then enable it with the normal `launchctl bootstrap gui/<uid> <file>` workflow. The tool does not enable it automatically. Do not create two services for one profile.

A LaunchAgent starts after that macOS user logs in. FileVault can require a person to unlock the Mac after a full restart or outage. Test the actual restart and power-loss procedure. Do not promise unattended cold-boot recovery until the chosen MDM/hardware setup proves it. Keep Docker running for that user. Prevent sleep as agreed, allow screen lock, and consider a UPS.

If internet/model/phone access fails, the agent must say the job is unavailable or leave it visibly blocked. Use local `status`, `doctor` and private gateway logs. A second founder can revoke a lost founder phone in DM with `founder.remove`; the last founder cannot be removed by chat. If both phones are lost, use the protected Mac/MDM recovery procedure: stop the gateway, verify replacements, take an encrypted backup, edit the founder record locally, increase `access_epoch`, clear checks, set `ready=false`, apply, restart and retest. This requires trusted local administrator access; it is not a staff recovery command.

## 7. Encrypted backup and restore

Create the age recovery identity on an approved recovery machine. Store the private key in Puestario's recovery vault, separate from the Mac and its backups. Only its public recipient is needed to create a backup. Never commit either company backups or recovery keys.

Stop this company's gateway first for a consistent full snapshot. The snapshot includes the actual workspace, protected state, access rules, jobs, notes, release, credentials, gateway state and evidence. This initial release provides **offline snapshots**, not a zero-downtime nightly backup service.

```bash
python3 -m managed.cli --root /Users/puestario/Clients/example-office backup --recipient age1-public-recipient-from-recovery-vault --output /Volumes/Backup/example-office-20260916.age
python3 -m managed.cli --root /Users/puestario/Restore/example-office restore --identity /Volumes/Recovery/company-age-key.txt --archive /Volumes/Backup/example-office-20260916.age
```

Use real paths and a real recipient. Restore refuses an existing destination, rejects links/unsafe archive paths and verifies file hashes. It sets Setup, pauses delivery, disables restored jobs, changes the gateway token and clears acceptance. Keep the original gateway stopped while reconciling the restored phone/session identity. Review future job times before creating replacement jobs; no backlog replay.

Optional Drive copy: install `managed/requirements-drive.txt` in the operator's private Python environment. Run `connect-google google-backup ... --scope drive-backup`, then:

```bash
python3 -m managed.drive_backup --root /Users/puestario/Clients/example-office --archive /Volumes/Backup/example-office-20260916.age --folder-id exact-client-folder-id --connection google-backup
```

With `drive.file`, the app must have been granted access to that exact folder (or create it through an approved setup flow). A folder name match is never used. Upload verifies checksum and size. Retention defaults to preview; `--prune` trashes only this company's labelled encrypted archives and keeps the newest. It never permanently deletes arbitrary folder contents.

## 8. Close and hand over

Follow [ACCEPTANCE.md](ACCEPTANCE.md). Save the operator's real results locally. `accept` records operator attestation and hashes the evidence; it does not claim an automated proof of a human test. Offline fixtures cannot pass it.

```bash
python3 -m managed.cli --root /Users/puestario/Clients/example-office doctor
python3 -m managed.cli --root /Users/puestario/Clients/example-office accept founders --evidence /Users/puestario/test-results/founders.txt --operator Operator
```

Repeat for each required check. Then `/desk close` must return Ready. Save the installed commit, image ID, configuration revision, acceptance evidence, support contact and recovery location. Later protected company/app changes require fresh checks.

## Costs to agree before activation

Record the responsible payer and current price for: Mac/UPS, phone/SIM plan, MDM, model provider, Docker licensing if applicable, each connected app, Google storage/OAuth project, backup storage, support and custom adapters. Model usage is separate from phone and SaaS bills. Use provider-enforced budgets where available and confirm alert recipients. This release does not enforce a combined spending cap across vendors. Do not promise one.

Primary implementation references: [OpenClaw trust model](https://docs.openclaw.ai/gateway/security/trust-model), [plugin tools](https://docs.openclaw.ai/plugins/agent-tools), [sandbox](https://docs.openclaw.ai/gateway/sandboxing), [Google desktop OAuth](https://developers.google.com/identity/protocols/oauth2/native-app), [Sheets update](https://developers.google.com/sheets/api/reference/rest/v4/spreadsheets.values/update), [Stripe charges](https://docs.stripe.com/api/charges/list), [age](https://github.com/FiloSottile/age).
