# extras/ — optional pieces, not part of the base install

The base install is one job, one agent: the files in `core/` and `client/`.
Nothing in `extras/` is loaded, counted, or checked by SETUP.md, and the
placeholder checks in PLACEHOLDERS.md skip this folder. Copy in what the job
needs, fill it in where you put it, and leave the rest here.

| Folder | What it is | Came from |
|---|---|---|
| `agents/` | Four sub-agent role definitions: operator, researcher, industry researcher, ad architect. A desk that runs one job does not need any of them. | The reference install's multi-agent phase. |
| `fitness/scripts/` | `progress_photos.py` downloads a client's progress photos from one coaching platform; `build_before_after.py` renders a comparison card. Both are shaped to one platform and one brand. | A fitness coaching desk. |
| `fitness/TOOLS-skool.md` | The Skool community login block for `client/connections/TOOLS.md`. | The same desk. |
| `fitness/heartbeat-checks.md` | The Stripe and Meta Ads morning checks for `client/operating/HEARTBEAT.md`. | The same desk. |

Adding a sub-agent or a script is a change to the desk's tools. On a live
install that is reserved change 2 in `core/config/reserved.md`: an owner asks
for it on WhatsApp from their verified number, and it gets a line in
`client/memory/decisions.jsonl`.
