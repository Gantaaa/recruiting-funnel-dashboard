# KPI definitions

Every metric below is implemented once, in
[`src/recruiting_funnel/metrics.py`](../src/recruiting_funnel/metrics.py), and
pinned by [`tests/test_metrics.py`](../tests/test_metrics.py). The dashboard,
the exported JSON and the weekly deck all read from that one implementation, so
a number cannot mean one thing on a tile and something else in a slide.

A note on grain: the dataset has **one row per candidate per requisition**. A
requisition with nine applicants occupies nine rows. Anything counted at the
requisition level therefore deduplicates on `Requisition_ID` first — counting
rows would count that requisition nine times.

## Velocity

| Metric | Definition | Notes |
|---|---|---|
| **Time to fill** | `Hire_Date − Req_Open_Date`, averaged over hires | The *business* clock: how long the seat sat empty. Reported as mean and median. |
| **Time to hire** | `Hire_Date − Application_Date`, averaged over hires | The *candidate* clock: how long the process took the person who got the job. |

These two get confused constantly, which is why both are reported. A team can
improve time-to-hire (a slicker process) while time-to-fill gets worse (reqs
sitting unstaffed before sourcing starts). Only one of them is a candidate
experience metric.

## Funnel

| Metric | Definition |
|---|---|
| **Stage count** | Candidates whose record shows they reached that stage |
| **Stage conversion** | `count(stage N) ÷ count(stage N−1)` |
| **Applied → hired** | `count(Hired) ÷ count(Applied)` |
| **Offer acceptance** | `count(Hired) ÷ count(Offer)` |

**Reaching a stage is evidenced by that stage's date being populated, not by
`Current_Stage`.** This is the one definition that differs from the original
spreadsheet, and it matters: `Current_Stage` records where a candidate *ended
up*, so a candidate who interviewed onsite and was then rejected shows as
`Rejected`. The spreadsheet mapped both `Rejected` and `Withdrawn` back to stage
1, which erased every stage those candidates actually reached.

On the shipped dataset that understates applied→screen conversion as 13.9% when
the true figure is 59.2%. The dashboard's funnel panel has a toggle that shows
both, because the difference is the clearest illustration of why the definition
matters.

The uncorrected calculation is kept in `metrics.funnel(rows, legacy=True)` so
the comparison stays runnable rather than being a claim in a README.

## Requisitions

| Metric | Definition |
|---|---|
| **Open / Filled / On Hold / Cancelled** | Distinct requisitions in each status |
| **Requisition fill rate** | `Filled ÷ (Open + Filled)` |
| **Ageing buckets** | Open requisitions grouped 0–30 / 31–60 / 60+ days since opening |
| **At risk** | Open requisitions past 60 days, oldest first |

Where a requisition's rows disagree about its status — which happens in the
original export — the status resolves by precedence: **Filled > Cancelled > On
Hold > Open**. A seat somebody was hired into is filled. Without this rule the
original workbook counted one requisition in both the open and filled buckets,
so its requisition totals came to 51 for a dataset containing 50.

The spreadsheet labelled the fill rate **"Headcount vs Plan"**, which it is not.
Headcount versus plan requires a hiring plan to compare against, and no such
target exists anywhere in the dataset. It has been renamed to what it actually
measures.

## Source effectiveness

| Metric | Definition |
|---|---|
| **Applicants** | Candidates attributed to that source |
| **Hires** | Of those, the ones hired |
| **Conversion** | `hires ÷ applicants` |

Conversion is always shown next to volume. A source with one applicant and one
hire converts at 100% and means nothing; the volume column is what stops that
from reading as the best channel on the page.

## Weekly trend

The 16-week history is **recomputed from the event dates on every build** rather
than accumulated into a snapshot table.

The original workbook appended one row per run to a `Weekly_Snapshots` tab, and
its first eight rows had been typed in by hand — they asserted roughly 300 open
requisitions for a dataset that had 14. Every week-over-week figure on that
dashboard was comparing this week against a number nobody had computed. Deriving
the history means it backfills correctly, cannot drift from the data, and
survives a re-run.

Weekly series distinguish two kinds of measure:

- **Flows** — applications, offers, hires. Events counted within a week. They
  sum, and they belong on a zero baseline.
- **Stocks** — open requisitions. A level measured at each week's end. Summing
  one is meaningless, which is how a dashboard ends up reporting "300 open
  requisitions" for a team that has nineteen.

## Data quality

`health` is the share of rows carrying **no error-level issue**. It counts rows,
not issues — one row with three problems is one unhealthy row. Warnings never
reduce health; they flag things worth a look that do not invalidate a metric.

The rules themselves are in [data-quality.md](./data-quality.md).
