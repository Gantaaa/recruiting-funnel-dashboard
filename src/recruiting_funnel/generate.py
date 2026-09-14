"""Seeded generator for the synthetic recruiting dataset.

Why this exists
---------------
The dataset originally exported from the workbook treated ``Requisition_ID`` as
a random label: 49 of its 50 requisitions carried rows disagreeing about the
department, region and open date of the *same* requisition. Every
requisition-level metric -- open requisitions, time-to-fill, at-risk ageing --
joins on that key, so all of them were measuring noise.

Here a requisition is a first-class entity generated first (one department, one
team, one region, one recruiter, one open date), and candidates are attached to
it afterwards. Funnel dates are always monotonic, and everything is anchored to
``reference_date`` so the dashboard never goes stale.

Nothing here describes a real company, candidate or hire.
"""

from __future__ import annotations

import argparse
import csv
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .schema import COLUMNS, FUNNEL_STAGES, REGIONS, SOURCES, STAGE_DATE_COLUMN

# Teams roll up into exactly one department, so the two columns can never
# disagree the way they did in the original export.
TEAM_TO_DEPARTMENT: dict[str, str] = {
    "Backend": "Engineering",
    "Frontend": "Engineering",
    "Data Science": "Engineering",
    "Product": "Product",
    "Design": "Product",
    "Sales": "Sales",
    "Customer Success": "Sales",
    "Marketing": "Marketing",
    "Finance": "G&A",
    "People Ops": "G&A",
}

RECRUITERS = ("Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Reyes")
HIRING_MANAGERS = tuple(f"Manager {n:02d}" for n in range(1, 21))
CANDIDATE_TYPES = ("External", "Internal", "Referral", "New Grad")

# Probability a candidate who reached stage N also reaches stage N+1. Tuned so
# the end-to-end applied -> hired rate lands in a plausible 6-9% band.
STAGE_PASS_RATE = {"Applied": 0.58, "Screen": 0.40, "Onsite": 0.50, "Offer": 0.88}

# Recruiters extend offers one at a time per requisition, so most candidates
# who clear the onsite bar never actually receive one -- the seat goes to
# somebody else first. This is the share of those near-miss candidates who did
# get an offer and turned it down, which is what the offer-acceptance rate
# measures. Without it, every strong onsite candidate looks like a declined
# offer and the acceptance rate collapses.
OFFER_DECLINE_SHARE = 0.20

# Share of applicants who arrive later in a requisition's life rather than in
# the burst just after it opens -- sourced candidates, re-posts, referrals.
LATE_APPLICANT_SHARE = 0.30

# Typical gap in days between consecutive stages, as (low, high).
STAGE_GAP_DAYS = {
    "Screen": (3, 12),
    "Onsite": (5, 18),
    "Offer": (4, 15),
    "Hired": (5, 21),
}

# Some sources convert better than others; this is what makes the source
# effectiveness tab say something instead of showing noise.
SOURCE_WEIGHT = {
    "Referral": 1.45,
    "Internal": 1.30,
    "LinkedIn": 1.00,
    "University": 0.90,
    "Job Board": 0.78,
    "Agency": 0.95,
}


@dataclass(slots=True)
class Requisition:
    requisition_id: str
    team: str
    department: str
    region: str
    recruiter: str
    hiring_manager: str
    open_date: date
    status: str


def _build_requisitions(rng: random.Random, count: int, reference: date) -> list[Requisition]:
    teams = list(TEAM_TO_DEPARTMENT)
    reqs: list[Requisition] = []
    for n in range(1, count + 1):
        team = rng.choice(teams)
        # Spread openings across the ten months before the reference date so
        # ageing buckets and weekly trends both have something to show.
        open_date = reference - timedelta(days=rng.randint(5, 300))
        reqs.append(
            Requisition(
                requisition_id=f"REQ-{open_date.year}-{n:04d}",
                team=team,
                department=TEAM_TO_DEPARTMENT[team],
                region=rng.choices(REGIONS, weights=(40, 28, 20, 12))[0],
                recruiter=rng.choice(RECRUITERS),
                hiring_manager=rng.choice(HIRING_MANAGERS),
                open_date=open_date,
                status="Open",  # resolved below, once we know who was hired
            )
        )
    return reqs


def _walk_funnel(rng: random.Random, req: Requisition, applied: date, source: str) -> dict:
    """Advance one candidate through the funnel, returning their stage dates."""
    dates: dict[str, date | None] = {stage: None for stage in FUNNEL_STAGES}
    dates["Applied"] = applied

    cursor = applied
    for stage in FUNNEL_STAGES[1:]:
        previous = FUNNEL_STAGES[FUNNEL_STAGES.index(stage) - 1]
        pass_rate = STAGE_PASS_RATE[previous]
        if previous != "Offer":
            # Source quality compounds across the funnel rather than acting
            # only at the top, which is what makes the source-effectiveness
            # tab show a stable ranking instead of small-sample noise.
            pass_rate = min(0.95, pass_rate * (SOURCE_WEIGHT[source] ** 0.6))
        if rng.random() > pass_rate:
            break
        low, high = STAGE_GAP_DAYS[stage]
        cursor = cursor + timedelta(days=rng.randint(low, high))
        dates[stage] = cursor
    return dates


def _current_stage(rng: random.Random, dates: dict, reference: date) -> str:
    """Where the candidate ended up, given how far they actually got."""
    reached = [s for s in FUNNEL_STAGES if dates[s] is not None]
    deepest = reached[-1]
    if deepest == "Hired":
        return "Hired"
    # Anyone whose last activity is old has resolved one way or the other;
    # recent activity means they are genuinely still in process.
    if (reference - dates[deepest]).days < 21:
        return deepest
    return rng.choices(("Rejected", "Withdrawn"), weights=(0.62, 0.38))[0]


