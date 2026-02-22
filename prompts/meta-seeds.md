# Meta-Prompt: Seeds + Coverage Framework

You are an expert technical interview coach. Given a profile description and optional context documents, generate two domain files: episode seeds and a coverage framework.

## Input

**Role:** {ROLE}
**Company:** {COMPANY}
**Domain:** {DOMAIN}
**Audience:** {AUDIENCE}

### Profile Content

{PROFILE_CONTENT}

### Context Documents

{CONTEXT_DOCS}

## Output

Generate TWO sections, each starting with its marker comment. Output ONLY the content below — no preamble, no explanations.

---

### Section 1: Seeds

<!-- DOMAIN_SEEDS -->
Use the following 12 examples as the definition for depth and content.
Do NOT summarize them. Expand on them using the specific technical details provided.

---

### Episode 1: <Title framed as tension or decision>
**Focus:** <1-line focus>
**Mental Model:** "<Concrete analogy>"
**The L4 Trap:** "<What a junior would do wrong>" (Fails because <why it fails at scale>).
**The Nitty Gritty:**
- <2-4 concrete technical bullets: protocols, data structures, algorithms, config details>
**The Staff Pivot:** "<Trade-off argument at Staff level>"

### Episode 2: ...
(repeat for all 12 episodes)

### Section 2: Coverage Framework

<!-- COVERAGE_FRAMEWORK -->
<Framework Name> Coverage Map (table)
   - Create a table mapping each episode (including Frontier Digests and any gap episodes) to 1-3 framework domains (tags) + one-line justification (<= 18 words).
   - Ensure coverage across ALL framework domains at least once across the full syllabus.

If no standard certification or knowledge framework applies to the domain, create a custom coverage map with 6-8 coverage areas relevant to the domain.

## Rules for Episode Seeds

- Each episode covers ONE core topic from the domain's sub-areas
- Title should be framed as a tension or architectural decision, not a topic label
- Mental Model must be a concrete analogy that helps reason about the problem
- L4 Trap must show what breaks at scale (not just "it's wrong" but the operational/business cost)
- Nitty Gritty must include real protocol names, config keys, algorithms, data formats — not vague descriptions
- Staff Pivot must frame a genuine architectural trade-off with competing approaches
- Distribute episodes across all sub-areas (2-3 episodes per sub-area for 4-6 sub-areas)
- Episodes should progress from foundational to advanced within each sub-area

## Quality Self-Checks (Run Silently Before Outputting)

- seeds section has exactly 12 episodes with real technical content (no vague "understand X" bullets)
- Episode seeds include real protocol/tool/algorithm names, not just topic labels
- Every L4 Trap explains the operational/business cost of the junior approach
- Coverage framework references a real certification/framework or creates a sensible custom one
- Coverage map covers all episodes including frontier digests
- Both sections start with the correct `<!-- MARKER -->` comments
