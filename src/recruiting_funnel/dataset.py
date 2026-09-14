"""Read ``recruiting_data.csv`` into typed :class:`~.schema.Row` records."""

from __future__ import annotations

import csv
from datetime import date, datetime
from pathlib import Path

from .schema import COLUMNS, DATE_COLUMNS, Row

DEFAULT_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "recruiting_data.csv"


class SchemaError(ValueError):
    """Raised when the CSV header does not match the expected field dictionary."""


def _parse_date(value: str) -> date | None:
    """Parse an ISO date, coercing anything unparseable to ``None``.

    The source workbook contains a handful of impossible dates typed as text
    (``2026-02-29`` in a non-leap year, ``2026-01-33``). One bad cell should not
    abort a pipeline run, so they are coerced here and reported as issues by
    :mod:`recruiting_funnel.validate`, which reads the raw CSV before typing.
    """
    value = value.strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _parse_int(value: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def load(path: str | Path) -> list[Row]:
    """Load and type the dataset, rejecting any header drift up front."""
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = tuple(reader.fieldnames or ())
        if header != COLUMNS:
            missing = [c for c in COLUMNS if c not in header]
            extra = [c for c in header if c not in COLUMNS]
            raise SchemaError(
                f"unexpected columns in {path}: missing={missing} extra={extra}"
            )

        rows: list[Row] = []
        for record in reader:
            if not (record["Candidate_ID"] or "").strip():
                continue  # trailing blank rows from the spreadsheet export
            typed = {
                key: (
                    _parse_date(value)
                    if key in DATE_COLUMNS
                    else _parse_int(value)
                    if key == "Time_to_Fill"
                    else (value or "").strip()
                )
                for key, value in record.items()
            }
            rows.append(Row(**typed))
    return rows


def load_default() -> list[Row]:
    """Load the dataset that ships with the repository."""
    return load(DEFAULT_DATA_PATH)
