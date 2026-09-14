"""Every recruiting KPI, defined exactly once.

The spreadsheet, the web dashboard and the weekly deck all read their numbers
from :func:`compute_all`, so a metric cannot mean one thing on a dashboard tile
and something else in the leadership deck. Definitions are documented in
``docs/kpi-definitions.md``; ``tests/test_metrics.py`` pins them against the
values the original Google Sheet computed.

Requisition-level metrics deduplicate on ``Requisition_ID`` first: the dataset
has one row per *candidate*, so counting rows would count a req once per
applicant.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import date, timedelta
from typing import Iterable, Sequence

from .schema import (
    AT_RISK_DAYS,
    DEPARTMENTS,
    FUNNEL_STAGES,
    REGIONS,
    SOURCES,
    Row,
)

# Legacy mapping: what the original spreadsheet used to place a candidate in the
# funnel. It reads Current_Stage, which means a candidate who was rejected after
# an onsite is recorded as never having got past Applied. Kept so the dashboard
# can show the corrected and uncorrected funnel side by side.
_LEGACY_STAGE_RANK = {
    "Applied": 1,
    "Screen": 2,
    "Phone Screen": 2,
    "Onsite": 3,
    "Offer": 4,
    "Hired": 5,
    "Rejected": 1,
    "Withdrawn": 1,
}


def _round(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)


def _mean(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def _median(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


# Precedence used to resolve a requisition whose rows disagree about its status.
# The source data contains at least one requisition carrying both "Open" and
# "Filled" rows; the original spreadsheet counted it once in each bucket, so its
# requisition totals exceeded the number of requisitions that exist. A seat that
# somebody was hired into is filled, so Filled wins.
_STATUS_PRECEDENCE = ("Filled", "Cancelled", "On Hold", "Open")


def requisition_status(rows: Sequence[Row]) -> str:
    """Resolve one requisition's status from its (possibly conflicting) rows."""
    present = {row.Headcount_Status for row in rows}
    for status in _STATUS_PRECEDENCE:
        if status in present:
            return status
    return next(iter(present), "")


def _requisitions(rows: Iterable[Row]) -> dict[str, Row]:
    """One representative row per requisition (requisition fields are constant)."""
    reqs: dict[str, Row] = {}
    for row in rows:
        reqs.setdefault(row.Requisition_ID, row)
    return reqs


def _requisition_statuses(rows: Sequence[Row]) -> dict[str, str]:
    """Map every requisition id to its single resolved status."""
    grouped: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[row.Requisition_ID].append(row)
    return {req: requisition_status(bucket) for req, bucket in grouped.items()}


def time_to_fill_days(rows: Iterable[Row]) -> list[int]:
    """Days from requisition open to hire, for every hired candidate.

    Time-to-fill runs on the business clock (``Req_Open_Date`` -> ``Hire_Date``).
    Time-to-hire runs on the candidate clock (``Application_Date`` -> ``Hire_Date``).
    Both are reported; they answer different questions and are easy to confuse.
    """
    return [
        (row.Hire_Date - row.Req_Open_Date).days
        for row in rows
        if row.Hire_Date and row.Req_Open_Date
    ]


def time_to_hire_days(rows: Iterable[Row]) -> list[int]:
    return [
        (row.Hire_Date - row.Application_Date).days
        for row in rows
        if row.Hire_Date and row.Application_Date
    ]


def funnel(rows: Sequence[Row], *, legacy: bool = False) -> list[dict]:
    """Counts and step conversion for each funnel stage.

    ``legacy=True`` reproduces the original spreadsheet's Current_Stage logic.
    The default derives each candidate's furthest stage from which stage dates
    are populated, so candidates who dropped out still count toward every stage
    they actually reached.
    """
    if legacy:
        depths = [_LEGACY_STAGE_RANK.get(row.Current_Stage, 0) for row in rows]
    else:
        depths = [row.furthest_stage_index for row in rows]

    out: list[dict] = []
    previous: int | None = None
    for index, stage in enumerate(FUNNEL_STAGES, start=1):
        count = sum(1 for depth in depths if depth >= index)
        out.append(
            {
                "stage": stage,
                "count": count,
                # Conversion from the immediately preceding stage.
                "conversion_from_previous": (
                    None if previous is None else _round(count / previous if previous else 0.0)
                ),
            }
        )
        previous = count
    return out


