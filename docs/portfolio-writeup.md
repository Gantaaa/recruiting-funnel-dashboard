# Recruiting Funnel Dashboard with AI-Generated Weekly Report

**Stack:** Python · Google Sheets · Apps Script · LLM API (narrative generation)
**Author:** Gantamir Gankhuyag — ggankhuy@ucsc.edu
**Project type:** Self-built prototype for learning Talent Strategy & Recruiting Operations workflows

> **Where this document sits.** This is the long-form design write-up, written
> while the project was being built. It covers the reasoning: why each KPI is
> defined the way it is, how the dashboard tabs were laid out, and how the
> automation hangs together.
>
> For what the project *is now* — including the data-quality audit of this
> workbook, the funnel bug it turned up, and the live dashboard — start at the
> [README](../README.md). Where the two disagree, the README and the code are
> current and this document is the earlier thinking. In particular: the metric
> layer has since moved into tested Python
> ([`metrics.py`](../src/recruiting_funnel/metrics.py)), the funnel
> calculation described in §5.2 was found to be wrong and corrected (see
> [kpi-definitions.md](./kpi-definitions.md)), and the `Weekly_Snapshots`
> approach in §8 was replaced by recomputing history from event dates.
>
> An "Interview Talking Points" section used to sit at §14. It was removed
> because it had gone stale against the project it describes, and because a
> design document should stand on its own rather than coach the reader on how
> to discuss it.
>
> The narrative step is provider-agnostic — any OpenAI-compatible chat
> completions endpoint works, configured in one place at the top of
> [`Code.gs`](../apps_script/Code.gs). The shipped configuration uses Groq;
> the Anthropic variant shown in §8 is an equally valid drop-in.

> **Honesty note (read this first).** This project was built end-to-end on **synthetic recruiting data** that I generated myself. It was **not deployed in production**, contains **no real candidate or company data**, and was never connected to a live ATS. The goal was to teach myself how recruiting-operations analytics actually works — the metrics, the funnel math, the reporting cadence — and to prove I can wire up a real automation pipeline (Sheets → Apps Script → AI → Slides/email). Everything below is written as if the prototype is complete and demo-ready, because it is; but I keep the "synthetic / not production" framing throughout so I can describe it accurately in an interview.

---

## 1. Executive Summary

### The business problem
Recruiting Operations teams live in spreadsheets. Every Monday a recruiting coordinator or RecOps analyst pulls a CSV export from the ATS, manually rebuilds pivot tables, recolors a few cells, and pastes screenshots into a slide deck for the weekly talent review with hiring leadership. The work is repetitive, error-prone, and the analyst spends more time *assembling* the report than *interpreting* it. By the time leadership sees the numbers, they're stale and there's no narrative explaining *why* time-to-fill jumped or *which* requisitions are at risk.

This project automates that entire loop. It turns a raw recruiting dataset into a live dashboard, computes the standard RecOps KPIs, snapshots them weekly, and uses an LLM (Claude or Gemini) to write a plain-English executive narrative that compares this week to last week, flags anomalies, and lands in a Google Slides deck and an email inbox — automatically, on a schedule.

### Why recruiting teams need this
- **Leadership wants signal, not spreadsheets.** A VP of Talent doesn't want 14 tabs; they want "we're 6 days slower to fill engineering roles than last week, and 3 of the 5 at-risk reqs are in EMEA." The AI layer produces exactly that.
- **RecOps headcount is scarce.** Most teams have one or two analysts supporting dozens of recruiters. Automating the weekly report frees a meaningful chunk of their week.
- **Consistency.** A scripted pipeline computes time-to-fill the same way every week. Manual reports drift — different people define the funnel differently.

### Manual processes this eliminates
| Manual step today | Replaced by |
|---|---|
| Export CSV, clean it, dedupe candidates | Python cleaning layer + Sheets validation |
| Rebuild pivot tables each week | Persistent pivots + Apps Script refresh |
| Recolor RAG (red/amber/green) cells | Conditional formatting rules |
| Compute week-over-week deltas by hand | Weekly snapshot tab + delta formulas |
| Write the "what happened" narrative | Claude/Gemini summary prompt |
| Paste charts into slides | Apps Script → Google Slides generator |
| Email the deck to leadership | `MailApp` scheduled trigger |

### Expected business impact (modeled, not measured)
Because this is synthetic, I'm careful **not** to claim real, audited savings. Based on the manual workflow I modeled, a weekly report that takes ~3–4 hours of analyst time to assemble collapses to a ~5-minute review-and-send. Over a year that's a plausible ~150+ analyst hours redirected from assembly to actual talent strategy. I'd validate that estimate against a real team before putting a number on a résumé.

