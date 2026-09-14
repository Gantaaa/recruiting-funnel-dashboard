# Example output

This is a real narrative produced by `generateNarrative()`, recovered verbatim
from the `AI_Output` tab of the workbook. It is not a mock-up — the `Logs` tab
records the run that produced it, along with the Slides deck it was written
into. (The deck URLs point into a private Drive, so the document ids are
redacted below.)

```
46183.72687936343  FAILED: LLM_API_KEY not set in Script Properties
46183.72700601852  FAILED: LLM_API_KEY not set in Script Properties
46183.72914503472  FAILED: LLM_API_KEY not set in Script Properties
46183.73385812500  FAILED: LLM_API_KEY not set in Script Properties
46183.74061070602  SUCCESS: https://docs.google.com/presentation/d/[redacted]/edit
46183.75129571759  SUCCESS: https://docs.google.com/presentation/d/[redacted]/edit
46184.44650186342  SUCCESS: https://docs.google.com/presentation/d/[redacted]/edit
```

The four failures are the credential check doing its job before the key was
set, which is the behaviour you want: the run stops at the missing property
rather than part-building a deck.

## The narrative, verbatim

> **HEADLINE**
> The main takeaway is that we have not made any hires this week, and our
> average time to fill a position is approximately 43 days.
>
> **WHAT CHANGED**
> There were no changes in the number of open requisitions, hires, or time to
> fill from last week, with no hires and no movement in time to fill.
>
> **RISKS**
> Our headcount is currently at 72.5% of plan, which may indicate a risk in
> meeting our hiring targets, and our offer acceptance rate of 55.2% may also
> be a concern.
>
> **OPPORTUNITIES**
> Our funnel conversion rate of 16.0% presents an opportunity to improve our
> hiring process and increase the number of candidates moving through the
> funnel to become hires.

It is well-structured, it is in the register a VP of Talent would expect, and
it invents nothing — every figure it cites really was on the dashboard.

## Two of those four figures were wrong

| Figure as narrated | What it actually was |
|---|---|
| "headcount is currently at **72.5% of plan**" | Not "of plan" at all — there is no hiring plan anywhere in the dataset. The formula was `Filled ÷ (Open + Filled)`, a fill rate, and its denominator counted one requisition twice, so it divided by 51 for a file containing 50 requisitions. |
| "offer acceptance rate of **55.2%**" | Came from the legacy funnel, which collapsed rejected and withdrawn candidates back to "Applied" and so undercounted the offer stage. Corrected, the same export gives **46.0%**. |

The other two — ~43 days average time-to-fill, 16.0% funnel conversion —
happened to be right.

## Why this is in the repository

This is the clearest argument for everything else here.

The model did its job perfectly. It was told to use only the figures it was
given and to invent nothing, and it obeyed. It then wrote a confident,
well-organised executive summary in which half the cited numbers were wrong,
and one of them was described by a name that does not correspond to anything
the data contains.

Nothing in the output looks wrong. There is no hedge, no anomaly, no stray
formatting to catch the eye — and it would have gone to a VP of Talent under
the heading **RISKS**.

An LLM narration layer inherits the correctness of the metric layer underneath
it and adds fluency on top, which makes a wrong number *more* persuasive rather
than less. That is why the metrics moved into
[`metrics.py`](../src/recruiting_funnel/metrics.py) with
[tests](../tests/test_metrics.py) pinning each definition, and why
[`validate.py`](../src/recruiting_funnel/validate.py) runs before any metric is
computed. The narrative step is the last thing in the pipeline that can be
trusted, so everything it reads from has to be checked first.
