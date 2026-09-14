"""Metric definitions, pinned.

Two jobs here. The first is the ordinary one: check each KPI against a dataset
small enough to verify by hand. The second is a regression guard on the funnel
bug inherited from the spreadsheet, which derived a candidate's furthest stage
from Current_Stage and so recorded everyone who was rejected or withdrew as
never having got past Applied.
"""

import unittest
from datetime import date, timedelta

from recruiting_funnel import compute_all
from recruiting_funnel.dataset import load_default
from recruiting_funnel.export import latest_event_date
from recruiting_funnel.metrics import (
    funnel,
    requisition_status,
    time_to_fill_days,
    time_to_hire_days,
)
from recruiting_funnel.schema import Row

# Derived from the dataset rather than hardcoded, so regenerating the data with
# `make data` (which anchors it to the day it runs) does not break the suite.
REFERENCE = latest_event_date(load_default())


def make_row(**overrides) -> Row:
    """A minimal applied-only candidate, with fields overridden as needed."""
    base = dict(
        Candidate_ID="C-1", Requisition_ID="REQ-1", Team="Backend",
        Department="Engineering", Region="NA", Recruiter="Alice Smith",
        Hiring_Manager="Manager 01", Source_of_Hire="Referral",
        Candidate_Type="Referral", Application_Date=date(2026, 1, 1),
        Phone_Screen_Date=None, Onsite_Date=None, Offer_Date=None,
        Hire_Date=None, Current_Stage="Applied",
        Req_Open_Date=date(2026, 1, 1), Time_to_Fill=None,
        Headcount_Status="Open",
    )
    base.update(overrides)
    return Row(**base)


class FunnelDerivation(unittest.TestCase):
    def test_a_rejected_candidate_still_counts_at_every_stage_they_reached(self):
        # Interviewed onsite, then rejected. They reached Onsite.
        row = make_row(
            Phone_Screen_Date=date(2026, 1, 5),
            Onsite_Date=date(2026, 1, 12),
            Current_Stage="Rejected",
        )
        counts = {entry["stage"]: entry["count"] for entry in funnel([row])}
        self.assertEqual(counts["Applied"], 1)
        self.assertEqual(counts["Screen"], 1)
        self.assertEqual(counts["Onsite"], 1)
        self.assertEqual(counts["Offer"], 0)

    def test_the_legacy_spreadsheet_logic_loses_that_candidate(self):
        """The bug this replaces: Rejected collapses back to Applied."""
        row = make_row(
            Phone_Screen_Date=date(2026, 1, 5),
            Onsite_Date=date(2026, 1, 12),
            Current_Stage="Rejected",
        )
        counts = {e["stage"]: e["count"] for e in funnel([row], legacy=True)}
        self.assertEqual(counts["Applied"], 1)
        self.assertEqual(counts["Screen"], 0)  # wrong, and why the fix exists
        self.assertEqual(counts["Onsite"], 0)

    def test_legacy_understates_conversion_on_the_real_dataset(self):
        rows = load_default()
        corrected = funnel(rows)[1]["count"]
        legacy = funnel(rows, legacy=True)[1]["count"]
        self.assertGreater(corrected, legacy)

    def test_conversion_is_measured_against_the_previous_stage(self):
        rows = [
            make_row(Candidate_ID="C-1"),
            make_row(Candidate_ID="C-2", Phone_Screen_Date=date(2026, 1, 8)),
        ]
        stages = {e["stage"]: e for e in funnel(rows)}
        self.assertIsNone(stages["Applied"]["conversion_from_previous"])
        self.assertEqual(stages["Screen"]["conversion_from_previous"], 0.5)


class RequisitionStatus(unittest.TestCase):
    def test_a_filled_row_wins_over_an_open_one(self):
        """The source workbook counted such a req as both open and filled."""
        rows = [
            make_row(Headcount_Status="Open"),
            make_row(Headcount_Status="Filled"),
        ]
        self.assertEqual(requisition_status(rows), "Filled")

    def test_requisition_counts_sum_to_the_number_of_requisitions(self):
        metrics = compute_all(load_default(), as_of=REFERENCE)
        kpis = metrics["kpis"]
        total = (
            kpis["open_requisitions"]
            + kpis["filled_requisitions"]
            + kpis["on_hold_requisitions"]
            + kpis["cancelled_requisitions"]
        )
        self.assertEqual(total, metrics["dataset"]["requisitions"])


