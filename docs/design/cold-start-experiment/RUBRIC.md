# Cold-Start Pack Rubric

Instantiation of `SCORING-FRAMEWORK.md` **v1.0.0** for the cold-start experiment. Scores
whether `setup`/`intake` produced a *usable* domain pack + episodes for an un-tuned domain.
Read the framework first; this file only fills in the specifics. Score **near (SRE)** and
**far (TPM)** separately, same day, no hand-tuning (see `EXPERIMENT.md`).

**Real goal (everything is a proxy for this):** *a learner who has never seen this domain can
study from the generated episodes and be meaningfully more prepared — with little or no expert
repair to the pack.* The episodes are what's consumed, so **episode usability outweighs pack
polish** in the verdict.

Verified against repo `main`: 4 domain files, markers and 7 episode components as below.

---

## Gates (binary — a fail caps the verdict; quality % can't rescue it)

| Gate | Check | Notes |
|---|---|---|
| **G1 Pipeline ran** | `setup`/`intake` -> `syllabus` -> `content --episode N` completed with **0 blocking repairs** | "blocking repair" = an edit you *had* to make to proceed (e.g. empty marker) |
| **G2 Markers present & non-stub** | All required markers across the 4 files hold real, non-stub content: `DOMAIN_SEEDS`; `COVERAGE_FRAMEWORK`; `DOMAIN_LENS`, `NITTY_GRITTY_LAYOUT`, `DOMAIN_REQUIREMENTS`, `DISTILL_REQUIREMENTS`, `STAKEHOLDERS`; `GEM_BOOKSHELF`, `GEM_EXAMPLES`, `GEM_CODING`, `GEM_FORMAT_EXAMPLES` | `prep.py status --profile P` detects presence; you judge stub-vs-real |
| **G3 No secret/PII in output** | no key/credential/PII pasted into a pack file | manual hygiene check |

Any gate fail -> see decision rule (caps at FAIL or INCONCLUSIVE).

---

## Group 1 - Pack quality (the 4 domain files) - max 12

Each 0-3 per the framework scale (0 absent/wrong - 1 generic - 2 specific w/ >=1 defect - 3 specific, defect-free).

| # | Dimension | Notes / proxy |
|---|---|---|
| P1 | **Seeds specificity** (`DOMAIN_SEEDS`) - 12 distinct, Staff-level, non-overlapping seeds | curriculum is real not a generic syllabus; overlapping/duplicate seeds = defects |
| P2 | **Coverage realness** (`COVERAGE_FRAMEWORK`) - maps to a **named** real framework | ref: SRE->Google SRE book/Workbook; TPM->a recognized PM competency model. Invented headers = cap at 1 |
| P3 | **Lens fidelity** (`DOMAIN_LENS` + `DOMAIN_REQUIREMENTS` + `STAKEHOLDERS`) | reads as written by someone who knows the field |
| P4 | **Nitty-Gritty reinterpretation** (`NITTY_GRITTY_LAYOUT`) - **the far-domain test** | SRE has wire/protocol analogs; **TPM does not** - did setup remap "Nitty Gritty" to domain artifacts (metrics trees, PRD specifics) or emit nonsense / force a fake protocol section? Most diagnostic pack dimension for portability |

**Trueness sub-check (count):** factual errors across the 4 files vs named refs.
0 -> no cap; 1+ -> caps the relevant dimension at 2; 4+ total -> Group 1 cannot exceed 50%.

---

## Group 2 - Episode quality (score ep 1 and ep 6) - max 18 each combined to 36

7 components per episode: **Title, Hook, Mental Model, Common Trap, Nitty Gritty, Staff Pivot, Scenario Challenge.**

| # | Dimension | Instrument | Notes |
|---|---|---|---|
| E1 | **Depth** | 0-3 (count non-obvious mechanisms/tradeoffs vs textbook restatement) | 3 teaches a senior practitioner something; 1 Wikipedia-level |
| E2 | **Trueness** | 0-3 (count errors vs named ref) | 1+ factual error -> cap at 2 |
| E3 | **Common Trap quality** | 0-3 | 3 real misconceptions that *sound right*; 1 strawmen |
| E4 | **Staff Pivot lands** | 0-3 | 3 genuine shift from "correct" to "architectural/strategic judgment"; 0 no real pivot |
| E5 | **Nitty Gritty survived** | 0-3 | engineering-shaped section produced domain-appropriate specifics? ties to P4 |
| **E6** | **Usable as-is** | **0 or 3** | would you study from this tomorrow without rewriting? No=0 Yes=3. **Nearest the real goal -> highest decision weight** |

6 dims x 3 = 18 per episode; 2 episodes = 36 max.

---

## Effort metrics (most honest signal - record precisely)

| Metric | Definition |
|---|---|
| **Time-to-first-usable-curriculum** | wall clock from `prep.py init` to the first episode you'd genuinely study |
| **Repairs wanted** | count from your no-edit log (itched to fix, didn't) |
| **Blocking repairs** | count of edits you *had* to make to proceed (also fails G1) |

---

## Aggregation

- Pack % = Group 1 subtotal / 12
- Episode % = (both episodes' 6 dims summed) / 36
- Gates separate; trueness caps applied before normalizing
- Confidence **low** if: only the 2 required episodes scored, single human rater on E1-E5, or human/LLM-judge divergence >1 level unreconciled

### Decision rule (mechanical lookup, per domain)

| Condition | Verdict |
|---|---|
| Any gate fail you couldn't resolve | **FAIL** (or INCONCLUSIVE if a one-off fluke worth a re-run) |
| Confidence = low | **INCONCLUSIVE** -> score more episodes / get 2nd rater first |
| Pack >=67% AND Episode >=67% AND 0 blocking repairs AND E6=3 both episodes | **PASS** |
| Meets %s but 1-2 blocking repairs, or E6=0 on an episode, or trueness-capped | **MARGINAL** |
| Below 67% on either group, or 3+ blocking repairs, or an expert-winces trueness error | **FAIL** |

Rationale for 67%: mostly-2s territory (specific, minor defects) - usable with iteration, the honest bar for a *cold* first pass. Tune if too lenient.

### Cross-domain read (after both scored)

| Near (SRE) | Far (TPM) | Meaning for the rewrite |
|---|---|---|
| PASS | PASS | Substrate bet holds. Build at full investment. |
| PASS | MARGINAL/FAIL | Portable within a technical neighborhood, not universal. Build; scope claim to "technical domains"; far is a later bet. |
| MARGINAL | any | Build, but budget real `meta-*` prompt-iteration; don't promise turnkey onboarding. |
| FAIL | - | Cold-start doesn't work. Reconsider scope before the rewrite - may be a single-domain product, substrate over-built. |
| INCONCLUSIVE | any | Don't decide yet. Score 2-4 more episodes (cheap on gpt-4o-mini) and re-run the rule. |

A FAIL that saves you from building the wrong substrate is the experiment **working**.
