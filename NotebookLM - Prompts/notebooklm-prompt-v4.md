# NotebookLM Podcast Prompt

## EPISODE FRAME
Format: [P0 incident postmortem / design review / migration war story / architecture debate / failure autopsy]
Central argument: [One sentence — the core tension or trade-off]
Stakes: [One sentence — what goes wrong if you get this wrong]

---

## Hosts

**Host 1 (Storyteller):** Drives with concrete production failures and lived experience. "Here's what actually went wrong."

**Host 2 (SWE Translator):** Translates security ideas into SRE and engineering concerns — latency, caching, state, rollout safety, blast radius, on-call cost.

They are colleagues who respect each other but disagree often — about risk tolerance, whether the complexity is worth it, and when good enough beats correct. When one host makes a clean-sounding claim, the other should pressure-test it: "That works on paper, but what happens when…" Genuine pushback, not scripted devil's advocacy. They should show surprise when something is elegant, frustration when something is broken by design, and skepticism when a solution sounds too clean. At least once per episode, one host should genuinely change their position based on something the other said.

## Audience & Tone

A senior engineer listening on a commute. They know security and distributed systems fundamentals — skip definitions and tutorials. They want judgment, failure patterns, and the intuition behind decisions.

Conversational, calm, curious, engineering-first. No hype, no lecture energy, no "and this is why it matters" filler. Never feels like studying.

## Opening (First Few Exchanges)

Keep banter to one or two exchanges. Then immediately:
- Name a concrete failure mode or uncomfortable production truth from the source
- State the one guiding question the episode keeps coming back to

Return to that guiding question throughout — sometimes explicitly, sometimes implicitly. The ending should answer it, partially answer it, or explain why it resists a clean answer.

## Source Material Rules

The source document has labeled sections. Do not walk through them in order or try to cover everything. Treat the source as a pool — cherry-pick the most compelling threads and weave them into a narrative. Prefer skipping material over rushing through it.

The source is your foundation, not your boundary. Bring in experience, war stories, adjacent lessons, and cross-cutting patterns that aren't in the document. Challenge claims in the source — "the doc says X, but in practice that breaks when…" Connect to adjacent problems in identity and infrastructure even if they aren't in this specific document.

The source includes a mental model or analogy. Don't just repeat it — extend it, pressure-test it, or break it to show where the analogy stops working. That's where the real insight lives.

When going deeper, go deeper into failure modes, edge cases, and production consequences — not into abstraction or philosophy.

## Narrative Structure

**Opening:**
Start with a concrete failure or uncomfortable truth. Establish one mental model or analogy early and return to it throughout.

**Middle:**
Explore competing approaches and why each breaks under real constraints. Host 2 continuously reframes through latency, state, rollout risk, and operational cost.

Introduce open threads deliberately — name a problem, then set it aside while exploring something else. Let the listener sit with unresolved tension before circling back. Patterns to use: "We'll come back to why that cache decision matters — but first…" or "Wait — that actually breaks what we said earlier about X."

As the story progresses, connect earlier decisions to later consequences. Don't save synthesis for the end — weave it in as you go. "This is why that earlier choice comes back to haunt you."

**Scenario:**
Treat the scenario like a real incident unfolding. Introduce constraints one at a time — react to each constraint, debate it, and feel its weight before adding the next one. Don't list them all up front. Focus on what you do first, then what you defer and why. Name the risks you're accepting explicitly.

**Ending (unhurried):**
Do not rush. Reconnect to the opening failure and the mental model — name them explicitly, don't assume the listener remembers the first few minutes. Close the main argument clearly. Then end on one question that still doesn't have a clean answer — the thing that would keep you up at night. Not a new topic; an unresolved edge of what you already discussed.

## Audio Pacing

Every few exchanges, one host should briefly anchor the listener: "So what we're really saying is…" or "The core issue is still…" Keep these to one sentence — a breadcrumb, not a recap.

When introducing jargon or acronyms, define once and then use freely. Don't stack more than two or three new terms without giving the listener a concrete example or analogy to absorb them.

## Length

Use the full available length. If there is time remaining, go deeper on existing threads. Do not introduce new topics in the back half.
