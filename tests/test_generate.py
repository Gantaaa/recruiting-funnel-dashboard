"""The generator must produce a dataset that is internally coherent.

These are the invariants the original hand-built dataset violated: 49 of its
50 requisitions carried rows that disagreed about the department, region and
open date of the same requisition.
"""

import unittest
from collections import defaultdict
from datetime import date

from recruiting_funnel.generate import generate
from recruiting_funnel.schema import FUNNEL_STAGES, STAGE_DATE_COLUMN

REFERENCE = date(2026, 9, 14)


class GeneratorInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = generate(seed=20260914, reference_date=REFERENCE)
        cls.by_requisition = defaultdict(list)
        for row in cls.rows:
            cls.by_requisition[row["Requisition_ID"]].append(row)

    def test_is_deterministic_for_a_given_seed(self):
        again = generate(seed=20260914, reference_date=REFERENCE)
        self.assertEqual(self.rows, again)

    def test_a_different_seed_gives_a_different_dataset(self):
        other = generate(seed=1, reference_date=REFERENCE)
        self.assertNotEqual(self.rows, other)

    def test_requisition_attributes_are_constant_within_a_requisition(self):
        for requisition_id, group in self.by_requisition.items():
            for column in ("Department", "Team", "Region", "Recruiter",
                           "Req_Open_Date", "Headcount_Status"):
                values = {row[column] for row in group}
                self.assertEqual(
                    len(values), 1,
                    f"{requisition_id} has conflicting {column}: {values}",
                )

    def test_team_always_rolls_up_to_its_own_department(self):
        from recruiting_funnel.generate import TEAM_TO_DEPARTMENT
        for row in self.rows:
            self.assertEqual(TEAM_TO_DEPARTMENT[row["Team"]], row["Department"])

    def test_funnel_dates_run_forward(self):
        for row in self.rows:
            dates = [
                row[STAGE_DATE_COLUMN[stage]]
                for stage in FUNNEL_STAGES
                if row[STAGE_DATE_COLUMN[stage]]
            ]
            self.assertEqual(dates, sorted(dates), row["Candidate_ID"])

    def test_a_candidate_cannot_skip_a_stage(self):
        """Reaching a stage implies every earlier stage date is populated."""
        for row in self.rows:
            reached = [
                bool(row[STAGE_DATE_COLUMN[stage]]) for stage in FUNNEL_STAGES
            ]
            deepest = max(i for i, hit in enumerate(reached) if hit)
            self.assertTrue(
                all(reached[: deepest + 1]),
                f"{row['Candidate_ID']} has a gap in its stage dates",
            )

    def test_no_dates_in_the_future(self):
        for row in self.rows:
            for column in STAGE_DATE_COLUMN.values():
                if row[column]:
                    self.assertLessEqual(row[column], REFERENCE)

    def test_a_requisition_is_filled_at_most_once(self):
        for requisition_id, group in self.by_requisition.items():
            hires = [row for row in group if row["Hire_Date"]]
            self.assertLessEqual(len(hires), 1, requisition_id)

    def test_filled_requisitions_have_exactly_one_hire(self):
        for requisition_id, group in self.by_requisition.items():
            if group[0]["Headcount_Status"] != "Filled":
                continue
            hires = [row for row in group if row["Hire_Date"]]
            self.assertEqual(len(hires), 1, requisition_id)

    def test_open_requisitions_have_no_hire(self):
        for requisition_id, group in self.by_requisition.items():
            if group[0]["Headcount_Status"] != "Open":
                continue
            self.assertEqual([r for r in group if r["Hire_Date"]], [], requisition_id)

    def test_candidate_ids_are_unique(self):
        ids = [row["Candidate_ID"] for row in self.rows]
        self.assertEqual(len(ids), len(set(ids)))

    def test_time_to_fill_matches_the_dates_it_is_derived_from(self):
        for row in self.rows:
            if row["Hire_Date"]:
                expected = (row["Hire_Date"] - row["Req_Open_Date"]).days
                self.assertEqual(row["Time_to_Fill"], expected)
            else:
                self.assertIsNone(row["Time_to_Fill"])

    def test_current_stage_never_claims_more_than_the_dates_show(self):
        for row in self.rows:
            if row["Current_Stage"] == "Hired":
                self.assertIsNotNone(row["Hire_Date"], row["Candidate_ID"])
            if row["Current_Stage"] == "Offer":
                self.assertIsNotNone(row["Offer_Date"], row["Candidate_ID"])


if __name__ == "__main__":
    unittest.main()
