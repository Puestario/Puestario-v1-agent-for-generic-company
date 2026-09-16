# systems.md — the two values core/ needs

`core/` is never edited. The rules in `core/rules/` are written to be identical
on every install so a newer `core/` can be pulled in without disturbing
anything a client filled in.

Two values are the exception: the rules have to name the systems this
business actually uses. They live here, in one file, and the rules point at
them by name.

**This is the only file inside `core/` that gets edited, and it is edited once.**
The other file in this folder, `reserved.md`, is never edited.

---

| Value | What it is | Example |
|---|---|---|
| `YOUR_PAYMENT_SYSTEM` | Whatever actually takes the money | Stripe |
| `YOUR_CRM_SYSTEM` | Whatever holds the contacts | GoHighLevel |

---

## Fill these in

- **Payment system:** YOUR_PAYMENT_SYSTEM
- **CRM system:** YOUR_CRM_SYSTEM

---

Rules that read this file:

- `core/rules/04-finding-a-persons-payments.md` — uses the payment system and
  the CRM in its four search steps.

Who the owners are is not a system value. It lives in
`client/identity/OWNER.md`, and every rule that needs an owner points there.
