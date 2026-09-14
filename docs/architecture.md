# Architecture

```
  ┌────────────────────┐
  │  generate.py       │   seeded synthetic generator
  │  (or a real ATS    │   requisitions first, candidates attached to them
  │   export)          │
  └─────────┬──────────┘
            │  data/recruiting_data.csv
            ▼
  ┌────────────────────┐
  │  validate.py       │   11 rules over the RAW csv, before typing
  └─────────┬──────────┘
            │  issues + health score
            ▼
  ┌────────────────────┐
  │  metrics.py        │   ◄── the single source of truth for every KPI
  └─────────┬──────────┘
            │
      ┌─────┴───────────────────┬─────────────────────┐
      ▼                         ▼                     ▼
 ┌──────────┐          ┌─────────────────┐   ┌────────────────┐
 │ export.py│          │ Google Sheets   │   │ Apps Script    │
 │  ↓ JSON  │          │ workbook        │   │  ↓ narrative   │
 │ web      │          │ (the original   │   │  ↓ Slides deck │
 │ dashboard│          │  delivery)      │   │  ↓ email       │
 └──────────┘          └─────────────────┘   └────────────────┘
```

## The one rule

**A KPI is defined once.** `metrics.py` computes it; everything downstream
renders it. The web dashboard holds no analytical logic — it reads
`dashboard.json` and draws. Even its department and region filters swap between
slices that Python pre-computed, rather than recalculating in the browser.

This is not architectural decoration. The failure it prevents is the specific
one the original workbook had: the funnel tab and the executive tile disagreeing
about what "conversion" meant, with no single place to go and check.

## Why validation runs before typing

`validate.py` reads the CSV with `csv.DictReader` and does its own parsing,
rather than operating on the typed rows `dataset.py` produces. That is
deliberate. `dataset.py` coerces an unparseable date to `None` so that one bad
cell cannot abort a pipeline run — which means by the time rows are typed, the
evidence of `2026-02-29` is gone. Validation has to see the raw text.

## Why there are no dependencies

The Python layer is standard library only. `pip install` is not a prerequisite
for `make test` on a fresh clone, and CI needs no lockfile or resolver step. For
750 rows and a fixed set of aggregations, pandas would add a dependency without
adding capability. At a scale where it earns its place — or where the source is
a warehouse rather than a CSV — the boundary to change is `dataset.load()`,
which everything else is written against.

## Where each piece runs

**Apps Script** owns orchestration and delivery, because it is the only runtime
that can natively touch Sheets, Slides and Gmail and run on Google's triggers.
It reads the KPI tiles by named range and never recomputes them.

**Python** owns generation, validation and metric computation — the work that is
awkward to express in formulas and impossible to unit-test in a spreadsheet.

**The browser** owns rendering only.

The split is by responsibility, not by convenience: each layer does the thing
its runtime is actually good at, and the boundaries are narrow enough to
describe in a sentence.

## Extending it to a real ATS

`dataset.load()` is the seam. It returns `list[Row]`; everything downstream
depends on that shape and nothing else. Pointing this at Greenhouse, Lever or
Workday means writing one function that returns `list[Row]` from their API —
the metrics, validation, tests, export and dashboard are unchanged.

What would need real thought beyond that seam: incremental pulls and a lookback
window for late-arriving records, mapping each ATS's configurable stage names
onto the canonical funnel, and access control, since real candidate data carries
obligations that synthetic data does not.
