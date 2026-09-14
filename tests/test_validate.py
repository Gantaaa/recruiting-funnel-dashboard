"""Data-quality rules.

The rules exist because the source workbook's own Data Quality tab reported
99.75% health on a dataset that contained four impossible calendar dates, a
requisition counted as both open and filled, and 49 requisitions whose rows
disagreed about their own department and region. Each rule below pins one of
those failures so it cannot come back.
"""

import unittest
from pathlib import Path

from recruiting_funnel.dataset import DEFAULT_DATA_PATH
from recruiting_funnel.validate import summarise, validate_file, validate_records

ORIGINAL_DATA_PATH = DEFAULT_DATA_PATH.with_name("recruiting_data_original.csv")


def record(**overrides) -> dict:
    base = {
        "Candidate_ID": "C-1", "Requisition_ID": "REQ-1", "Team": "Backend",
        "Department": "Engineering", "Region": "NA", "Recruiter": "Alice Smith",
        "Hiring_Manager": "Manager 01", "Source_of_Hire": "Referral",
        "Candidate_Type": "Referral", "Application_Date": "2026-01-01",
        "Phone_Screen_Date": "", "Onsite_Date": "", "Offer_Date": "",
        "Hire_Date": "", "Current_Stage": "Applied",
        "Req_Open_Date": "2026-01-01", "Time_to_Fill": "",
        "Headcount_Status": "Open",
    }
    base.update(overrides)
    return base


def rules(records: list[dict]) -> set[str]:
    return {issue.rule for issue in validate_records(records)}


class Rules(unittest.TestCase):
    def test_a_clean_record_produces_no_issues(self):
        self.assertEqual(validate_records([record()]), [])

    def test_impossible_calendar_dates_are_caught(self):
        # February 29th does not exist in 2026, and a spreadsheet stores it as
        # text -- which is exactly why date comparisons silently passed it.
        self.assertIn("INVALID_DATE", rules([record(Phone_Screen_Date="2026-02-29")]))
        self.assertIn("INVALID_DATE", rules([record(Onsite_Date="2026-01-33")]))

    def test_a_value_outside_the_controlled_vocabulary_is_caught(self):
        self.assertIn("UNKNOWN_ENUM", rules([record(Region="Antarctica")]))
        self.assertIn("UNKNOWN_ENUM", rules([record(Source_of_Hire="Carrier Pigeon")]))

    def test_stage_dates_running_backwards_are_caught(self):
        found = rules([record(
            Application_Date="2026-03-01",
            Phone_Screen_Date="2026-02-01",
        )])
        self.assertIn("DATE_OUT_OF_ORDER", found)

    def test_a_stage_claimed_without_its_date_is_caught(self):
        self.assertIn(
            "MISSING_STAGE_DATE",
            rules([record(Current_Stage="Hired", Hire_Date="")]),
        )

    def test_a_missing_required_anchor_is_caught(self):
        self.assertIn("MISSING_REQUIRED", rules([record(Req_Open_Date="")]))

    def test_a_skipped_stage_date_is_flagged(self):
        found = rules([record(Onsite_Date="2026-02-01", Phone_Screen_Date="")])
        self.assertIn("SKIPPED_STAGE_DATE", found)

    def test_duplicate_candidate_ids_are_caught(self):
        found = rules([record(Candidate_ID="C-1"), record(Candidate_ID="C-1")])
        self.assertIn("DUPLICATE_CANDIDATE_ID", found)

    def test_a_requisition_with_two_statuses_is_caught(self):
        found = rules([
            record(Candidate_ID="C-1", Headcount_Status="Open"),
            record(Candidate_ID="C-2", Headcount_Status="Filled"),
        ])
        self.assertIn("INCONSISTENT_REQ_STATUS", found)

    def test_a_requisition_that_moves_department_is_caught(self):
        found = rules([
            record(Candidate_ID="C-1", Department="Engineering"),
            record(Candidate_ID="C-2", Department="Sales"),
        ])
        self.assertIn("INCONSISTENT_REQ_ATTRIBUTE", found)

    def test_issues_carry_the_row_number_they_came_from(self):
        issues = validate_records([record(), record(Candidate_ID="C-2", Region="Nowhere")])
        enum_issue = next(i for i in issues if i.rule == "UNKNOWN_ENUM")
        self.assertEqual(enum_issue.row, 3)  # header is row 1
        self.assertEqual(enum_issue.candidate_id, "C-2")


class Summary(unittest.TestCase):
    def test_health_counts_rows_not_issues(self):
        """One row with three problems is one unhealthy row, not three."""
        records = [record(Region="Nowhere", Source_of_Hire="Nope", Req_Open_Date="")]
        summary = summarise(len(records), validate_records(records))
        self.assertGreater(summary["errors"], 1)
        self.assertEqual(summary["rows_with_errors"], 1)
        self.assertEqual(summary["health"], 0.0)

    def test_warnings_do_not_reduce_health(self):
        records = [record(Onsite_Date="2026-02-01", Phone_Screen_Date="")]
        summary = summarise(len(records), validate_records(records))
        self.assertEqual(summary["errors"], 0)
        self.assertGreater(summary["warnings"], 0)
        self.assertEqual(summary["health"], 1.0)


class ShippedDatasets(unittest.TestCase):
    def test_the_generated_dataset_is_clean(self):
        issues = validate_file(DEFAULT_DATA_PATH)
        self.assertEqual(
            [i for i in issues if i.severity == "error"], [],
            "data/recruiting_data.csv should validate cleanly",
        )

    @unittest.skipUnless(ORIGINAL_DATA_PATH.exists(), "original export not present")
    def test_the_archived_original_still_reproduces_its_known_defects(self):
        """Guards the before/after story in the README against bit-rot."""
        found = {i.rule for i in validate_file(ORIGINAL_DATA_PATH)}
        self.assertIn("INVALID_DATE", found)
        self.assertIn("INCONSISTENT_REQ_STATUS", found)
        self.assertIn("INCONSISTENT_REQ_ATTRIBUTE", found)


if __name__ == "__main__":
    unittest.main()
