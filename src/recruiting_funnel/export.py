"""Render the computed metrics to the JSON the web dashboard reads.

The dashboard holds no analytical logic of its own: it draws whatever this
file writes. That is the point -- a KPI is defined once, in
:mod:`recruiting_funnel.metrics`, and the spreadsheet, the deck and the web
dashboard are all downstream of it.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from . import __version__
from .dataset import DEFAULT_DATA_PATH, load
from .metrics import compute_all, weekly_trend
from .schema import AT_RISK_DAYS, TTF_AMBER_MAX, TTF_GREEN_MAX
from .validate import summarise, validate_file


def latest_event_date(rows) -> date:
    """The most recent date appearing anywhere in the dataset.

    This is the default reporting date, rather than ``date.today()``, so that a
    given dataset always exports byte-identical JSON. CI checks the committed
    ``dashboard.json`` against a fresh build; if the report date drifted with
    the wall clock, that check would fail every day after the commit for
    reasons that have nothing to do with the code.
    """
    dates = [
        value
        for row in rows
        for value in (
            row.Application_Date, row.Phone_Screen_Date, row.Onsite_Date,
            row.Offer_Date, row.Hire_Date, row.Req_Open_Date,
        )
        if value is not None
    ]
    return max(dates)


def _slice(rows, *, as_of: date) -> dict:
    metrics = compute_all(rows, as_of=as_of)
    metrics["weekly_trend"] = weekly_trend(rows, as_of=as_of)
    return metrics


def build_payload(data_path: str | Path, *, as_of: date | None = None) -> dict:
    """Build the whole dashboard payload, including one slice per filter value.

    The dashboard's department and region filters swap between pre-computed
    slices rather than recomputing anything in the browser. That keeps
    :mod:`recruiting_funnel.metrics` the only place a KPI is ever defined --
    the page draws numbers, it does not derive them.
    """
    data_path = Path(data_path)
    rows = load(data_path)
    as_of = as_of or latest_event_date(rows)

    metrics = _slice(rows, as_of=as_of)

    # A fresh copy, so the payload does not contain a reference to itself.
    slices: dict[str, dict] = {"all": _slice(rows, as_of=as_of)}
    for department in sorted({row.Department for row in rows}):
        subset = [row for row in rows if row.Department == department]
        slices[f"department:{department}"] = _slice(subset, as_of=as_of)
    for region in sorted({row.Region for row in rows}):
        subset = [row for row in rows if row.Region == region]
        slices[f"region:{region}"] = _slice(subset, as_of=as_of)

    metrics["slices"] = slices
    metrics["filters"] = {
        "department": sorted({row.Department for row in rows}),
        "region": sorted({row.Region for row in rows}),
    }
    metrics["data_quality"] = summarise(len(rows), validate_file(data_path))
    metrics["meta"] = {
        "generated_at": as_of.isoformat(),
        "source": data_path.name,
        "version": __version__,
        "synthetic": True,
        "thresholds": {
            "time_to_fill_green_max": TTF_GREEN_MAX,
            "time_to_fill_amber_max": TTF_AMBER_MAX,
            "at_risk_days": AT_RISK_DAYS,
        },
    }
    return metrics


def _default(value):
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(f"not JSON serialisable: {type(value).__name__}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(DEFAULT_DATA_PATH))
    parser.add_argument("--out", default="docs/data/dashboard.json")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="reporting date (default: the latest event date in the dataset)",
    )
    args = parser.parse_args(argv)

    payload = build_payload(args.data, as_of=args.as_of)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=_default), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
