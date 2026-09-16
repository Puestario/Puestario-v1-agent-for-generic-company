# Daily Reports — Format & Rules

Daily report files live here. Format: `YYYY-MM-DD.md`

## Why This Folder Exists
The agent reads these files directly before generating reports. It never estimates or recalls numbers from memory — it reads the actual file for the date in question.

## File Naming
- Today's report: `2026-08-27.md` (always use full ISO date)
- Never abbreviate the year or use other date formats

## Minimum Required Contents Per Report

```markdown
# Daily Report — YYYY-MM-DD

## Revenue
- [list transactions with amounts]
- Total: $X,XXX.XX

## Leads
- New leads: X
- Source: [channel]

## Ad Spend
- Meta: $XXX.XX
- Other: $XXX.XX
- Total: $XXX.XX

## Notes
[anything unusual, one-time events, flags]
```

## Report Generation Rules (enforced in AGENTS.md Section 7)
1. Agent loads this file before generating any report
2. If the file is missing, agent flags it — never estimates
3. Weekly reports cross-reference all 7 daily files for the week
4. Every report includes a "Sources:" verification line
