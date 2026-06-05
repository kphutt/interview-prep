# Scoring Framework

**Version: 1.0.0** · A reusable method for turning a subjective "is this good?" judgment
into a measurable, repeatable score that two different scorers — including an LLM judge —
land on within one level of each other.

This file is **domain-independent**. It contains no specifics about any particular thing
being scored. To use it, you *instantiate* it into a rubric for a specific target (see
[Instantiating](#instantiating-for-a-new-target)). Examples: scoring a generated content
pack, a prompt, a README, an API's error handling, a test suite's coverage.

> **Why version it:** once you reuse this across evaluations, a score recorded under v1.0
> is not comparable to one under v2.0 if the scale or aggregation changed. **Every recorded
> score MUST cite the framework version it used** (e.g. `scored with SCORING-FRAMEWORK v1.0.0`).
> Same eval-capture discipline you'd apply to any pipeline: capture the version with the data.

---

## The core idea

A score is only useful if it is **reproducible** (same artifact → same score, across
scorers and across days) *and* **valid** (the thing it measures actually predicts the thing
you care about). Most rubrics chase reproducibility and forget validity; this framework
forces both. The operational test for every criterion you write:

> **Could two different scorers — a human, a different human, and an LLM judge — disagree
> about what this criterion means when looking at the same artifact?**
> If yes, it is not operational yet. Rewrite it until they can't.

---

## Three kinds of measurement (pick the right one per criterion)

Don't grade everything 0–3. Match the instrument to the thing:

| Instrument | Use for | Output |
|---|---|---|
| **Gate (binary)** | Pass/fail prerequisites where partial credit is meaningless ("did it run?", "is every required field present and non-stub?") | ✅ / ❌ |
| **Count** | Anything you can tally in the artifact ("factual errors per 1000 words", "domain-specific concepts named", "empty markers") | integer (+ a direction: lower- or higher-is-better) |
| **Anchored scale (0–3)** | Genuine quality dimensions that resist counting ("depth", "trueness") — and only after you've defined each level observably | 0–3 |

Reserve the 0–3 scale for things that truly need judgment. If you can count it, count it —
counts reproduce; impressions don't. If it's a prerequisite, gate it — gates keep a broken
artifact from earning a flattering quality score.

---

## Writing an anchored scale

Every scale point gets a **concrete, observable descriptor** — something a scorer can point
at in the artifact, not a feeling. The generic template (specialize the `X`):

| Score | Meaning (observable) |
|---|---|
| **0** | X is **absent**, or present but wrong. |
| **1** | X is present but **generic** — would be equally true of any target in this category; says nothing specific. |
| **2** | X is present and **specific**, but has **≥1 defect** (error, gap, or a claim a knowledgeable reviewer would challenge). |
| **3** | X is present, specific, and **defect-free** — you would ship it as-is. |

The two failure modes this guards against: the **"1" trap** (generic filler that pattern-
matches as competent — the most common LLM-generated failure) and the **"2 vs 3" blur**
(resolved by making 3 mean *zero* defects, a countable bar, not "very good").

### Operationalizing the slippery dimensions

Some dimensions (e.g. "expertise", "depth", "would an expert object") are the most important
*and* the hardest to make objective. Don't abandon them and don't fake precision — convert
to a **proxy you can observe or count**:

- "Depth" → *counts named, specific mechanisms / tradeoffs a senior practitioner would know,
  vs. textbook definitions.* A "3" names several non-obvious ones; a "1" restates definitions.
- "An expert would wince" → *error count against a **named** reference source.* Name the
  source in the rubric (a canonical book, spec, or framework) so trueness is checkable, not
  vibes. 0 errors and a domain expert nods = 3; 1+ factual error = capped at 2.
- "Usable as-is" → *binary:* would the intended user act on / consume this without a rewrite?

If a dimension genuinely cannot be made objective, **say so in the rubric** and give the
tightest anchored scale you can plus a calibration anchor. An honest "this one stays partly
subjective" beats a fake number.

### Calibration anchors — sourced from real output, never invented

For the 2–3 most important dimensions, attach a calibration anchor: a concrete example of
what a "1" vs a "3" looks like, so scorers align.

**Do not invent factual example snippets.** An invented "here's what a great answer looks
like" risks containing a subtly wrong claim that then miscalibrates every future scorer
toward the error. Instead:

- **Default:** fill calibration anchors from the **actual first real output** once you have
  it. Until then, mark them `[PLACEHOLDER — fill from first real artifact]`. A rubric that is
  honestly *incomplete until it has seen real output* is correct, not deficient.
- **Allowed up front:** purely **structural** anchors that carry no factual claim — e.g.
  "a 0 on completeness = a required section is literally empty." Those are safe to write now.

---

## The LLM-judge output contract

A rubric is only machine-applicable if the model returns something you can aggregate.
Criteria alone produce prose you can't sum. **Any rubric built from this framework MUST
specify this output contract for an LLM judge:**

For each dimension, the judge returns:
```
- dimension: <name>
  score: <0-3 | count | pass/fail>
  evidence: "<≤25-word quote or precise pointer from the artifact justifying the score>"
```
Then a footer:
```
subtotals: { <group>: <raw>/<max>, ... }
normalized: <overall %>
gates: { <gate name>: pass|fail, ... }
verdict: <read mechanically from the decision rule>
confidence: <high|medium|low> + one-line reason
```
The **evidence quote is mandatory** — it's what makes a score auditable and what you put
"in view" when resolving a disagreement (below). A score with no evidence pointer is not a
score, it's an assertion.

---

## Aggregation

1. Group dimensions (e.g. "pack quality", "output quality"). Counts get converted to a 0–3
   sub-score via a stated mapping (e.g. *0 errors→3, 1→2, 2-3→1, 4+→0*) so everything
   aggregates on one scale.
2. **Subtotal** = sum of a group's dimension scores.
3. **Normalized** = subtotal ÷ max possible, as a %. Thresholds are stated in %.
4. **Gates are separate** — they never average in. A failed gate caps or overrides the
   verdict regardless of how high the quality % is (a broken artifact that reads nicely is
   still broken).

### Worked example (fake numbers, to pin the arithmetic)

A group with 4 dimensions, each 0–3 (max 12):

| Dimension | Score |
|---|---|
| Specificity | 3 |
| Trueness (0 errors→3) | 2 |
| Depth | 2 |
| Coverage | 1 |
| **Subtotal** | **8 / 12** |
| **Normalized** | **8 ÷ 12 = 67%** |

Gate check: `ran without blocking repair = pass`. → eligible for a real verdict.
If the decision rule says "≥ 67% and all gates pass = MARGINAL", the verdict is **MARGINAL**,
read mechanically — no interpretation.

---

## Reliability: making the score trustworthy

- **Two scorers minimum on subjective (0–3) dimensions** — ideally you + an LLM judge.
  Counts and gates are objective enough for one scorer.
- **Divergence rule:** if two scorers differ by **>1 level** on any dimension, the score on
  that dimension is *not yet trustworthy*. Resolve it (below) before aggregating.
- **Distrust your own numbers if:** you scored faster than ~1–2 min/dimension; a single human
  rated a subjective dimension with no second opinion; or human and LLM judge diverge widely
  and you didn't reconcile. Note any of these in the confidence field.

### Disagreement-resolution rule (don't improvise this each time)

When two scorers (or human vs. LLM judge) diverge:
1. **Re-score with evidence in view.** Both put their evidence quote on the table; often one
   scorer simply missed a passage. Re-rate. Most splits resolve here.
2. **If still split:** bring a **third rater**, or apply the stated **default — take the lower
   score.** (Lower-by-default is the conservative choice when the score gates a real decision;
   it biases toward "prove it's good" rather than "assume it's good".)
3. Record that a resolution was needed — it's a signal the dimension's anchors need tightening.

---

## Validity: are you measuring the right thing?

Reproducibility is necessary but not sufficient — a rubric can be perfectly consistent and
measure the wrong thing. For **every dimension**, state:

- **What it's a proxy for** — the real-world property you actually care about.
- **The mislead risk** — how an artifact could score high here yet fail the real goal.

Then weight the decision accordingly: the dimension closest to the real goal should carry the
most decision weight. (Generic example: a content pack can score high on "polished, no errors"
yet produce output nobody wants to consume — so *downstream-usability* must outweigh
*upstream-polish* in the verdict. Score both; trust the one nearer the goal.)

---

## Confidence and the right to be inconclusive

A score that gates a decision **must be allowed to say "not enough signal yet."** Build an
`INCONCLUSIVE` outcome into every decision rule, triggered when:

- too few artifacts were scored (state the minimum n; small n is thin evidence),
- human and LLM judge diverged >1 level on key dimensions and weren't reconciled, or
- scoring was rushed.

`INCONCLUSIVE` → *gather more / re-score before deciding*, never a forced pass/fail. Refusing
to decide on thin evidence is a valid, valuable outcome — not a failure to produce a number.

---

## Instantiating for a new target

To turn this framework into a working rubric for something specific:

1. **Name the real goal.** One sentence: what does "good" ultimately mean *for the decision
   this score feeds*? Everything else is a proxy for this.
2. **List candidate dimensions.** Brainstorm what varies between a good and bad instance.
3. **Assign an instrument to each** (gate / count / anchored scale) per the table above.
   Push toward gates and counts; reserve 0–3 for true judgment.
4. **Write observable anchors** for each scale; name the reference source for any "trueness"
   dimension; mark calibration anchors as `[PLACEHOLDER]` until you have real output.
5. **Define aggregation + the count→score mappings**, and a **worked example**.
6. **Write the decision rule** as a mechanical lookup over (normalized %, gates, counts,
   confidence), including an `INCONCLUSIVE` branch.
7. **Add the validity note** (proxy-for / mislead-risk) per dimension and set decision weights.
8. **State the LLM-judge output contract** (reuse the one above).
9. **Stamp the framework version** the rubric was built against.

---

## Tiny worked example A — a SOFT target (README clarity)

Proves the framework on a judgment-heavy target.

**Real goal:** a new developer can set up and use the project without asking questions.

| Dimension | Instrument | Anchors | Proxy for / mislead risk |
|---|---|---|---|
| Quickstart works | **Gate** | Following the quickstart verbatim succeeds: ✅/❌ | *Proxy:* can a user actually start. *Risk:* none — it's the thing itself. |
| Prerequisite clarity | 0–3 | 0 none stated · 1 listed but vague · 2 specific, 1 gap · 3 specific & complete | *Proxy:* setup friction. *Risk:* complete-looking but untested. |
| Concept findability | Count | # of "how do I X?" a new dev would have after reading, for the project's top 5 tasks (lower better; map 0→3, 1→2, 2-3→1, 4+→0) | *Proxy:* self-service. *Risk:* answers present but buried. |

Gate fails → verdict caps at FAIL regardless of prose quality. That's the framework keeping
a beautiful-but-broken README honest.

## Tiny worked example B — a HARD target (API error handling)

Proves it flexes from "vibes" to objective checklist on a countable target.

**Real goal:** the API fails safely and tells the caller what to do.

| Dimension | Instrument | Anchors |
|---|---|---|
| Every endpoint returns a typed error shape | **Gate** | All endpoints: ✅/❌ |
| Error-path test coverage | Count | # of failure modes (auth, validation, rate-limit, upstream-down, malformed) with a test, of a named checklist of 5 (higher better; 5→3, 4→2, 2-3→1, 0-1→0) |
| Secrets in error output | **Gate** (inverted) | Any error leaks a token/PII/stack-with-secrets? ❌ if yes |
| Retryable vs terminal distinction | 0–3 | 0 absent · 1 present, inconsistent · 2 consistent, 1 miscategorized · 3 every error correctly classified |

Same framework, almost entirely gates and counts — because the target supports it. A soft
target leans on anchored scales; a hard target leans on gates/counts. If both instantiate
cleanly, the framework generalized.

---

*Changelog — v1.0.0: initial framework (gates/counts/anchored scales, LLM-judge contract,
disagreement resolution, validity check, inconclusive outcome, two worked examples).*
