# Data quality

Validation runs over the **raw CSV, before typing**. That ordering is the whole
point: several real defects in the source workbook are invisible once the data
has been parsed, because a spreadsheet stores an impossible date as *text*, and
comparing text to a date returns a result rather than an error.

The workbook's own Data Quality tab reported **99.75% health**. The audit below
is what was actually in the file.

## What the audit found in the original export

| Finding | Count | Why the spreadsheet missed it |
|---|---|---|
| Requisitions whose rows disagree about their own department, region or open date | 49 of 50 | Nothing checked that a requisition was internally consistent |
| Impossible calendar dates (`2026-01-32`, `2026-01-33`, `2026-02-29` ×2 in a non-leap year) | 4 | Stored as text; the date-logic formula compared text and passed |
| A requisition counted as both open and filled | 1 | `COUNTUNIQUEIFS` counted it once in each bucket, making 50 requisitions total 51 |
| A department (`Marketing`, 50 rows) absent from every dashboard breakdown | 50 rows | Department lists on the dashboard tabs were hardcoded |
| Recruiter tab listing four recruiters who appear nowhere in the data | 4 rows | Names hardcoded from an illustrative example, not read from the data |

The last one is the quietest and the worst: the Recruiter tab rendered a
complete, well-formatted table of four names, every row reading zero, because
the names came from a worked example rather than the dataset. Nothing errored.

The incoherent requisition key is the most serious, because it is not a
cosmetic problem — `Requisition_ID` is the join key for every requisition-level
metric. Time-to-fill was subtracting a randomly-assigned open date from a real
hire date.

That finding is why [`generate.py`](../src/recruiting_funnel/generate.py)
exists: a requisition is now generated first, as a real entity with one
department, team, region, recruiter and open date, and candidates are attached
to it afterwards. The invariant is enforced by
[`tests/test_generate.py`](../tests/test_generate.py).

The original export is kept at `data/recruiting_data_original.csv`, and a test
asserts it still reproduces its defects, so the before/after above stays honest
rather than becoming a story about a file nobody can check.

## The rules

Each rule is pinned by a test in
[`tests/test_validate.py`](../tests/test_validate.py).

### Errors — the number this feeds is wrong

| Rule | Catches |
|---|---|
| `INVALID_DATE` | A date cell that is not a real calendar date |
| `UNKNOWN_ENUM` | A value outside the controlled vocabulary for its column |
| `MISSING_REQUIRED` | A blank `Application_Date` or `Req_Open_Date` |
| `DATE_OUT_OF_ORDER` | A funnel stage dated before the stage preceding it |
| `MISSING_STAGE_DATE` | `Current_Stage` claims a stage whose date is blank |
| `DUPLICATE_CANDIDATE_ID` | The same candidate id on more than one row |
| `INCONSISTENT_REQ_STATUS` | One requisition carrying two headcount statuses |
| `INCONSISTENT_REQ_ATTRIBUTE` | One requisition whose rows disagree about department, region or open date |

### Warnings — worth a look, but no metric is wrong

| Rule | Catches |
|---|---|
| `APPLIED_BEFORE_REQ_OPEN` | A candidate who applied before the role opened |
| `HIRED_WITHOUT_OFFER` | A hire with no recorded offer date |
| `SKIPPED_STAGE_DATE` | A later stage reached with an earlier stage's date blank |

## Running it

```bash
make validate
```

or directly:

```python
from recruiting_funnel.validate import validate_file, summarise

issues = validate_file("data/recruiting_data.csv")
print(summarise(750, issues)["health"])
```

Each issue carries its rule, severity, CSV line number, candidate id, column and
a readable explanation — enough to go and fix the row, which is the only thing
a data-quality report is actually for.

The dataset shipped in `data/recruiting_data.csv` validates clean: 750 rows, no
errors, no warnings. A test enforces that, so a regression in the generator
fails the build rather than quietly degrading the dashboard.