---

## 2. Project Objectives

**Dashboard goals**
- Single source of truth for funnel, headcount, and velocity metrics.
- Drill-down from company-level rollup to recruiter / region / requisition.
- Self-updating: no manual pivot rebuilds.

**Reporting goals**
- Produce a leadership-ready weekly report with zero manual formatting.
- Always show **week-over-week change**, not just a static snapshot.
- Consistent KPI definitions across every report.

**Automation goals**
- One scheduled trigger runs the whole pipeline (refresh → snapshot → AI → slides → email).
- Idempotent and re-runnable; a failed run can be re-triggered safely.
- Logging so a human can audit what the automation did.

**AI-assisted insights goals**
- Translate numbers into an executive narrative.
- Detect and surface anomalies (a metric moving more than expected).
- Stay grounded: the model only describes data passed to it, never invents figures.

---

## 3. End-to-End System Architecture

```
                 ┌──────────────────────────────────────────────┐
                 │            SYNTHETIC DATA SOURCE              │
                 │   Python generator → Recruiting_Data sheet    │
                 └───────────────────────┬──────────────────────┘
                                         │ (CSV import / API write)
                                         ▼
        ┌────────────────────────────────────────────────────────────┐
        │                     GOOGLE SHEETS WORKBOOK                   │
        │                                                              │
        │  Recruiting_Data ──► Pivot tables ──► Dashboard tabs (8)     │
        │        │                                      │              │
        │        └────────► Data_Quality audit ◄────────┘              │
        │                                                              │
        │  Weekly_Snapshots  ◄─── appended each Monday by Apps Script  │
        └───────────────────────────────┬──────────────────────────────┘
                                         │
              ┌──────────────────────────┼───────────────────────────┐
              ▼                          ▼                           ▼
   ┌──────────────────┐      ┌────────────────────────┐    ┌──────────────────┐
   │  PYTHON LAYER     │      │   APPS SCRIPT ENGINE   │    │  CLAUDE / GEMINI │
   │  (offline / Colab)│      │  (bound to workbook)   │    │       API        │
   │ • generate data   │      │ • refreshSnapshot()    │    │ • week-vs-week    │
   │ • validate (13)   │      │ • getMetrics()         │───►│   narrative       │
   │ • compute metrics │      │ • generateNarrative()  │◄───│ • exec summary    │
   │ • export JSON     │      │ • buildSlides()        │    │                   │
   └──────────────────┘      │ • sendSummaryEmail()   │    └──────────────────┘
                              └───────────┬────────────┘
                                          ▼
                        ┌────────────────────────────────┐
                        │   GOOGLE SLIDES (auto-built)   │
                        │   + EMAIL to leadership inbox  │
                        └────────────────────────────────┘
```

**Component roles**

- **Synthetic dataset / `Recruiting_Data` sheet** — the raw event log; one row per candidate-requisition. Everything else derives from it.
- **Pivot tables** — pre-aggregate the raw rows into the shapes each dashboard tab needs (funnel counts, headcount by region, source mix).
- **Dashboard tabs** — the human-facing views. Charts + KPI tiles + filters.
- **`Weekly_Snapshots`** — an append-only history of KPI values, one row per week. This is what makes week-over-week comparison possible.
- **Apps Script engine** — the orchestrator. It's bound to the workbook and does everything that needs to happen *inside* Google's ecosystem: refreshing, snapshotting, calling the AI API, building slides, emailing.
- **Python layer** — runs *outside* Sheets (Colab / local). It handles the heavier data work that's awkward in formulas: dedup logic, validation rules, statistical anomaly detection, trend fitting. In this prototype Python prepares/validates the dataset before it lands in Sheets; in a production version it could run as a Cloud Function.
- **Claude / Gemini** — the narrative brain. Apps Script sends it a compact JSON of this-week-vs-last-week metrics and gets back an executive summary.
- **Slides + email** — the delivery layer.

**Why split work between Apps Script and Python?** Apps Script is the only thing that can natively touch Sheets/Slides/Gmail and run on Google's triggers, so it owns orchestration and delivery. Python is better at statistics and data wrangling, so it owns the analytical heavy lifting. Keeping them separated by responsibility is a deliberate design choice, not an accident.

---

## 4. Synthetic Dataset Design

The core table is `Recruiting_Data`: **one row per candidate per requisition**.
The shipped dataset is 750 rows across 70 requisitions, spanning roughly ten
months, generated by [`generate.py`](../src/recruiting_funnel/generate.py) from
a fixed seed so it is reproducible.

