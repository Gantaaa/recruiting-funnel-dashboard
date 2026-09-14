# The original workbook

`Recruiting_Funnel_Dashboard.xlsx` is the first version of this project, kept
**unchanged**. It is the "before" in the audit the
[README](../README.md#what-auditing-my-own-workbook-found) describes.

## Its numbers do not match the dashboard, and are not meant to

| | Workbook | Live dashboard |
|---|---|---|
| Candidate rows | 400 | 750 |
| Avg time to fill | 42.69 days | 61.22 days |
| Requisitions | 51 counted, **50 exist** | 70 |
| Funnel | 400 / 237 / 176 / 116 / 64 | 750 / 444 / 175 / 68 / 49 |

Two separate reasons they differ. The workbook runs on the original 400-row
export, which is retained at
[`data/recruiting_data_original.csv`](../data/recruiting_data_original.csv);
the dashboard runs on the regenerated dataset. And the workbook's formulas are
themselves wrong, in the ways catalogued in
[`docs/data-quality.md`](../docs/data-quality.md).

## What is still broken in here, deliberately

- **`Requisition_ID` is not a coherent key.** 49 of its 50 requisitions have
  rows disagreeing about their own department, region and open date, so every
  requisition-level figure — time-to-fill above all — is built on a bad join.
- **Open + Filled = 51** for a file containing 50 requisitions, because
  `COUNTUNIQUEIFS` counts a requisition carrying both statuses once in each.
- **The Recruiter tab lists four recruiters who appear nowhere in the data.**
  Every row reads zero. It looks completely normal.
- **The `Marketing` department** (50 rows) is missing from every breakdown,
  because the department lists on the dashboard tabs are hardcoded.
- **The funnel reads `Current_Stage`**, so everyone rejected or withdrawn
  collapses back to "Applied".
- **Four impossible dates** sit in the data as text, and the workbook's own
  date-logic check passes them.

Its Data Quality tab reports **99.75% health** throughout.

## Do not use this as a metric reference

The authoritative definitions are
[`src/recruiting_funnel/metrics.py`](../src/recruiting_funnel/metrics.py) and
[`docs/kpi-definitions.md`](../docs/kpi-definitions.md).

This file is here so the audit is something you can open and check, rather than
a claim you have to take on trust. Please do not "fix" it — the defects are the
point.

## Opening it

Built in Google Sheets. Several tabs use Sheets-only functions
(`COUNTUNIQUEIFS`, `MAP`, `LAMBDA`, `HSTACK`) that Excel cannot evaluate — it
shows `__xludf.DUMMYFUNCTION` with the last cached value beside it. To see it
work, import to Google Sheets rather than opening in Excel.

The bound Apps Script is in [`apps_script/`](../apps_script/).