class Velocity(unittest.TestCase):
    def test_time_to_fill_runs_from_requisition_open(self):
        row = make_row(
            Req_Open_Date=date(2026, 1, 1),
            Application_Date=date(2026, 1, 11),
            Hire_Date=date(2026, 3, 2),
        )
        self.assertEqual(time_to_fill_days([row]), [60])

    def test_time_to_hire_runs_from_application(self):
        row = make_row(
            Req_Open_Date=date(2026, 1, 1),
            Application_Date=date(2026, 1, 11),
            Hire_Date=date(2026, 3, 2),
        )
        self.assertEqual(time_to_hire_days([row]), [50])

    def test_candidates_without_a_hire_are_excluded(self):
        self.assertEqual(time_to_fill_days([make_row()]), [])


class Ageing(unittest.TestCase):
    def test_open_requisitions_are_bucketed_by_age(self):
        rows = [
            make_row(Candidate_ID="C-1", Requisition_ID="R1",
                     Req_Open_Date=REFERENCE - timedelta(days=10)),
            make_row(Candidate_ID="C-2", Requisition_ID="R2",
                     Req_Open_Date=REFERENCE - timedelta(days=45)),
            make_row(Candidate_ID="C-3", Requisition_ID="R3",
                     Req_Open_Date=REFERENCE - timedelta(days=99)),
        ]
        metrics = compute_all(rows, as_of=REFERENCE)
        self.assertEqual(metrics["aging_buckets"], {"0-30": 1, "31-60": 1, "60+": 1})

    def test_at_risk_lists_the_oldest_open_requisition_first(self):
        metrics = compute_all(load_default(), as_of=REFERENCE)
        ages = [r["days_open"] for r in metrics["at_risk_requisitions"]]
        self.assertEqual(ages, sorted(ages, reverse=True))
        self.assertTrue(all(age >= 60 for age in ages))


class Consistency(unittest.TestCase):
    """Cross-checks that catch a metric drifting away from its own inputs."""

    @classmethod
    def setUpClass(cls):
        cls.metrics = compute_all(load_default(), as_of=REFERENCE)

    def test_funnel_counts_never_increase_down_the_funnel(self):
        counts = [entry["count"] for entry in self.metrics["funnel"]]
        self.assertEqual(counts, sorted(counts, reverse=True))

    def test_total_hires_equals_the_funnel_hired_count(self):
        hired = next(e for e in self.metrics["funnel"] if e["stage"] == "Hired")
        self.assertEqual(self.metrics["kpis"]["total_hires"], hired["count"])

    def test_hires_equal_filled_requisitions(self):
        self.assertEqual(
            self.metrics["kpis"]["total_hires"],
            self.metrics["kpis"]["filled_requisitions"],
        )

    def test_department_hires_sum_to_total_hires(self):
        total = sum(entry["hires"] for entry in self.metrics["by_department"])
        self.assertEqual(total, self.metrics["kpis"]["total_hires"])

    def test_region_hires_sum_to_total_hires(self):
        total = sum(entry["hires"] for entry in self.metrics["by_region"])
        self.assertEqual(total, self.metrics["kpis"]["total_hires"])

    def test_source_candidates_sum_to_the_dataset_size(self):
        total = sum(entry["candidates"] for entry in self.metrics["by_source"])
        self.assertEqual(total, self.metrics["dataset"]["candidates"])

    def test_rates_are_proportions(self):
        for key in ("offer_acceptance_rate", "funnel_conversion_rate",
                    "requisition_fill_rate"):
            self.assertGreaterEqual(self.metrics["kpis"][key], 0.0)
            self.assertLessEqual(self.metrics["kpis"][key], 1.0)

    def test_median_time_to_fill_is_not_wildly_off_the_mean(self):
        kpis = self.metrics["kpis"]
        self.assertLess(
            abs(kpis["avg_time_to_fill"] - kpis["median_time_to_fill"]), 20
        )

    def test_hires_this_week_never_exceeds_hires_this_month(self):
        kpis = self.metrics["kpis"]
        self.assertLessEqual(kpis["hires_last_7_days"], kpis["hires_last_30_days"])


if __name__ == "__main__":
    unittest.main()