The grain is the thing to hold onto: a requisition occupies as many rows as it
had applicants. Every requisition-level figure therefore has to deduplicate on
`Requisition_ID` before counting — and every one of those figures depends on
that key being coherent, which in the first version of this dataset it was not
(see [`docs/data-quality.md`](./data-quality.md)).

### Field dictionary

| Field | Type | Why it exists |
|---|---|---|
| `Candidate_ID` | string `C-#####` | Unique candidate key; needed for dedup and to count distinct people vs. applications. |
| `Requisition_ID` | string `REQ-YYYY-####` | The open role. Joins candidates to headcount; lets us count applicants per req. |
| `Team` | string | Sub-org (e.g., Platform, Growth). Granular ownership view. |
| `Department` | string | Eng / Sales / G&A / etc. Leadership rolls up here. |
| `Region` | string | NA / EMEA / APAC / LATAM. Drives regional velocity analysis. |
| `Recruiter` | string | Owning recruiter. Needed for recruiter-productivity views. |
| `Hiring_Manager` | string | The HM. Useful for HM responsiveness / bottleneck analysis. |
| `Source_of_Hire` | enum | Referral / LinkedIn / Job Board / Agency / Internal / University. Source-effectiveness analysis. |
| `Candidate_Type` | enum | External / Internal / Referral / New Grad. Different funnels convert differently. |
| `Application_Date` | date | Funnel entry point; anchors time-to-hire. |
| `Phone_Screen_Date` | date | First interview stage; used for stage conversion. |
| `Onsite_Date` | date | Later interview stage. |
| `Offer_Date` | date | When an offer was extended; anchors offer-acceptance timing. |
| `Hire_Date` | date | Start/accept date; anchors time-to-fill. |
| `Current_Stage` | enum | Applied / Screen / Onsite / Offer / Hired / Rejected / Withdrawn. The funnel position. |
| `Req_Open_Date` | date | When the requisition opened. True time-to-fill is measured from here. |
| `Time_to_Fill` | number (days) | `Hire_Date − Req_Open_Date`. The headline velocity metric. |
| `Headcount_Status` | enum | Open / Filled / On Hold / Cancelled. Drives open-req and headcount KPIs. |

> Two date anchors matter and people confuse them: **Time-to-Fill** is measured from `Req_Open_Date` (a business/planning clock), while **Time-to-Hire** is measured from `Application_Date` of the hired candidate (a candidate-experience clock). I keep both so I can speak to the difference — that's a common interview gotcha.

### Sample records

Real rows from `data/recruiting_data.csv`, showing one requisition and the
first seven of its twenty-eight applicants:

| Candidate | Dept | Region | Recruiter | Source | Req opened | Applied | Offer | Hired | Stage | TTF | Req status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C-10337 | Product | NA | Charlie Brown | University | 2025-11-26 | 2025-11-26 | 2025-12-22 | 2026-01-08 | Hired | 43 | Filled |
| C-10681 | Product | NA | Charlie Brown | LinkedIn | 2025-11-26 | 2025-11-28 | — | — | Rejected | — | Filled |
| C-10159 | Product | NA | Charlie Brown | Agency | 2025-11-26 | 2025-12-03 | — | — | Rejected | — | Filled |
| C-10245 | Product | NA | Charlie Brown | Internal | 2025-11-26 | 2025-12-03 | — | — | Rejected | — | Filled |
| C-10493 | Product | NA | Charlie Brown | Job Board | 2025-11-26 | 2025-12-04 | — | — | Rejected | — | Filled |
| C-10633 | Product | NA | Charlie Brown | LinkedIn | 2025-11-26 | 2025-12-11 | — | — | Rejected | — | Filled |
| C-10304 | Product | NA | Charlie Brown | University | 2025-11-26 | 2025-12-12 | — | — | Rejected | — | Filled |

Two things this shows. **`REQ-2025-0023` is one role, so department, region,
recruiter and open date are identical on every row** — that invariant is
asserted in [`tests/test_generate.py`](../tests/test_generate.py), because the
first version of this dataset violated it on 49 of 50 requisitions.

And **one seat, twenty-eight applicants, one hire.** Counting rows would report
this requisition twenty-eight times.

> An earlier version of this section used a hand-written sample table with
> invented recruiter names. Those names then got hardcoded into the workbook's
> Recruiter tab, which rendered four recruiters who appear nowhere in the data,
> every row reading zero. The sample above is generated from the real file for
> that reason.

