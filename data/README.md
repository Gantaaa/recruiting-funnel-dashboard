# Data

## `recruiting_data.csv`

The working dataset: 750 candidate rows across 70 requisitions, one row per
candidate per requisition. Produced by
[`generate.py`](../src/recruiting_funnel/generate.py) from a fixed seed, so it
is reproducible:

```bash
make data
```

It validates clean — no errors, no warnings — and a test enforces that.

Dates are anchored to the generation date rather than hardcoded, so the
dashboard always has recent activity to show instead of going stale.

## `recruiting_data_original.csv`

The original export from the Google Sheets workbook, kept unchanged.

It is here because the README makes specific claims about what was wrong with it
— 49 of 50 requisitions internally inconsistent, four impossible calendar dates,
one requisition counted as both open and filled. A test asserts those defects
are still reproducible from this file, so the before/after stays checkable
rather than becoming a story about a file nobody can inspect.

Do not "fix" it. Its defects are the point.

## Field dictionary

See [`schema.py`](../src/recruiting_funnel/schema.py) for the authoritative
column list and controlled vocabularies, and
[`docs/kpi-definitions.md`](../docs/kpi-definitions.md) for how each field feeds
the metrics.

| Field | Notes |
|---|---|
| `Candidate_ID` | Unique per row |
| `Requisition_ID` | The join key for requisition-level metrics. Constant attributes per requisition. |
| `Team` → `Department` | Team rolls up to exactly one department |
| `Region` | NA / EMEA / APAC / LATAM |
| `Recruiter`, `Hiring_Manager` | Owning recruiter and HM for the requisition |
| `Source_of_Hire` | Referral / LinkedIn / Job Board / Agency / Internal / University |
| `Candidate_Type` | External / Internal / Referral / New Grad |
| `Application_Date` … `Hire_Date` | Funnel stage dates, always monotonic |
| `Current_Stage` | Where the candidate ended up — **not** how far they got |
| `Req_Open_Date` | Anchors time-to-fill |
| `Time_to_Fill` | `Hire_Date − Req_Open_Date`, populated only for hires |
| `Headcount_Status` | Open / Filled / On Hold / Cancelled |
