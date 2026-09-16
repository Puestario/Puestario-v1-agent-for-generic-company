# HEARTBEAT.md
# Agent periodic checks — runs every ~30 min via heartbeat poll
# Quiet hours: YOUR_QUIET_HOURS_START – YOUR_QUIET_HOURS_END (HEARTBEAT_OK unless truly urgent)
# Track last check times in: client/memory/heartbeat-state.json

## EMAIL (check every 2-3 hours)
- Scan YOUR_OWNER_EMAIL and YOUR_OWNER_2_EMAIL for unread messages
- Alert if: client question, payment issue, urgent reply needed, anything from key contacts
- Skip if: newsletters, receipts, automated notifications

## CALENDAR (check every heartbeat)
- Alert if any event starts within the next 2 hours
- Give a heads-up 30 min before meetings
- Key recurring events to watch: (list yours in YOUR_RECURRING_EVENTS)

## Other daily checks
- Only the checks in this file run. Optional checks for a payment system and an
  ad platform are in `extras/fitness/heartbeat-checks.md`; paste one in here if
  the desk's job needs it, and name the real system, not a brand the desk does
  not use.

## Stay quiet (HEARTBEAT_OK) when:
- Nothing new since last check
- It's quiet hours
- All checks passed with nothing urgent
- You already alerted about something and are waiting for a response
- A new lead comes in and your automation handles it automatically