---

## 5. Dashboard Design

Eight tabs. Each is fed by pivot tables off `Recruiting_Data` and a couple of helper columns. Filters are implemented with Sheets **slicers** so leadership can self-serve.

### 5.1 Executive Overview
- **Purpose:** the one screen a VP looks at. Everything else is a drill-down.
- **Metrics:** Open Reqs, Hires (this period), Avg Time-to-Fill, Offer Acceptance Rate, Headcount vs. plan.
- **Visualizations:** KPI tiles with RAG coloring + week-over-week delta arrows; a small trend sparkline per KPI.
- **Pivots:** rollups of hires and open reqs by department.
- **Filters:** Department, Region, Date range.
- **Leadership use case:** "Are we on track to hit our hiring plan this quarter, and where are we slipping?"

### 5.2 Hiring Funnel
- **Purpose:** show stage-to-stage conversion and where candidates drop.
- **Metrics:** counts at Applied → Screen → Onsite → Offer → Hired, plus conversion % between each.
- **Visualizations:** funnel chart + a conversion-rate bar chart.
- **Pivots:** count of `Candidate_ID` by `Current_Stage` (and furthest stage reached).
- **Filters:** Department, Region, Source, Recruiter.
- **Leadership use case:** "Our offer→hire rate dropped — are we losing people at offer stage (comp problem) or earlier?"

### 5.3 Headcount Tracking
- **Purpose:** plan vs. actual headcount and open-req aging.
- **Metrics:** Filled vs. Open vs. On-Hold reqs, headcount delta to plan, aging buckets (0–30 / 31–60 / 60+ days open).
- **Visualizations:** stacked bar (status by dept) + aging histogram.
- **Pivots:** `Headcount_Status` by `Department`; open-req age buckets.
- **Filters:** Department, Region, Status.
- **Leadership use case:** "Which departments have reqs aging past 60 days?"

### 5.4 Regional Performance
- **Purpose:** compare hiring velocity and volume across regions.
- **Metrics:** hires, open reqs, avg TTF by region.
- **Visualizations:** map-style/region bar charts; TTF-by-region comparison.
- **Pivots:** hires & avg TTF by `Region`.
- **Filters:** Department, Time period.
- **Leadership use case:** "EMEA is filling 12 days slower than NA — staffing or market issue?"

### 5.5 Source Effectiveness
- **Purpose:** which channels produce hires (and quality/efficiency).
- **Metrics:** hires by source, applicant→hire conversion by source, share of hires.
- **Visualizations:** bar chart of hires by source; conversion-rate comparison.
- **Pivots:** hires by `Source_of_Hire`; conversion by source.
- **Filters:** Department, Region.
- **Leadership use case:** "Referrals convert 3× better than job boards — should we lean into referral incentives?"

### 5.6 Recruiter Performance
- **Purpose:** workload and output per recruiter (used carefully — for support, not punishment).
- **Metrics:** open reqs owned, hires made, avg TTF, candidates in pipeline.
- **Visualizations:** sortable table + hires-per-recruiter bar.
- **Pivots:** hires & open reqs by `Recruiter`.
- **Filters:** Department, Region.
- **Leadership use case:** "Is anyone carrying too many open reqs and needs load rebalanced?"

### 5.7 Time-to-Fill Analysis
- **Purpose:** the velocity deep-dive.
- **Metrics:** avg/median TTF overall, by dept, by region, by source; distribution.
- **Visualizations:** box/whisker or histogram of TTF; trend line over weeks.
- **Pivots:** avg/median TTF by multiple dimensions.
- **Filters:** Department, Region, Source, Period.
- **Leadership use case:** "Median TTF is 48 days but the mean is 71 — a few stuck reqs are dragging the average."

### 5.8 Data Quality Audit
- **Purpose:** trust. If leadership doesn't trust the data they ignore the dashboard.
- **Metrics:** % rows missing key dates, duplicate candidate flags, date-logic violations, orphan reqs.
- **Visualizations:** an issues table with counts + a "data health %" tile.
- **Pivots:** count of flagged rows by issue type.
- **Filters:** Issue type.
- **Leadership use case:** "Can I trust this week's numbers? Data health is 97% — yes, with 3 flagged rows under review."

---

## 6. KPI Definitions

