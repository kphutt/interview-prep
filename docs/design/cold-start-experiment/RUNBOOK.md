# Cold-Start Experiment — Runbook (Windows / PowerShell)

Your reference while running. You're in `C:\Users\karst\dev\interview-prep`, deps installed
(`openai==2.20.0`, pinned — correct, don't change). Companion files: `EXPERIMENT.md` (design),
`RUBRIC.md` (scoring), `SCORING-FRAMEWORK.md` (the reusable method).

**Windows notes:** use `python` (not `python3`). Set the API key per-session in PowerShell —
there is no `source .env`. The `openai.exe not on PATH` and `pip upgrade available` warnings
from install are both harmless; ignore them.

---

## Where you are now
- [x] Repo cloned, in the folder
- [x] `pip3 install -r requirements.txt` done (downgraded 2.21.0 -> 2.20.0 to match pin — fine)
- [ ] API key set  <- you are here
- [ ] Smoketest
- [ ] SRE domain (near)
- [ ] TPM domain (far)
- [ ] Cross-domain decision

---

## Step 0b — Set your API key + smoketest (~2 min, pennies)

Every new PowerShell window needs the key set again (it's per-session):
```powershell
$env:OPENAI_API_KEY = "sk-..."        # paste your real key
```

Confirm the install and that the pipeline runs end to end:
```powershell
python -c "import openai; print(openai.__version__)"   # expect 2.20.0
python prep.py all --profile smoketest --yes
```
If the smoketest completes, your environment is known-good and every failure after this is
signal about the *pack*, not the harness. If it errors on an API call, note it — that's the
one legitimate reason to consider an SDK bump (see bottom).

Drop the experiment files into the repo's docs convention so they travel with the project:
```powershell
New-Item -ItemType Directory -Force -Path docs\design\cold-start-experiment
# move EXPERIMENT.md, RUBRIC.md, SCORING-FRAMEWORK.md, and this RUNBOOK.md into that folder
```

---

# DOMAIN 1 — SRE (near). Do this one fully before touching TPM.

**Start your clock** (time-to-first-usable-curriculum is a scored metric, measured from init).

## Step 1 — Create the profile
```powershell
python prep.py init sre
```
Open `profiles\sre\profile.md`, replace contents with the **NEAR** config from `EXPERIMENT.md`
(role = Staff SRE, `model: gpt-4o-mini`, episode counts, framing comment). Save.

## Step 2 — Author the pack  (pick a path; both for SRE is useful)

**Free path ($0):** open a *fresh* AI chat (no priming). Paste `prompts\intake.md`. Answer
briefly/honestly as a new user. It outputs 5 files — save into:
```
profiles\sre\profile.md
profiles\sre\domain\seeds.md
profiles\sre\domain\coverage.md
profiles\sre\domain\lenses.md
profiles\sre\domain\gem-sections.md
```

**Paid path (~$5-10):**
```powershell
python prep.py setup --profile sre --yes
```

Verify markers landed:
```powershell
python prep.py status --profile sre
```

>>> NO-EDIT RULE STARTS NOW. Open `docs\design\cold-start-experiment\sre-repair-log.md` and
>>> LOG every fix you're tempted to make instead of making it. Only exception: an empty marker
>>> that errors the pipeline -> make the minimum fix, log it as a BLOCKING repair (fails Gate G1).

## Step 3 — Generate one slice (~20-40 min, mostly waiting)
```powershell
python prep.py syllabus --profile sre --yes
python prep.py content --profile sre --episode 1 --yes
python prep.py content --profile sre --episode 6 --yes
```
Outputs in `profiles\sre\outputs\episodes\`. **Stop the clock** once you've read enough of
episode 1 to know if you'd study from it.

## Step 4 — Score same day, with RUBRIC.md open
1. Gates G1/G2/G3 first.
2. Group 1 (pack P1-P4) on the 4 domain files; have the Google SRE book/Workbook TOC open as the named trueness reference.
3. Group 2 (episodes E1-E6) on ep 1 and ep 6. ~1-2 min/dimension; faster = distrust it.
4. Second rater: paste an episode + `RUBRIC.md` into a fresh AI chat: "Score using this rubric;
   follow the LLM-judge output contract — per-dimension score + evidence quote + normalized %."
   Reconcile any >1-level split (re-score with evidence in view; still split -> take the lower).
5. Aggregate -> read the decision rule -> write verdict + numbers into
   `docs\design\cold-start-experiment\sre-scorecard.md`. Low confidence -> INCONCLUSIVE, generate
   2-4 more episodes rather than forcing a call.

---

# DOMAIN 2 — TPM (far). Repeat Steps 1-4 with the FAR config.
```powershell
python prep.py init tpm
```
Use the **FAR** config from `EXPERIMENT.md`. Watch **P4 / E5** especially — does
`NITTY_GRITTY_LAYOUT` remap sensibly to PM artifacts (metrics trees, PRD specifics) or force a
fake protocol section? That's the portability test. Score TPM as harshly as you scored SRE —
resist grading the far domain on a curve. Log to `tpm-repair-log.md` / `tpm-scorecard.md`.

---

# Step 5 — Cross-domain decision (~10 min)
Take both verdicts to the cross-domain table in `RUBRIC.md`. The *pattern* is the answer:
- PASS / PASS -> build the substrate at full investment
- PASS / not -> portable within technical domains; scope the claim; far is a later bet
- near MARGINAL -> build, but budget `meta-*` prompt iteration
- near FAIL -> reconsider scope before the rewrite (may be a single-domain product)
- INCONCLUSIVE -> score 2-4 more episodes, re-run the rule

Write a one-page decision note in `docs\design\cold-start-experiment\`. That note answers the
architecture doc's section 9 and tells you whether the Zod-schema step proceeds.

---

## Traps to avoid
- Don't jump to `gpt-5.2-pro` to rescue a borderline result without scoring the mini output
  first — you need to know if the *pack* or the *model* is the limiter (that's a separate run).
- Don't score the next day — same-day, while the repair-itch is fresh.
- Don't let a polished pack soften your E6 "would I study this tomorrow" call — it's binary on purpose.

## If an OpenAI SDK error appears mid-run (only then)
`pip install --upgrade openai`, re-test, then re-pin what worked. Log it in the repair log as
an ENVIRONMENT fix, not a pack issue, so it doesn't contaminate scoring.

## Per-session reminder
New terminal window = re-run `$env:OPENAI_API_KEY = "sk-..."` before any `prep.py` API command.
