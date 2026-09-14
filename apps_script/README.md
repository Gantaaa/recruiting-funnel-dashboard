# Apps Script automation

The weekly leadership report, as a single time-driven job bound to the Google
Sheets workbook. `runWeeklyReport()` is the only entry point:

```
runWeeklyReport()
  ├─ refreshSnapshot()          append this week's KPIs to Weekly_Snapshots
  ├─ getMetrics()               read the six KPI tiles by named range
  ├─ generateNarrative()        ask an LLM to write the executive summary
  ├─ buildSlides()              copy the template deck and fill it in
  │    ├─ insertSheetChart_()   pull live charts from the workbook
  │    └─ buildAtRiskTable_()   requisitions open past the threshold
  └─ log_()                     write the outcome to the Logs tab
```

Every step is a small named function so it can be run on its own from the Apps
Script editor when one part misbehaves, and the whole thing is re-runnable:
`refreshSnapshot()` will not append a second row for a day it has already
written.

## Why an LLM is in the loop at all

The numbers are not the hard part — assembling them into the two paragraphs a
VP of Talent actually reads is. The prompt is given the exact current and prior
week figures and told to use only those, so the narrative cannot invent a
number that is not on the dashboard. The model writes the framing; the
spreadsheet owns the arithmetic.

## Setup

1. Open the workbook, then **Extensions → Apps Script**.
2. Paste `Code.gs` in, and set the manifest to match `appsscript.json`
   (**Project Settings → Show "appsscript.json" manifest file**).
3. Make a Google Slides deck to act as the template. Give it five slides and
   use these placeholders wherever the values should land:
   `{{WEEK_OF}}`, `{{OPEN_REQS}}`, `{{HIRES}}`, `{{TTF}}`, `{{OFFER_ACCEPT}}`,
   `{{HC_VS_PLAN}}`, `{{NARRATIVE}}`.
4. Under **Project Settings → Script Properties**, add:

   | Property | Required | Purpose |
   |---|---|---|
   | `LLM_API_KEY` | yes | API key for the narrative step |
   | `TEMPLATE_ID` | yes | File ID of the Slides template |
   | `REPORT_FOLDER` | no | Drive folder to file generated decks in |
   | `REPORT_EMAIL` | no | Recipient for the emailed report |

   Script Properties is the only place the key lives. It is never committed,
   never hardcoded, and never written to a cell.

5. Confirm the workbook has these named ranges pointing at the Exec_Overview
   tiles: `KPI_OpenReqs`, `KPI_Hires`, `KPI_TTF`, `KPI_OfferAccept`,
   `KPI_FunnelConv`, `KPI_HCvsPlan`.
6. Run `runWeeklyReport()` once by hand and approve the OAuth scopes.
7. Run `setupTrigger()` once to schedule it for Monday mornings.

## Deploying with clasp

```bash
npm install -g @google/clasp
clasp login
cp .clasp.json.example .clasp.json   # then paste in your script id
clasp push
```

`.clasp.json` is gitignored because it contains a script id specific to your
own copy of the workbook.

## The email step

`sendReportEmail()` is written and working but left commented out, along with
its call in `runWeeklyReport()`. Enabling it requires the Gmail scope and sends
to a real inbox, which is not something a demo should do on a timer. To turn it
on, uncomment both, set `REPORT_EMAIL`, and re-authorise.