| KPI | Definition / formula | Notes |
|---|---|---|
| **Headcount** | Count of reqs with `Headcount_Status = Filled` (filled seats) | Distinguish *filled headcount* from *planned headcount*. |
| **Open Requisitions** | Count of reqs with `Headcount_Status = Open` | Aging measured as `TODAY() − Req_Open_Date`. |
| **Time-to-Fill** | `AVG(Hire_Date − Req_Open_Date)` for filled reqs | Business clock; report median alongside mean. |
| **Time-to-Hire** | `AVG(Hire_Date − Application_Date)` for hired candidates | Candidate-experience clock. |
| **Offer Acceptance Rate** | `Offers Accepted ÷ Offers Extended` | Accepted = candidate reached `Hired` after `Offer_Date`. |
| **Funnel Conversion Rate** | stage-to-stage: `Count(stage N+1) ÷ Count(stage N)` | Report each step (App→Screen, Screen→Onsite, …). |
| **Source Effectiveness** | `Hires from source ÷ Applicants from source` | Pair with volume so a 1-of-1 source doesn't look "100%." |
| **Recruiter Productivity** | Hires per recruiter per period; secondary: avg TTF, active pipeline | Context matters — req difficulty varies. |
| **Regional Hiring Velocity** | Avg TTF by region + hires-per-week by region | Combines speed and volume. |

---

## 7. Google Sheets Implementation

### Workbook structure
```
[Recruiting_Data]   ← raw event log (the only sheet you type/import into)
[Helper_Calcs]      ← derived columns (TTF, furthest stage, age buckets, dup flags)
[Pivots]            ← all pivot tables live here, off-screen from dashboards
[Exec_Overview]     [Funnel]  [Headcount]  [Regional]
[Source]            [Recruiter]  [Time_to_Fill]  [Data_Quality]
[Weekly_Snapshots]  ← append-only KPI history (Apps Script writes here)
[Config]            ← named ranges, plan/target values, slicer settings
```

### Formula examples
```excel
# Time-to-Fill on filled reqs (Helper_Calcs)
=IF(AND($O2="Filled", $K2<>"", $N2<>""), $K2-$N2, "")
   # O = Headcount_Status, K = Hire_Date, N = Req_Open_Date

# Furthest stage reached (for funnel that counts people who advanced past a stage)
=IFS($L2="Hired",5, $L2="Offer",4, $L2="Onsite",3, $L2="Screen",2, TRUE,1)

# Open-req age bucket
=IFS(P2="", "n/a", P2<=30,"0-30", P2<=60,"31-60", TRUE,"60+")
   # where P2 = TODAY()-Req_Open_Date for open reqs

# Offer Acceptance Rate (Config / Exec tile)
=COUNTIFS(Recruiting_Data!L:L,"Hired") /
 COUNTIFS(Recruiting_Data!I:I,"<>")     # I = Offer_Date not blank

# Week-over-week delta on a KPI (Exec_Overview), pulling from Weekly_Snapshots
=LET(cur, INDEX(Weekly_Snapshots!B:B, MATCH(MAX(Weekly_Snapshots!A:A),Weekly_Snapshots!A:A,0)),
     prev, INDEX(Weekly_Snapshots!B:B, MATCH(MAX(Weekly_Snapshots!A:A),Weekly_Snapshots!A:A,0)-1),
     cur-prev)
```

### Pivot table designs
| Pivot | Rows | Columns | Values | Feeds |
|---|---|---|---|---|
| Funnel counts | Furthest stage | — | COUNT distinct Candidate_ID | Funnel tab |
| Headcount status | Department | Headcount_Status | COUNT reqs | Headcount / Exec |
| TTF by region | Region | — | AVG & MEDIAN of TTF | Regional / TTF |
| Source mix | Source_of_Hire | Stage=Hired? | COUNT hires, COUNT applicants | Source tab |
| Recruiter load | Recruiter | Status | COUNT reqs, COUNT hires | Recruiter tab |

### Data validation rules
- `Current_Stage`, `Headcount_Status`, `Region`, `Source_of_Hire`, `Candidate_Type` → **dropdown from a list in Config** (prevents free-text typos that break pivots).
- Date fields → **must be a valid date** (reject text).
- `Requisition_ID` → custom formula validation matching `REQ-\d{4}-\d{4}` pattern.

### Conditional formatting rules
- TTF cell: green ≤ 45 days, amber 46–70, red > 70.
- Open-req age: red if > 60 days.
- Offer Acceptance tile: red if < 80%.
- Data Quality issue rows: highlight the offending cell (e.g., red if `Hire_Date < Application_Date`).

---

## 8. Google Apps Script Automation

### Architecture

