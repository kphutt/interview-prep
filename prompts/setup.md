# Domain Setup — Interview Prep Pipeline

You are an expert technical interview coach. Generate domain-adapted configuration files for an interview prep content pipeline.

## Context

Role: {PREP_ROLE}
Company: {PREP_COMPANY}
Domain: {PREP_DOMAIN}
Audience: {PREP_AUDIENCE}
Date: {AS_OF_DATE}

## Profile Content

The user's profile.md (contains role details and any notes):

```
{PROFILE_CONTENT}
```

## Your Task

Generate exactly 4 adapted files based on the profile above. Output each file with the exact delimiter format shown below — no code fences, no extra commentary before the first delimiter or after the last file.

## Output Format

Output ONLY the 4 files, each preceded by a delimiter line:

```
=== FILE: seeds.md ===
(file content here)

=== FILE: coverage.md ===
(file content here)

=== FILE: lenses.md ===
(file content here)

=== FILE: gem-sections.md ===
(file content here)
```

## File 1: seeds.md

Episode seed data for syllabus generation. This is the most important file — it defines depth and content for 12 core episodes.

Begin with:
```
<!-- DOMAIN_SEEDS -->
Use the following 12 examples as the definition for depth and content.
Do NOT summarize them. Expand on them using the specific technical details provided.

---
```

Then 12 episodes, each formatted as:
```
### Episode N: <Title framed as tension or decision>
**Focus:** <1-line focus>
**Mental Model:** "<Concrete analogy>"
**The Common Trap:** "<What a junior would do wrong>" (Fails because <why it fails at scale>).
**The Nitty Gritty:**
- <2-4 concrete technical bullets: protocols, data structures, algorithms, config details>
**The Staff Pivot:** "<Trade-off argument at Staff level>"
```

Rules for episode seeds:
- Each episode covers ONE core topic from the domain's sub-areas
- Title should be framed as a tension or architectural decision, not a topic label
- Mental Model must be a concrete analogy that helps reason about the problem
- Common Trap must show what breaks at scale (not just "it's wrong" but the operational/business cost)
- Nitty Gritty must include real protocol names, config keys, algorithms, data formats — not vague descriptions
- Staff Pivot must frame a genuine architectural trade-off with competing approaches
- Distribute episodes across all domain sub-areas
- Episodes should progress from foundational to advanced within each sub-area

## File 2: coverage.md

Coverage framework for syllabus generation.

Begin with `<!-- COVERAGE_FRAMEWORK -->` then provide a coverage map instruction. If a standard certification/framework maps to the domain (e.g., CISSP for security, DAMA-DMBOK for data, AWS SA for cloud), reference it:

```
<!-- COVERAGE_FRAMEWORK -->
<Framework Name> Coverage Map (table)
   - Create a table mapping each episode (including Frontier Digests and any gap episodes) to 1-3 <framework> domains (tags) + one-line justification (<= 18 words).
   - Ensure coverage across ALL <N> <framework> domains at least once across the full syllabus.
```

If no standard framework applies, create a custom one with 6-8 coverage areas relevant to the domain.

## File 3: lenses.md

Domain lenses for content and distill prompts. Must have exactly these 5 sections with these exact marker names:

```
<!-- DOMAIN_LENS -->
<1-line description of what "domain depth" means: the specific mechanisms, patterns, and concerns>

<!-- NITTY_GRITTY_LAYOUT -->
    1) **<Subsection specific to the domain>**
    2) **<Subsection specific to the domain>**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
  - Include concrete <domain-specific technical details>.
  - Include concrete <domain-specific data/state handling>.
  - Include explicit threats and concrete failure modes (what breaks, how it breaks).
  - Include operational reality (logs/metrics/SLOs, paging triggers, canary/rollback, blast radius).
  - Include at least one policy/control detail (least privilege, approvals, auditability, retention).

<!-- DISTILL_REQUIREMENTS -->
  - 2 concrete <domain-specific technical details>
  - 2 <domain-specific data/state details>
  - 2 operational details (logs, metrics, SLOs, alerting, rollout/canary, failure modes)
  - 1 policy/control detail (least privilege, approvals, audit, compliance)
  - 1 explicit threat or failure mode

<!-- STAKEHOLDERS -->
<Comma-separated list of key stakeholders, e.g.: Data, Product, Platform, Compliance>
```

Subsections 1-2 in the Nitty Gritty layout should be domain-specific. Subsections 3-6 are standard across domains.

## File 4: gem-sections.md

Domain-specific sections for the Gemini Gem coaching bot. Must have exactly these 4 sections:

```
<!-- GEM_BOOKSHELF -->
Reference these layers during feedback to give the candidate a retrieval framework under pressure.

| Layer | <Domain Concept> | Role |
|-------|----------|------|
| <Layer 1> | <Name> | <1-line description> |
| <Layer 2> | <Name> | <1-line description> |
| ... | ... | ... |

Use it like: "<Example of using the bookshelf in coaching feedback>"

<!-- GEM_EXAMPLES -->
> Domain: "<Example domain-lens interview question>"
>
> RRK: "<Same topic but through operate/reliability lens>"

<!-- GEM_CODING -->
<Domain>-flavored scripting when it arises naturally or on request. Examples: <2-3 concrete examples relevant to the domain>.

<!-- GEM_FORMAT_EXAMPLES -->
<date>|Interview|<Topic>|<Concept>|Owned|<Detail explaining what was tested and how candidate did>|Locked

<date>|Interview|<Topic>|<Concept>|Coached|<Detail explaining nudges needed>|Drill: <specific focus>

<date>|Interview|<Topic>|<Concept>|Missed|<Detail explaining the gap>|STOP: Restudy before interview
```

The Bookshelf should be a 4-6 row reference table mapping domain layers/abstractions that help a candidate organize knowledge under pressure.

## Quality Checks (Run Silently Before Outputting)

- All 4 files use the exact section markers shown above
- seeds.md has exactly 12 episodes with real technical content (no vague "understand X" bullets)
- lenses.md has all 5 sections (DOMAIN_LENS, NITTY_GRITTY_LAYOUT, DOMAIN_REQUIREMENTS, DISTILL_REQUIREMENTS, STAKEHOLDERS)
- gem-sections.md has all 4 sections (GEM_BOOKSHELF, GEM_EXAMPLES, GEM_CODING, GEM_FORMAT_EXAMPLES)
- Episode seeds include real protocol/tool/algorithm names, not just topic labels
- Every Common Trap explains the operational/business cost of the junior approach
- Coverage framework references a real certification/framework or creates a sensible custom one
- Each file delimiter follows the exact format: === FILE: <name> ===