def generate(
    *,
    seed: int = 20260914,
    requisitions: int = 70,
    candidates: int = 750,
    reference_date: date | None = None,
) -> list[dict]:
    """Produce a coherent synthetic dataset as a list of CSV-ready dicts."""
    rng = random.Random(seed)
    reference = reference_date or date.today()

    reqs = _build_requisitions(rng, requisitions, reference)

    # Weight requisitions so some roles attract far more applicants than
    # others, which is what makes per-req pipeline depth worth looking at.
    weights = [rng.uniform(0.4, 3.0) for _ in reqs]

    # Pass 1: walk every candidate through the funnel independently.
    drafts: list[dict] = []
    for n in range(candidates):
        req = rng.choices(reqs, weights=weights)[0]
        source = rng.choices(SOURCES, weights=(22, 20, 21, 14, 6, 17))[0]
        candidate_type = (
            "Internal" if source == "Internal"
            else "Referral" if source == "Referral"
            else "New Grad" if source == "University"
            else "External"
        )

        # Applications cluster in the weeks just after a requisition opens
        # rather than spreading evenly over its whole life, which is what keeps
        # time-to-fill in a realistic band instead of drifting with req age.
        window = max((reference - req.open_date).days - 5, 1)
        if rng.random() < LATE_APPLICANT_SHARE:
            # Sourced or re-posted later in the requisition's life, which is
            # what keeps recent weeks from looking empty on long-open roles.
            offset = rng.randint(0, window)
        else:
            offset = int(rng.triangular(0, min(window, 75), 0))
        applied = req.open_date + timedelta(days=min(offset, window))

        dates = _walk_funnel(rng, req, applied, source)

        # Drop anything that would land in the future.
        for stage in FUNNEL_STAGES:
            if dates[stage] and dates[stage] > reference:
                for later in FUNNEL_STAGES[FUNNEL_STAGES.index(stage):]:
                    dates[later] = None
                break
        if not dates["Applied"]:
            continue

        drafts.append(
            {
                "candidate_id": f"C-{10001 + n}",
                "req": req,
                "source": source,
                "candidate_type": candidate_type,
                "dates": dates,
            }
        )

    # Pass 2: a requisition can only be filled once. Among the candidates who
    # reached Hired on the same req, the earliest hire date wins the seat. The
    # rest are resolved by when they got there: anyone already at offer when
    # the seat went is an offer that was not accepted, and anyone who would
    # have been offered later simply never gets one, because the req closed.
    # Doing this as a second pass keeps the outcome independent of the order
    # candidates happen to be generated in.
    by_req: dict[str, list[dict]] = defaultdict(list)
    for draft in drafts:
        by_req[draft["req"].requisition_id].append(draft)

    hired_by_req: dict[str, date] = {}
    for requisition_id, group in by_req.items():
        hires = [d for d in group if d["dates"]["Hired"]]
        if not hires:
            continue
        winner = min(hires, key=lambda d: d["dates"]["Hired"])
        hired_by_req[requisition_id] = winner["dates"]["Hired"]
        for draft in group:
            if draft is winner or not draft["dates"]["Offer"]:
                continue
            draft["dates"]["Hired"] = None
            if rng.random() >= OFFER_DECLINE_SHARE:
                # Never actually offered: the seat went to someone else while
                # they were still in process, so they stop at their onsite.
                draft["dates"]["Offer"] = None

    rows: list[dict] = []
    for draft in drafts:
        req, dates = draft["req"], draft["dates"]
        stage = _current_stage(rng, dates, reference)
        rows.append(
            {
                "Candidate_ID": draft["candidate_id"],
                "Requisition_ID": req.requisition_id,
                "Team": req.team,
                "Department": req.department,
                "Region": req.region,
                "Recruiter": req.recruiter,
                "Hiring_Manager": req.hiring_manager,
                "Source_of_Hire": draft["source"],
                "Candidate_Type": draft["candidate_type"],
                "Application_Date": dates["Applied"],
                "Phone_Screen_Date": dates["Screen"],
                "Onsite_Date": dates["Onsite"],
                "Offer_Date": dates["Offer"],
                "Hire_Date": dates["Hired"],
                "Current_Stage": stage,
                "Req_Open_Date": req.open_date,
                "Time_to_Fill": (
                    (dates["Hired"] - req.open_date).days if dates["Hired"] else None
                ),
                "Headcount_Status": "",  # resolved below
            }
        )

    # Resolve requisition status once, from whether anyone was hired into it.
    for req in reqs:
        if req.requisition_id in hired_by_req:
            req.status = "Filled"
        else:
            req.status = rng.choices(
                ("Open", "On Hold", "Cancelled"), weights=(0.86, 0.09, 0.05)
            )[0]
    status_by_req = {r.requisition_id: r.status for r in reqs}
    for row in rows:
        row["Headcount_Status"] = status_by_req[row["Requisition_ID"]]

    rows.sort(key=lambda r: r["Candidate_ID"])
    return rows


def write_csv(rows: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: (value.isoformat() if isinstance(value, date) else
                          "" if value is None else value)
                    for key, value in row.items()
                }
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260914)
    parser.add_argument("--requisitions", type=int, default=70)
    parser.add_argument("--candidates", type=int, default=750)
    parser.add_argument(
        "--reference-date",
        type=date.fromisoformat,
        default=None,
        help="anchor date for the dataset (default: today)",
    )
    parser.add_argument("--out", default="data/recruiting_data.csv")
    args = parser.parse_args(argv)

    rows = generate(
        seed=args.seed,
        requisitions=args.requisitions,
        candidates=args.candidates,
        reference_date=args.reference_date,
    )
    write_csv(rows, args.out)
    print(f"wrote {len(rows)} rows to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