def _breakdown(
    rows: Sequence[Row], attribute: str, categories: Sequence[str] | None = None
) -> list[dict]:
    """Volume, hires, open reqs and average TTF grouped by one dimension."""
    grouped: dict[str, list[Row]] = defaultdict(list)
    for row in rows:
        grouped[getattr(row, attribute)].append(row)

    # Use the declared vocabulary when there is one, so a category with zero
    # rows still shows up as an explicit zero rather than silently vanishing.
    keys = list(categories) if categories else sorted(grouped)

    out = []
    for key in keys:
        bucket = grouped.get(key, [])
        hires = [r for r in bucket if r.Current_Stage == "Hired"]
        ttf = time_to_fill_days(bucket)
        open_reqs = {
            req
            for req, status in _requisition_statuses(bucket).items()
            if status == "Open"
        }
        out.append(
            {
                "name": key,
                "candidates": len(bucket),
                "hires": len(hires),
                "open_reqs": len(open_reqs),
                "conversion": _round(len(hires) / len(bucket)) if bucket else None,
                "avg_time_to_fill": _round(_mean(ttf), 2),
                "median_time_to_fill": _round(_median(ttf), 2),
            }
        )
    return out


def at_risk_requisitions(
    rows: Sequence[Row], *, as_of: date, min_days: int = AT_RISK_DAYS, limit: int = 10
) -> list[dict]:
    """Open requisitions aged past ``min_days``, oldest first."""
    statuses = _requisition_statuses(rows)
    out = []
    for req_id, row in _requisitions(rows).items():
        if statuses[req_id] != "Open" or not row.Req_Open_Date:
            continue
        days_open = (as_of - row.Req_Open_Date).days
        if days_open >= min_days:
            out.append(
                {
                    "requisition_id": req_id,
                    "department": row.Department,
                    "region": row.Region,
                    "recruiter": row.Recruiter,
                    "days_open": days_open,
                }
            )
    out.sort(key=lambda item: item["days_open"], reverse=True)
    return out[:limit]


def aging_buckets(rows: Sequence[Row], *, as_of: date) -> dict[str, int]:
    """Open requisitions bucketed by how long they have been open."""
    buckets = {"0-30": 0, "31-60": 0, "60+": 0}
    statuses = _requisition_statuses(rows)
    for req_id, row in _requisitions(rows).items():
        if statuses[req_id] != "Open" or not row.Req_Open_Date:
            continue
        days = (as_of - row.Req_Open_Date).days
        key = "0-30" if days <= 30 else "31-60" if days <= 60 else "60+"
        buckets[key] += 1
    return buckets


def hires_in_window(rows: Sequence[Row], *, as_of: date, days: int = 7) -> int:
    """Hires whose ``Hire_Date`` falls in the trailing ``days`` window."""
    return sum(
        1
        for row in rows
        if row.Hire_Date and 0 <= (as_of - row.Hire_Date).days < days
    )