A single Apps Script project **bound to the workbook**. One time-driven trigger
fires `runWeeklyReport()` every Monday at 7am, and it calls the steps in order.
Each step is a small named function so it can be run on its own from the editor
when one part misbehaves, and the whole thing is re-runnable —
`refreshSnapshot()` will not append a second row for a day it has already
written.

```
runWeeklyReport()
  ├─ refreshSnapshot()          append this week's KPIs to Weekly_Snapshots
  ├─ getMetrics()               read the six KPI tiles by named range
  ├─ generateNarrative()        ask the model for the executive summary
  ├─ buildSlides()              copy the template deck and fill it in
  │    ├─ insertSheetChart_()   pull live charts from the workbook
  │    └─ buildAtRiskTable_()   requisitions open past the threshold
  └─ log_()                     write the outcome to the Logs tab
```

### The code

The full script is [`apps_script/Code.gs`](../apps_script/Code.gs); setup,
required Script Properties and how to swap the narrative provider are in
[`apps_script/README.md`](../apps_script/README.md). A real run's output, and
an account of the two figures it got wrong, is in
[`apps_script/example-output.md`](../apps_script/example-output.md).

Three decisions in it worth naming:

**The API key lives in Script Properties, never in the file.** It is read once
at the top and the run fails immediately if it is missing, rather than
part-building a deck and then erroring. The Logs tab in the shipped workbook
shows exactly that happening four times before the key was set.

**The model is given the numbers, not the data.** The prompt receives the six
current KPIs and the six deltas as text, with an instruction to use only those
and invent nothing. It cannot reach the dataset, so it cannot derive a figure
that is not already on the dashboard — which also means it inherits any error
in those figures, as the example output shows.

**Column positions are named, not inlined.** `getAtRiskReqs()` reads the raw
sheet by index, so the indexes live in one `COL` map at the top. Inserting a
column upstream then breaks in one obvious place rather than silently changing
which field the at-risk table reports.

## 9. AI Weekly Summary System

### Workflow
1. Apps Script computes `current`, `previous` and `delta` for each KPI.
2. It formats them into a tightly scoped prompt.
3. It sends that to the narrative model.
4. The model returns a short executive summary, which is written into the deck
   and kept on the `AI_Output` tab.

> **Anomaly flagging is not implemented.** The design below included it, and
> earlier versions of this document described it as though it shipped. It does
> not. With sixteen weeks of history and hire counts in the low single digits
> per week, a standard-deviation rule would flag noise most weeks; doing it
> properly needs either more history or a model of the count distribution.
> Listed in §14 as future work.

### Prompt engineering strategy
- **Ground the model in data, forbid invention.** The prompt says: use only the numbers provided; if a figure isn't given, don't state it.
- **Constrain the output shape.** Ask for a fixed structure (headline → what changed → risks → opportunities) so the slide template always fits.
- **Set the voice.** "Write for a VP of Talent: plain English, no jargon, lead with the takeaway."
- **Keep detection out of the model.** Anything the model is asked to *notice*
  rather than *phrase* is a thing it can get wrong silently. The division
  intended here is that arithmetic stays in code and only framing is the
  model's job — see the caveat above about how far that is actually built.
- **Cap length** so it fits one slide.

### Prompt template
```
You are a recruiting operations analyst writing the weekly talent review
for a VP of Talent. Use ONLY the numbers in the DATA block. Never invent
figures. If something isn't provided, don't mention it.

Write 4 short sections, plain English, ~150 words total:
1. HEADLINE — the single most important takeaway this week.
2. WHAT CHANGED — 2–3 bullets on the biggest week-over-week moves, with direction.
3. RISKS — anything flagged as an anomaly or trending the wrong way.
4. OPPORTUNITIES — one constructive, data-supported suggestion.

Lead with the takeaway. No preamble. No em-dashes.

DATA:
{current_week_figures}
{change_from_last_week}
```

The prompt as shipped is in
[`generateNarrative()`](../apps_script/Code.gs); it passes the six current
figures and the six deltas as formatted text rather than JSON, with explicit
rounding instructions so the model does not restate a percentage to nine
decimal places.

### Example input
```json
{
  "week_of": "2026-03-30",
  "current":  {"openReqs": 41, "hires": 7,  "ttf": 58, "offerAccept": 0.82, "funnelConv": 0.18},
  "previous": {"openReqs": 38, "hires": 9,  "ttf": 49, "offerAccept": 0.88, "funnelConv": 0.21},
  "delta":    {"openReqs": 3,  "hires": -2, "ttf": 9,  "offerAccept": -0.06, "funnelConv": -0.03}
}
```
```
ANOMALY FLAGS: ["avgTimeToFill +9 days WoW (largest jump in 6 weeks)",
                "offerAcceptRate dropped below 85% threshold"]
```

