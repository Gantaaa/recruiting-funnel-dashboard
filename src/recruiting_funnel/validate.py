"""Data-quality rules for the recruiting dataset.

This runs against the *raw* CSV rather than the typed rows, because several
real defects in the source workbook are invisible after typing: an impossible
date such as ``2026-02-29`` is a text cell, and a spreadsheet comparing text to
a date silently returns a result instead of an error. The original workbook's
Data Quality tab reported 99.75% health while missing half of them.

Severities
----------
``error``    the number it feeds is wrong or a row cannot be interpreted
``warning``  suspicious, worth a human look, does not invalidate a metric
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from .schema import (
    CANDIDATE_TYPES,
    DATE_COLUMNS,
    FUNNEL_STAGES,
    HEADCOUNT_STATUSES,
    REGIONS,
    SOURCES,
    STAGES,
    STAGE_DATE_COLUMN,
)

# Columns whose value must be identical on every row of a given requisition.
REQUISITION_INVARIANTS = ("Department", "Region", "Req_Open_Date")

ENUM_COLUMNS = {
    "Region": REGIONS,
    "Source_of_Hire": SOURCES,
    "Candidate_Type": CANDIDATE_TYPES,
    "Current_Stage": STAGES,
    "Headcount_Status": HEADCOUNT_STATUSES,
}


@dataclass(frozen=True, slots=True)
class Issue:
    rule: str
    severity: str
    row: int  # 1-based line number in the CSV, header included
    candidate_id: str
    column: str
    detail: str

    def as_dict(self) -> dict:
        return asdict(self)


def _is_date(value: str) -> bool:
    try:
        datetime.strptime(value.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def validate_file(path: str | Path) -> list[Issue]:
    """Run every rule over the CSV at ``path`` and return the issues found."""
    with open(path, newline="", encoding="utf-8") as fh:
        records = [r for r in csv.DictReader(fh) if (r.get("Candidate_ID") or "").strip()]
    return validate_records(records)


def validate_records(records: list[dict]) -> list[Issue]:
    issues: list[Issue] = []

    def add(rule, severity, index, record, column, detail):
        issues.append(
            Issue(rule, severity, index + 2, record.get("Candidate_ID", ""), column, detail)
        )

    seen_candidates: Counter[str] = Counter()
    by_requisition: dict[str, list[tuple[int, dict]]] = defaultdict(list)

    for index, record in enumerate(records):
        seen_candidates[record["Candidate_ID"]] += 1
        by_requisition[record["Requisition_ID"]].append((index, record))

        # --- impossible or malformed dates -------------------------------
        parsed: dict[str, datetime | None] = {}
        for column in DATE_COLUMNS:
            raw = (record.get(column) or "").strip()
            if not raw:
                parsed[column] = None
                continue
            if not _is_date(raw):
                parsed[column] = None
                add(
                    "INVALID_DATE", "error", index, record, column,
                    f"{raw!r} is not a real calendar date",
                )
            else:
                parsed[column] = datetime.strptime(raw, "%Y-%m-%d")

        # --- controlled vocabularies -------------------------------------
        for column, allowed in ENUM_COLUMNS.items():
            value = (record.get(column) or "").strip()
            if value and value not in allowed:
                add(
                    "UNKNOWN_ENUM", "error", index, record, column,
                    f"{value!r} is not one of {', '.join(allowed)}",
                )

        # --- required anchors --------------------------------------------
        for column in ("Application_Date", "Req_Open_Date"):
            if parsed[column] is None and not (record.get(column) or "").strip():
                add(
                    "MISSING_REQUIRED", "error", index, record, column,
                    "required date is blank",
                )

        # --- funnel dates must run forward -------------------------------
        ordered = [
            (stage, parsed[STAGE_DATE_COLUMN[stage]])
            for stage in FUNNEL_STAGES
        ]
        present = [(stage, value) for stage, value in ordered if value is not None]
        for (prev_stage, prev_value), (stage, value) in zip(present, present[1:]):
            if value < prev_value:
                add(
                    "DATE_OUT_OF_ORDER", "error", index, record,
                    STAGE_DATE_COLUMN[stage],
                    f"{stage} ({value:%Y-%m-%d}) precedes "
                    f"{prev_stage} ({prev_value:%Y-%m-%d})",
                )

        if parsed["Application_Date"] and parsed["Req_Open_Date"]:
            if parsed["Application_Date"] < parsed["Req_Open_Date"]:
                add(
                    "APPLIED_BEFORE_REQ_OPEN", "warning", index, record,
                    "Application_Date",
                    "candidate applied before the requisition opened",
                )

        # --- stage vs. evidence ------------------------------------------
        stage = (record.get("Current_Stage") or "").strip()
        if stage == "Hired" and parsed["Hire_Date"] is None:
            add(
                "MISSING_STAGE_DATE", "error", index, record, "Hire_Date",
                "Current_Stage is Hired but Hire_Date is missing",
            )
        if stage == "Offer" and parsed["Offer_Date"] is None:
            add(
                "MISSING_STAGE_DATE", "error", index, record, "Offer_Date",
                "Current_Stage is Offer but Offer_Date is missing",
            )
        if parsed["Hire_Date"] and parsed["Offer_Date"] is None:
            add(
                "HIRED_WITHOUT_OFFER", "warning", index, record, "Offer_Date",
                "candidate was hired with no recorded offer date",
            )

        # A populated later stage with an empty earlier one means the funnel
        # count for the skipped stage understates reality.
        for earlier, later in zip(FUNNEL_STAGES, FUNNEL_STAGES[1:]):
            if parsed[STAGE_DATE_COLUMN[later]] and not parsed[STAGE_DATE_COLUMN[earlier]]:
                add(
                    "SKIPPED_STAGE_DATE", "warning", index, record,
                    STAGE_DATE_COLUMN[earlier],
                    f"reached {later} with no {earlier} date recorded",
                )

    # --- cross-row rules --------------------------------------------------
    for candidate_id, count in seen_candidates.items():
        if count > 1:
            index = next(i for i, r in enumerate(records) if r["Candidate_ID"] == candidate_id)
            add(
                "DUPLICATE_CANDIDATE_ID", "error", index, records[index],
                "Candidate_ID", f"appears on {count} rows",
            )

    for requisition_id, entries in by_requisition.items():
        index, record = entries[0]
        statuses = {(r.get("Headcount_Status") or "").strip() for _, r in entries}
        if len(statuses) > 1:
            add(
                "INCONSISTENT_REQ_STATUS", "error", index, record, "Headcount_Status",
                f"{requisition_id} carries conflicting statuses: "
                f"{', '.join(sorted(statuses))}",
            )
        for column in REQUISITION_INVARIANTS:
            values = {(r.get(column) or "").strip() for _, r in entries}
            if len(values) > 1:
                add(
                    "INCONSISTENT_REQ_ATTRIBUTE", "error", index, record, column,
                    f"{requisition_id} has conflicting {column}: "
                    f"{', '.join(sorted(values))}",
                )

    issues.sort(key=lambda issue: (issue.row, issue.rule))
    return issues


def summarise(records_count: int, issues: list[Issue]) -> dict:
    """Aggregate issues into the shape the dashboard's data-quality tile wants."""
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    affected = {i.row for i in errors}
    return {
        "rows": records_count,
        "errors": len(errors),
        "warnings": len(warnings),
        "rows_with_errors": len(affected),
        # Share of rows that carry no error-level issue.
        "health": round(1 - len(affected) / records_count, 4) if records_count else 1.0,
        "by_rule": dict(Counter(i.rule for i in issues).most_common()),
        "issues": [i.as_dict() for i in issues],
    }