def compute_all(rows: Sequence[Row], *, as_of: date | None = None) -> dict:
    """Compute the full metric set. ``as_of`` defaults to today.

    Anything time-relative (open-req ageing, hires this week) is measured
    against ``as_of`` and is passed in explicitly so results are reproducible
    in tests instead of drifting with the wall clock.
    """
    as_of = as_of or date.today()

    reqs = _requisitions(rows)
    status_counts = Counter(_requisition_statuses(rows).values())
    hired = [row for row in rows if row.Current_Stage == "Hired"]

    ttf = time_to_fill_days(rows)
    tth = time_to_hire_days(rows)

    stages = funnel(rows)
    by_stage = {entry["stage"]: entry["count"] for entry in stages}

    open_reqs = status_counts.get("Open", 0)
    filled_reqs = status_counts.get("Filled", 0)

    return {
        "as_of": as_of.isoformat(),
        "dataset": {
            "candidates": len(rows),
            "requisitions": len(reqs),
            "date_range": {
                "earliest_application": min(
                    (r.Application_Date for r in rows if r.Application_Date),
                    default=None,
                ),
                "latest_hire": max(
                    (r.Hire_Date for r in rows if r.Hire_Date), default=None
                ),
            },
        },
        "kpis": {
            "open_requisitions": open_reqs,
            "filled_requisitions": filled_reqs,
            "on_hold_requisitions": status_counts.get("On Hold", 0),
            "cancelled_requisitions": status_counts.get("Cancelled", 0),
            "total_hires": len(hired),
            "hires_last_7_days": hires_in_window(rows, as_of=as_of, days=7),
            "hires_last_30_days": hires_in_window(rows, as_of=as_of, days=30),
            "avg_time_to_fill": _round(_mean(ttf), 2),
            "median_time_to_fill": _round(_median(ttf), 2),
            "avg_time_to_hire": _round(_mean(tth), 2),
            "median_time_to_hire": _round(_median(tth), 2),
            # Offers accepted / offers extended. Both measured from dates, so a
            # candidate still deciding counts in the denominator only.
            "offer_acceptance_rate": _round(
                by_stage["Hired"] / by_stage["Offer"] if by_stage["Offer"] else 0.0
            ),
            # End-to-end applied -> hired.
            "funnel_conversion_rate": _round(
                by_stage["Hired"] / by_stage["Applied"] if by_stage["Applied"] else 0.0
            ),
            # Share of requisitions that are filled rather than still open. The
            # original spreadsheet labelled this "Headcount vs Plan", which it
            # is not -- there is no hiring plan in the dataset to compare to.
            "requisition_fill_rate": _round(
                filled_reqs / (open_reqs + filled_reqs)
                if (open_reqs + filled_reqs)
                else 0.0
            ),
        },
        "funnel": stages,
        "funnel_legacy": funnel(rows, legacy=True),
        "by_department": _breakdown(rows, "Department", DEPARTMENTS),
        "by_region": _breakdown(rows, "Region", REGIONS),
        "by_source": _breakdown(rows, "Source_of_Hire", SOURCES),
        "by_recruiter": _breakdown(rows, "Recruiter"),
        "aging_buckets": aging_buckets(rows, as_of=as_of),
        "at_risk_requisitions": at_risk_requisitions(rows, as_of=as_of),
    }


def weekly_trend(rows: Sequence[Row], *, as_of: date, weeks: int = 16) -> list[dict]:
    """Reconstruct a week-by-week history directly from the event dates.

    The original workbook kept a ``Weekly_Snapshots`` tab that an Apps Script
    appended one row to per run, and its first eight rows were typed in by hand
    -- they claimed ~300 open requisitions against a dataset that had 14. Every
    week-over-week number on the dashboard was therefore comparing against
    fiction.

    Replaying the dates instead means the history is recomputed from the data
    every time, cannot drift from it, and backfills correctly.
    """
    # Week ending on the most recent Sunday, walking backwards from there.
    last_sunday = as_of - timedelta(days=(as_of.weekday() + 1) % 7)

    statuses = _requisition_statuses(rows)
    reqs = _requisitions(rows)
    hire_dates = {
        row.Requisition_ID: row.Hire_Date for row in rows if row.Hire_Date
    }

    out: list[dict] = []
    for index in range(weeks - 1, -1, -1):
        week_end = last_sunday - timedelta(weeks=index)
        week_start = week_end - timedelta(days=6)

        hires = [
            row for row in rows
            if row.Hire_Date and week_start <= row.Hire_Date <= week_end
        ]
        applications = sum(
            1 for row in rows
            if row.Application_Date and week_start <= row.Application_Date <= week_end
        )
        offers = sum(
            1 for row in rows
            if row.Offer_Date and week_start <= row.Offer_Date <= week_end
        )

        # A requisition was open at week_end if it had been opened by then and
        # had not yet been filled (or was filled later).
        open_at_week_end = 0
        for req_id, row in reqs.items():
            if not row.Req_Open_Date or row.Req_Open_Date > week_end:
                continue
            filled_on = hire_dates.get(req_id)
            if filled_on and filled_on <= week_end:
                continue
            if statuses[req_id] in ("Cancelled",):
                continue
            open_at_week_end += 1

        ttf = [
            (row.Hire_Date - row.Req_Open_Date).days
            for row in hires
            if row.Req_Open_Date
        ]
        out.append(
            {
                "week_ending": week_end.isoformat(),
                "applications": applications,
                "offers": offers,
                "hires": len(hires),
                "open_requisitions": open_at_week_end,
                "avg_time_to_fill": _round(_mean(ttf), 1),
            }
        )
    return out
