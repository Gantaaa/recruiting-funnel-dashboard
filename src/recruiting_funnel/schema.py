"""Field dictionary and controlled vocabularies for the recruiting dataset.

One row of ``recruiting_data.csv`` is one *candidate on one requisition*. A
requisition therefore appears on as many rows as it had applicants, which is
how a real ATS export looks and why most requisition-level metrics have to
deduplicate on ``Requisition_ID`` before counting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# Column order of data/recruiting_data.csv. Kept explicit so a reordered or
# renamed export fails loudly in load() instead of silently shifting columns.
COLUMNS: tuple[str, ...] = (
    "Candidate_ID",
    "Requisition_ID",
    "Team",
    "Department",
    "Region",
    "Recruiter",
    "Hiring_Manager",
    "Source_of_Hire",
    "Candidate_Type",
    "Application_Date",
    "Phone_Screen_Date",
    "Onsite_Date",
    "Offer_Date",
    "Hire_Date",
    "Current_Stage",
    "Req_Open_Date",
    "Time_to_Fill",
    "Headcount_Status",
)

DATE_COLUMNS: tuple[str, ...] = (
    "Application_Date",
    "Phone_Screen_Date",
    "Onsite_Date",
    "Offer_Date",
    "Hire_Date",
    "Req_Open_Date",
)

REGIONS: tuple[str, ...] = ("NA", "EMEA", "APAC", "LATAM")
DEPARTMENTS: tuple[str, ...] = ("Engineering", "Product", "Sales", "Marketing", "G&A")
SOURCES: tuple[str, ...] = (
    "Referral",
    "LinkedIn",
    "Job Board",
    "Agency",
    "Internal",
    "University",
)
CANDIDATE_TYPES: tuple[str, ...] = ("External", "Internal", "Referral", "New Grad")
STAGES: tuple[str, ...] = (
    "Applied",
    "Screen",
    "Onsite",
    "Offer",
    "Hired",
    "Rejected",
    "Withdrawn",
)
HEADCOUNT_STATUSES: tuple[str, ...] = ("Open", "Filled", "On Hold", "Cancelled")

# The funnel is ordered, and each step is reached by having the corresponding
# date populated. Deriving the funnel from dates rather than from Current_Stage
# is deliberate -- see FUNNEL_STAGES below and docs/kpi-definitions.md.
FUNNEL_STAGES: tuple[str, ...] = ("Applied", "Screen", "Onsite", "Offer", "Hired")

# Stage index -> the date column that proves the candidate reached it.
STAGE_DATE_COLUMN: dict[str, str] = {
    "Applied": "Application_Date",
    "Screen": "Phone_Screen_Date",
    "Onsite": "Onsite_Date",
    "Offer": "Offer_Date",
    "Hired": "Hire_Date",
}

# Time-to-fill RAG thresholds (days), used by the dashboard and the deck.
TTF_GREEN_MAX = 45
TTF_AMBER_MAX = 70

# An open requisition older than this is flagged "at risk".
AT_RISK_DAYS = 60


@dataclass(frozen=True, slots=True)
class Row:
    """One candidate-on-requisition record, with dates already parsed."""

    Candidate_ID: str
    Requisition_ID: str
    Team: str
    Department: str
    Region: str
    Recruiter: str
    Hiring_Manager: str
    Source_of_Hire: str
    Candidate_Type: str
    Application_Date: date | None
    Phone_Screen_Date: date | None
    Onsite_Date: date | None
    Offer_Date: date | None
    Hire_Date: date | None
    Current_Stage: str
    Req_Open_Date: date | None
    Time_to_Fill: int | None
    Headcount_Status: str

    def reached(self, stage: str) -> bool:
        """True if this candidate demonstrably reached ``stage``.

        Evidence is the stage's date column being populated, not Current_Stage.
        A candidate who interviewed onsite and was then rejected still reached
        Onsite; Current_Stage only records where they ended up.
        """
        return getattr(self, STAGE_DATE_COLUMN[stage]) is not None

    @property
    def furthest_stage_index(self) -> int:
        """1-based index of the deepest funnel stage this candidate reached."""
        depth = 0
        for i, stage in enumerate(FUNNEL_STAGES, start=1):
            if self.reached(stage):
                depth = i
        return depth
