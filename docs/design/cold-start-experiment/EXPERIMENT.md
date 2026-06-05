# Cold-Start Pack Authoring Experiment

**The bet:** can `setup` / `intake` produce a *usable* domain pack for a domain you've never
hand-tuned? The shipped `security-infra` profile was refined over weeks - that proves nothing
about cold-start. This removes the hand-tuning and asks: how good is the first pass, and how
far from usable?

**Why it gates the rewrite:** if cold-start works, the "domain compiler" substrate is
justified (domains are cheap data experiments). If it fails, the architecture is still sound
but the business is a domain-specific product - and you'd scale back the substrate. You want
this answer *before* writing the manifest schema, not after.

**Files:** scoring method lives in `SCORING-FRAMEWORK.md` (reusable); the actual dimensions +
decision rule in `RUBRIC.md`. This file is just the runbook. (Fits the repo's
`docs/design/{initiative}/` convention - drop these under `docs/design/cold-start-experiment/`.)

---

## Design: two domains, deliberately chosen

| Domain | Why | A pass here proves |
|---|---|---|
| **Near - Site Reliability Engineering** | Adjacent to security-infra: shared ops/infra vocab, a real coverage canon (Google SRE book / Workbook), Staff depth exists. | `setup` generalizes *within the neighborhood* - the easy case. If this fails, cold-start is dead. |
| **Far - Technical Product Management** | Deliberately outside engineering-depth: **no wire/protocol "Nitty Gritty" analog**, success is judgment not correctness. Stresses every interview-prep-shaped assumption in the prompts. | `setup` generalizes *out of domain* - the real test. The `NITTY_GRITTY_LAYOUT` reinterpretation (rubric P4/E5) is the portability test in miniature. |

Run both. Near tells you if cold-start works at all; far tells you if it's a compiler or a
security-prep app with a swap feature.

---

## Procedure (one weekend, ~$0-20)

For **each** domain:

### Phase 1 - Author the pack (the experiment itself)
Two paths; run at least one, ideally both for the near domain to compare $0 vs paid:
- **Free (`intake.md`):** `python3 prep.py init sre`, paste `prompts/intake.md` into a fresh
  chat (cold - no priming), answer briefly & honestly as a real new user, paste the 5 generated
  files into `profiles/sre/...`. **No hand-edits.**
- **Paid (`setup`):** fill `profile.md` (below), `python3 prep.py setup --profile sre --yes`.
  3 API calls (`meta-seeds` -> seeds+coverage, `meta-lenses`, `meta-gem`), ~$5-10. No hand-edits.

### Phase 2 - Generate one slice (enough to judge, not the full run)
```
python3 prep.py syllabus --profile sre --yes
python3 prep.py content --profile sre --episode 1 --yes
python3 prep.py content --profile sre --episode 6 --yes
```
Set `model: gpt-4o-mini` in `profile.md` for the first pass (default is `gpt-5.2-pro` - real
money on a full run). Only re-run on a strong model if mini output is borderline and you need
to know whether the *model* or the *pack* is the limiter.

### Phase 3 - Score it same day, using RUBRIC.md
Score near and far separately. Ideally score each twice (you + an LLM judge using the rubric's
output contract), reconcile any >1-level splits, then read the decision rule. Don't skip the
confidence/INCONCLUSIVE check - n=2 episodes is thin by design.

---

## The no-hand-tuning rule (read twice)

The instinct will be to "just fix" a weak seed or bad lens. Don't - that's the manual repair
the experiment measures. **Log every repair you're tempted to make instead of making it;** the
size of that list *is* a result. A pack you'd need to rewrite is a fail even if you could
rewrite it well, because "you, an expert, rewriting it" is not the substrate working - it's you.

If you must repair to get *any* output (empty marker -> pipeline errors), make the minimum fix
and log it as a **blocking repair** - those fail Gate G1 and count double against viability.

---

## profile.md - NEAR (SRE)
Save as `profiles/sre/profile.md` after `prep.py init sre`:
```markdown
role: Staff Site Reliability Engineer
company: a top tech company with large-scale distributed systems
domain: Site Reliability Engineering
audience: Senior Software Engineers and SREs
model: gpt-4o-mini
core_episodes: 8
frontier_episodes: 4
# Framing: SRE at scale - SLIs/SLOs/error budgets, incident command, on-call & toil,
# capacity/load, observability (metrics/logs/traces), distributed-systems failure modes,
# progressive delivery, postmortem culture. Coverage anchor: Google SRE book + Workbook + PRR.
```

## profile.md - FAR (Technical PM)
Save as `profiles/tpm/profile.md` after `prep.py init tpm`:
```markdown
role: Principal Technical Product Manager
company: a top tech company shipping platform/infrastructure products
domain: Technical Product Management
audience: Senior PMs and engineering leads moving into product
model: gpt-4o-mini
core_episodes: 8
frontier_episodes: 4
# Framing: technical PM for platform/infra - strategy & prioritization, PRDs/spec-writing,
# metrics & North-Star/driver trees, experimentation/A-B, stakeholder alignment, technical
# tradeoff judgment, roadmap/resourcing, GTM for dev/infra products.
# SCORING NOTE: no engineering "wire/nitty-gritty" analog - watch how setup reinterprets
# NITTY_GRITTY_LAYOUT (rubric P4). That reinterpretation IS the far-domain test.
```

---

## Outcome -> action (full table in RUBRIC.md)
- Near PASS + Far PASS -> build the substrate at full investment.
- Near PASS + Far not -> portable within technical domains; far is a later bet.
- Near MARGINAL -> build, but budget `meta-*` prompt iteration.
- Near FAIL -> reconsider scope; you may be building a single-domain product.
- INCONCLUSIVE -> score 2-4 more episodes (cheap) before deciding.

A "FAIL, build smaller" result from a weekend is a **win** - you learned it before locking the
manifest schema, not after.