### Example output (what the model returns)
```
HEADLINE: Hiring slowed this week — time-to-fill jumped 9 days and offer
acceptance slipped below our 85% line.

WHAT CHANGED:
- Average time-to-fill rose from 49 to 58 days, the biggest weekly jump in six weeks.
- We made 7 hires versus 9 last week, while open reqs grew from 38 to 41.
- Offer acceptance fell from 88% to 82%.

RISKS: The acceptance dip plus the time-to-fill jump suggests offers are
landing slower and converting worse — possibly a comp or competing-offer issue
worth checking on the reqs that stalled at offer stage.

OPPORTUNITIES: Open reqs are outpacing hires three to one this week. Rebalancing
load on the most-loaded recruiters could keep the backlog from compounding.
```

---

## 10. Python Analytics Layer

Python does the work that is clumsy in formulas and impossible to unit-test in
a spreadsheet. The shipped implementation is in
[`src/recruiting_funnel/`](../src/recruiting_funnel/):

| Module | Responsibility |
|---|---|
| [`schema.py`](../src/recruiting_funnel/schema.py) | Field dictionary, controlled vocabularies, what "reaching a stage" means |
| [`generate.py`](../src/recruiting_funnel/generate.py) | Seeded synthetic generator; requisitions are built first, candidates attached to them |
| [`dataset.py`](../src/recruiting_funnel/dataset.py) | CSV to typed rows, rejecting header drift |
| [`validate.py`](../src/recruiting_funnel/validate.py) | 13 data-quality rules, run over the raw CSV before typing |
| [`metrics.py`](../src/recruiting_funnel/metrics.py) | Every KPI, defined exactly once |
| [`export.py`](../src/recruiting_funnel/export.py) | Metrics to the JSON the web dashboard reads |

### Three things changed from the original design

**No pandas.** The first sketch of this layer was built on pandas. For 750
rows and a fixed set of aggregations it was buying a dependency and no
capability, so the shipped code is standard library only. The practical payoff
is that `make test` works on a fresh clone with no install step and CI needs no
resolver. The boundary to revisit is `dataset.load()` — at warehouse scale,
that is the one function that changes.

**No `.str.title()` normalisation.** The original plan normalised the enum
columns by trimming and title-casing them, to stop `"Linkedin"` and
`"LinkedIn"` splitting a pivot. That fix is worse than the problem: `.title()`
turns `"LinkedIn"` into `"Linkedin"`, corrupting the correctly-spelled value in
order to match the typo. Silently rewriting data to make a report tidy is how
you lose the ability to reconcile it against the source. The shipped code
validates against a controlled vocabulary and *reports* anything outside it
instead — see `UNKNOWN_ENUM`.

**No anomaly detection.** The design included z-score flagging on the weekly
KPIs. It is not implemented, and the write-up previously implied it was. With
16 weeks of history and hire counts in the low single digits per week, a
z-score would flag noise constantly; it needs either more history or a model
of the count distribution, and neither was worth building on synthetic data.
It is honest future work rather than a shipped feature.

### On testing

The metric definitions carry 51 tests, which is the part of this layer that
most needed them: a KPI is a definition as much as a calculation, and a test is
the only place a definition can be pinned so that changing it has to be
deliberate. See [`tests/`](../tests/).

## 11. Automated Google Slides Reporting

### Slide structure (template deck)
1. **Title** — "Weekly Talent Review — {{WEEK_OF}}" + the five headline KPI tiles.
2. **AI Narrative** — the `{{NARRATIVE}}` text box populated by the model.
3. **Time-to-Fill trend** — embedded live Sheets chart.
4. **Funnel** — conversion chart.
5. **At-risk reqs** — auto-filled table of reqs open > 60 days.
6. **Appendix** — definitions + synthetic-data disclaimer.

### Data population logic
- `replaceAllText('{{TOKEN}}', value)` swaps placeholders for current values — the template stays human-editable and the script just fills blanks.
- Charts are **inserted as linked Sheets charts** so opening the deck pulls the latest render.
- The at-risk table is built by querying open reqs aged > 60 and writing rows into a template table shape.

### Weekly leadership review workflow
Monday 7am trigger → pipeline runs → deck + email land before the team's Monday standup → analyst spends 5 minutes sanity-checking → leadership reviews in the talent sync. The analyst's job shifts from *building* to *verifying and interpreting*.

---

## 12. Weekly Report Template

