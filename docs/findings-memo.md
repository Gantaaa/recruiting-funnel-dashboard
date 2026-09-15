# Why our hiring numbers didn't add up

**To:** Talent Strategy leadership
**From:** Gantamir Gankhuyag
**Re:** Errors found in the recruiting dashboard, and what I changed

*This memo is written against the synthetic prototype in this repository, in
the form I would send it to a real TA leadership team. No real company or
candidate data is involved.*

---

## The short version

Our dashboard said the average role took **43 days to fill**. That number was
not trustworthy, and neither were three of the five other headline figures on
the executive view. The dashboard's own data-quality check reported everything
was **99.75% healthy** the entire time.

None of this looked broken. Every tab loaded, every chart drew, every number
was formatted correctly. That is what made it worth stopping to check.

I have rebuilt the calculations, and the corrected figures are now live. Below
is what was wrong, why it happened, and what it would have cost us.

## What was wrong

**Roles were double-counted, and counted against the wrong teams.**

Every role should appear in our data with one team, one region, and one date it
opened. In 49 of our 50 roles, different rows disagreed about all three — the
same requisition would show as Engineering on one row and Sales on another.

This matters more than it sounds. The requisition number is how we connect a
hire back to the role it filled. When that link is unreliable, *time-to-fill is
measuring nothing*: we were subtracting a randomly chosen "date opened" from a
real hire date. The 43-day figure wasn't slightly off. It was arbitrary.

One role was also counted as both open and filled, so our requisition totals
came to 51 for a set containing 50.

**We counted candidates by where they ended up, not how far they got.**

Someone who interviewed onsite and was then rejected was recorded as never
having progressed past "applied." Roughly 40% of our candidates fall into that
group, so the funnel showed a cliff at the very first stage that did not exist.

Applied-to-screen conversion read **59%**. The real figure was **82%**.

**Offer acceptance was overstated.** The same counting error inflated it to
**55%** when it was actually **46%**.

**"Headcount vs Plan: 72.5%" was not a comparison to plan.** There is no
hiring plan in our data to compare against. The figure was the share of roles
that had been filled — a reasonable metric with a misleading name on it.

**A whole department was invisible.** Marketing — 12.5% of all candidates —
appeared in no breakdown on any tab, because the department lists on the
dashboard were typed in by hand and Marketing was left off.

**The recruiter tab showed four recruiters who don't work here.** The names
were carried over from an example. Every row read zero hires, zero open roles.
It looked entirely normal.

## Why it happened

Not carelessness on any single day. Three ordinary causes:

1. **The checks tested the wrong thing.** Our data-quality tab counted blank
   cells and duplicate names. Nothing checked whether a role was internally
   consistent, which is where the real damage was.
2. **Impossible dates were stored as text.** Four records carried dates like
   29 February in a non-leap year. Spreadsheets compare text to dates without
   complaining, so the date check passed them.
3. **Lists were typed, not read.** Departments and recruiters were hardcoded,
   so the dashboard silently stopped reflecting reality as the data changed.

## What it would have cost us

- **Capacity planning.** A 43-day time-to-fill says our process is healthy. If
  the true figure is materially higher, we are under-resourced and don't know.
- **Where we invest.** A funnel showing a cliff at screen sends us to fix
  sourcing. The real drop-off is later, which is an interview-process problem.
- **Offer strategy.** Acceptance at 55% looks acceptable. At 46% it warrants a
  compensation review.
- **Recruiter conversations.** A table of zeros, presented as performance data,
  is worse than showing nothing.

## What I changed

Every metric is now calculated in one place, and each definition has a test
that fails the build if the number moves unexpectedly. Eleven checks run over
the raw data before any figure is computed — including the ones that would have
caught all of the above. The weekly history is recalculated from the underlying
records each time rather than accumulated, so it can no longer drift.

The dashboard has a toggle showing the old and corrected funnel side by side.

## What I'd ask for

1. **Agree the definitions.** Time-to-fill and time-to-hire are different
   clocks and we currently use them interchangeably. Fifteen minutes to settle
   which one leadership reports on.
2. **Treat a data-quality failure as a blocker.** If the checks fail, the
   weekly report should not send. Right now nothing stops it.
3. **Rename "Headcount vs Plan"** — or give me the hiring plan, and I'll build
   the metric it currently pretends to be.
