# heartbeat-checks.md — optional daily checks for HEARTBEAT.md

These two checks were written for a fitness coaching desk that took payments
on Stripe and ran Meta ads. They are not part of the base install. Paste the
ones you need into `client/operating/HEARTBEAT.md`, rename the heading to the
system the desk actually reads (the payment system and CRM are named in
`core/config/systems.md`), and delete the rest.

A heartbeat check is a read. It never sends, charges, refunds or edits.

## STRIPE (once per day — morning check)
- Pull yesterday's revenue and today's charges
- Alert only if: revenue is $0 for the day by noon, or a charge fails/refunds

## META ADS (once per day — morning check)
- Pull last 24h spend + CTR + any campaigns with 0 impressions
- Alert if: a campaign stops running, CTR drops sharply, daily budget hits cap early