> **Illustrative layout.** Every figure below is invented to show the shape of
> the report — they come from neither dataset in this repository. For a real
> run, see [`apps_script/example-output.md`](../apps_script/example-output.md),
> which includes what the model got wrong.

**Key metrics**
| KPI | This week | Last week | Δ |
|---|---|---|---|
| Open requisitions | 41 | 38 | +3 |
| Hires | 7 | 9 | −2 |
| Avg time-to-fill | 58 d | 49 d | +9 d |
| Offer acceptance | 82% | 88% | −6 pts |
| Funnel conversion (app→hire) | 18% | 21% | −3 pts |
| Headcount vs. plan | −12 | −10 | −2 |

**Changes from prior week** — Hiring pace slowed: fewer hires, more open reqs, and a notable jump in time-to-fill. Offer acceptance dropped below the 85% threshold.

**Risks**
- Time-to-fill +9 days is the largest weekly jump in six weeks (flagged anomaly).
- Offer acceptance below 85% — possible comp / competing-offer pressure.
- Open reqs growing faster than hires; backlog risk.

**Opportunities**
- Three of the five at-risk reqs are in EMEA — a targeted sourcing push or load rebalance there would move the average most.
- Referrals are still converting ~3× job boards; a short referral campaign could lift volume cheaply.

**Executive summary**

This section is written at run time by the model, from the figures above and
the prior week's. It is the only part of the report that is not deterministic,
and the prompt is given the exact numbers with an instruction to invent none.

The narrative is deliberately *not* mocked up here. A hand-written sample would
read better than the real thing, which would misrepresent what the step
actually produces. The genuine output — and an account of the two figures it
cited that were wrong — is in
[`apps_script/example-output.md`](../apps_script/example-output.md).

---

## 13. Data Quality

The rules that ship, what each one catches, and the full audit of this
workbook are in [`docs/data-quality.md`](./data-quality.md). That file is
authoritative; this section is about what I got wrong before writing it.

### What I planned for, and what actually happened

At design time I listed the failure modes I could imagine: candidates pointing
at requisitions that don't exist, hires credited to the wrong recruiter,
"Linkedin" and "LinkedIn" splitting a pivot, missing dates on a stage a
candidate had clearly reached.

**None of those occurred.** Two of them could not have — a requisition in this
model is derived from the candidate rows themselves rather than held in a
separate list, so there is no list for a candidate to be orphaned from.

What actually broke every requisition-level metric was something I had not
thought to check at all: whether a requisition was *internally consistent*.
49 of 50 had rows disagreeing about which team and region they belonged to and
when they opened. Time-to-fill, requisition ageing, at-risk reporting — all of
them join on that key, and all of them were measuring noise.

### The lesson

I had written a data-quality tab. It reported 99.75% health. It was checking
for blanks and duplicate names — the errors that are easy to imagine and easy
to count — and it was silent about the one that mattered, because I had only
thought to verify the *contents* of rows and never the *relationships between
them*.

The checks that now run are the ones that would have caught it: every field
that should be constant across a requisition is asserted to be constant, and
the assertion runs before any metric is computed rather than on a tab beside
the results.

## 14. Capstone Expansion

How this prototype could grow into a Talent Strategy internship capstone.

**Automated recruiting operations workflow**
End-to-end, hands-off: nightly ingest from the ATS → automated cleaning/validation → KPI recompute → anomaly detection → weekly AI report → distribution. The human role becomes exception-handling and strategy, not assembly.

**Ashby integration concept**
Replace the synthetic source with Ashby's API. Pull requisitions, candidates, stage history, and offers on a schedule into a warehouse table that mirrors my `Recruiting_Data` schema. Because I designed the schema around standard ATS concepts, the downstream logic ports with minimal change. (Prototype stays synthetic; this is the production path.)

**Visier dashboard integration concept**
For organizations on Visier, push the computed KPIs as a feed so recruiting velocity sits alongside broader people-analytics (attrition, comp, DEI). My layer becomes the recruiting-specific feeder into an enterprise analytics platform rather than a standalone dashboard.

**Executive reporting automation roadmap**
1. *Now (prototype):* synthetic data, manual run, AI weekly report. ✅
2. *Phase 1:* live ATS ingestion + scheduled runs.
3. *Phase 2:* warehouse-backed metrics, significance-tested anomalies.
4. *Phase 3:* conversational analytics ("why did EMEA slow down?") answered from the dataset.
5. *Phase 4:* predictive — forecast time-to-fill and flag reqs likely to age out before they do.

---

*Built as a learning prototype on synthetic data. No production deployment, no real candidate or company data.*
