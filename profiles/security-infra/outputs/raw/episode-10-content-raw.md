## Title
Crypto Agility (Post‑Quantum): Hybrid TLS + Rotate the Math Without a Code Push

## Hook
- Post‑quantum is not a one‑time “upgrade TLS” task; it’s a multi‑year compatibility program where old clients, pinned partners, and enterprise middleboxes keep negotiating against your edge every day.
- “Store now, decrypt later” collapses the usual security timeline: traffic captured today can become a breach years later, so prioritization is about *confidentiality horizon*, not just current exploitability.
- Hybrid TLS key exchange increases handshake CPU and message size, directly pressuring handshake p99 latency budgets and edge capacity planning (and turning “security improvement” into an SRE paging risk).
- Crypto agility is a reliability feature: when primitives/policies change, you need a controlled rotation path that doesn’t require 100 services to patch + redeploy under incident pressure.
- The ecosystem doesn’t move in lockstep: PQ in X.509 signatures is far more brittle than PQ in key exchange, so “full PQ” is constrained by tooling, PKI chains, and client validators—not just crypto libraries.
- Agility cuts both ways: if you “support many algorithms,” you expand your attack surface via downgrade/ossification and algorithm confusion (especially in JOSE/JWT), creating hard-to-debug auth failures at scale.
- Rollouts must be reversible within minutes: canarying hybrid TLS without fast server-side kill switches turns handshake failures into prolonged outages with no safe mitigation.
- Without continuous crypto inventory (TLS endpoints, token signing/verification, storage encryption configs), you cannot scope impact during an algorithm incident, and compliance attestations become manual and error-prone.
- Policy/compliance constraints (e.g., FIPS-aligned regions, audit evidence, change control) can slow change; Staff-level work is designing controls that enable *both* safe emergency rotation and credible audit trails.

## Mental Model
Crypto agility is like swapping an engine while the car is doing 70 mph: you can’t pull over the entire fleet, and every driver’s car (client) is a different model year. Hybrid crypto is like running two engines in parallel for a while so the car keeps moving even if one engine design turns out to be flawed. The real constraint is coordinating the swap across a fleet you don’t fully control while keeping crash rates (outages) near zero.

- The “fleet” maps to heterogeneous clients/partners/middleboxes; operationally this means long dual-policy windows, exception governance, and cohort-based rollouts.
- “Two engines in parallel” maps to ECDHE (e.g., X25519) + PQ KEM (ML‑KEM class) and combining secrets so either primitive failing doesn’t collapse confidentiality.
- “Quick-release mounts” maps to primitive-agnostic crypto APIs + centralized runtime policy so you can rotate algorithms/keys without code pushes across services.
- “Dashboard at 70 mph” maps to mandatory telemetry: what clients offered, what you selected, resumption rates, and failure reasons—otherwise incident response becomes packet-capture archaeology.
- Failure/adversary mapping: a “bad mechanic” is downgrade/ossification (or an attacker/middlebox forcing weaker negotiation), leaving you unknowingly running on the classical “engine” only.

## Common Trap
- Red flag: “We’ll wait until PQ is fully standardized and ubiquitous” — fails because long-lived secrets can be recorded today and partners pin stacks for 12–18+ months; it converts ambiguity into a future emergency cutover with high outage probability and sustained on-call toil.
- Red flag: “Hardcode algorithms/key sizes in application code” — fails at scale because 100 services drift and emergency rotation requires mass rebuilds/redeploys; it creates developer friction, long lead times, inconsistent compliance posture, and a high-risk, partial rollout.
- “Enable hybrid TLS everywhere at once” — fails because the first-order impacts are CPU spikes and ClientHello size intolerance in enterprise networks; it burns error budgets quickly and forces chaotic rollback when you lack segmentation by client cohort/hostname.
- Red flag: “Agility means we accept many JOSE `alg` values and trust token headers” — fails because algorithm confusion and `kid`-driven key selection bugs become pervasive; it increases code paths, test matrix size, and incident frequency (auth failures) across services.
- “Let each team tune crypto settings locally” — fails because policy drift (TLS versions, curves, key sizes) becomes unbounded; SRE/debugging effort goes up service-by-service, and compliance evidence becomes a manual scavenger hunt.
- “We’ll debug from user-reported failures instead of instrumenting negotiation” — fails because handshake errors are under-specified and cohort attribution is hard; it creates long MTTR during rollouts and makes safe canaries effectively impossible.

## Nitty Gritty
**Protocol / Wire Details**
- TLS 1.3 agility is negotiated via `ClientHello` extensions: `supported_versions`, `supported_groups`, `key_share`, `signature_algorithms`; at the edge, you need structured visibility into what is *offered* vs what is *selected*.
- Hybrid key exchange: collect two shared secrets—one from classical ECDHE (e.g., X25519) and one from a PQ KEM (ML‑KEM/Kyber class)—within a single handshake where possible.
- Combine the two secrets via HKDF in a transcript-bound, labeled way so compromise of either primitive alone does not reveal handshake traffic keys (and so “hybrid” can’t be silently reduced to “classical only” by implementation bugs).
- Hybrid increases first-flight sizes; monitor ClientHello size distribution because some middleboxes drop/timeout on large hellos or unknown group IDs, producing hard-to-diagnose connection failures.
- Certificate interoperability reality: keep server certs on broadly supported classical signatures (RSA/ECDSA) while piloting PQ in key exchange; PQ signatures in X.509 are ecosystem-sensitive (chain building, intermediates, client validators).
- Token verification agility is dangerous without strictness: enforce JOSE `alg` allowlists (e.g., `ES256`, `EdDSA`) and reject `alg=none`; ensure the key type (EC/OKP/RSA) matches the algorithm to prevent confusion.
- Use explicit `kid` as a key-version selector (JWKS, JWS header, or internal metadata) but treat it as untrusted input; do not allow arbitrary key fetching based on `kid`.
- Use hostname/SNI-based policy to target hybrid to endpoints carrying 10–15 year confidentiality data, avoiding “all traffic pays the cost” while still meeting risk requirements.
- Anchor: `supported_groups` — primary signal for PQ/hybrid client capability.
- Anchor: `key_share` — where hybrid size/CPU costs materialize.

**Data Plane / State / Caching**
- JWKS/public-key material must be cached aggressively: honor `Cache-Control`/`max-age`, use `ETag` conditional GETs, and implement stale-while-revalidate so transient control-plane issues don’t become data-plane auth outages.
- Maintain bounded `kid → key` caches with negative caching for unknown `kid`s to prevent per-request network calls and to blunt attacker-driven cache-miss floods.
- Dual-verify windows: accept signatures from key version N and N‑1 for an overlap period; publish keys before first use and retire only after max token TTL + clock skew to avoid widespread auth breakage.
- TLS session resumption is your latency/cost lever: maximize TLS 1.3 PSK/session ticket resumption so hybrid handshake cost doesn’t dominate p99; treat resumption rate as an SLI (not just a nice-to-have).
- Session ticket key rotation must include overlap (decrypt old, encrypt new) and consistent distribution across the edge fleet; otherwise a ticket-key change causes handshake storms and user-visible latency spikes.
- Replay boundaries: if TLS 1.3 0‑RTT is enabled, restrict to idempotent operations; otherwise disable to avoid replay risk and incident forensics complexity.
- Anchor: resumption_rate_sli — leading indicator of hybrid cost regression.
- Anchor: `kid` — enables rotation and dual-verify without code changes.

**Threats & Failure Modes**
- Downgrade/ossification: middleboxes/legacy stacks force negotiation away from PQ/hybrid (or strip unknown groups), turning “hybrid” into “mostly classical”; detect via “offered PQ but negotiated classical” rates and enforce minimums on protected endpoints.
- Middlebox intolerance failure mode: oversized ClientHello can manifest as connection resets/timeouts early in handshake; without cohort attribution, this becomes a noisy, prolonged on-call incident.
- Algorithm confusion in JOSE: accepting arbitrary `alg` or not binding `kid` to issuer/audience lets attackers steer verification into weak or wrong primitives; treat token headers as attacker-controlled.
- Red flag: “Support every algorithm for agility” — scales into untestable combinations and incident-prone policy drift.
- Inventory gaps are a threat amplifier: during an algorithm break you can’t scope blast radius, and compliance can’t attest “no forbidden alg usage,” leading to blunt emergency disables with product fallout.
- Partial PQ coverage risk: canarying hybrid at 10% doesn’t protect captured traffic outside that slice; for 10–15 year data, ensure deterministic routing to protected endpoints (avoid accidental downgrade via misrouting/redirects).
- FIPS-aligned region constraint: PQ primitives may lag validated-module availability; be explicit about what runs where, document compensating controls, and ensure auditors can trace policy state at any point in time.
- Central policy misconfig is a reliability risk: a single bad policy push (disallowing widely-used groups) can cause fleet-wide handshake failures; require staged rollout + preflight validation against real client offers.

**Operations / SLOs / Rollout**
- Canary hybrid TLS by *client cohort* (library/version, OS family, partner ID) and by hostname/SNI; random sampling is insufficient for attribution and partner safety.
- Telemetry requirements: structured events for `{selected_group, offered_groups, client_hello_size, resumed, failure_bucket, client_fingerprint}` with privacy-aware sampling; you need time-series deltas for rapid rollback decisions.
- SLO guardrails: define explicit rollback thresholds tied to handshake p99 and CPU; policy pushes should be automatically halted/rolled back when thresholds breach for sustained windows.
- Rollback must be control-plane only: toggles to remove PQ KEM groups, adjust supported_groups ordering, or temporarily force classical + resumption, all without code deploys.
- Incident response (“algorithm incident”) playbook: stop minting new artifacts with the risky primitive, extend dual-verify/dual-decrypt windows, coordinate partner comms, and validate inventory to confirm containment.
- Crypto inventory: continuously enumerate algorithm usage across TLS termination, JWT signing/verifying, and storage encryption configs; tie items to owners and produce compliance evidence automatically.
- Central crypto policy enforcement: CI blocks introduction of disallowed algorithms; runtime enforcement rejects noncompliant configs; exceptions require owner + expiry to prevent permanent legacy.
- Capacity/cost planning: hybrid’s CPU impact can be a step-function; run canaries with pre-provisioned headroom and explicit cost/SLO trade-offs agreed with SRE and product owners.

**Interviewer Probes (Staff-level)**
- Probe: How would you combine ECDHE and ML‑KEM secrets in TLS 1.3 so neither can be silently dropped?
- Probe: What metrics/logs prove that “hybrid is actually negotiated” (not just configured) under ossification pressure?
- Probe: In a FIPS-aligned region, how do you handle PQ pilots while still producing audit-grade evidence and rollback readiness?
- Probe: How do you design `kid` rotation + JWKS caching so a JWKS outage doesn’t become a data-plane incident?

**Implementation / Code Review / Tests**
- Coding hook: Enforce JOSE `alg` allowlist + key-type match; unit-test `alg=none`, mismatched `alg`, and wrong-key-type tokens.
- Coding hook: Treat `kid` as opaque/untrusted; cap size/charset, bound lookup complexity, and negative-test random-`kid` floods (no per-request JWKS fetch).
- Coding hook: Implement JWKS caching with `ETag` + stale-while-revalidate; integration-test verifier behavior during control-plane/JWKS endpoint outage.
- Coding hook: Add policy preflight: simulate proposed `supported_groups` against sampled real ClientHello offers; block rollouts that would strand major cohorts.
- Coding hook: Hybrid TLS correctness tests: assert hybrid negotiation occurs when offered; assert deterministic fallback behavior per hostname policy.
- Coding hook: Resumption regression tests: ensure resumption rate and handshake p99 stay within thresholds after enabling hybrid; chaos-test session ticket key rotation overlap.
- Coding hook: Rollback safety under load: flip policy to disable PQ KEM mid-incident and verify graceful continuation (no crashes, bounded error spike).

## Staff Pivot
- Competing approaches: **(A)** do nothing until mandated, **(B)** big-bang PQ cutover, **(C)** crypto-agile abstraction + selectively enable hybrid on high-value paths.
- **A** optimizes for today’s simplicity but guarantees tomorrow’s emergency: when policy or primitives change, you’ll have no inventory, no rollback muscle, and a sprawling redeploy queue—high MTTR and stakeholder panic.
- **B** is “architecturally pure” but operationally reckless: it ignores pinned partners, legacy runtimes, and middlebox intolerance, turning a security project into an availability incident with long-lived exceptions.
- I pick **C**: make the platform *agile first* (central policy + primitive-agnostic APIs + telemetry), then turn on hybrid where the confidentiality horizon justifies cost (10–15 year data classes).
- Decisive trade-off: accept bounded handshake overhead + control-plane complexity to dramatically reduce the probability and blast radius of a one-day algorithm incident that forces unsafe mass changes.
- Scope control to manage latency: apply hybrid by SNI/endpoint class, not globally; use resumption aggressively so hybrid cost is paid mainly on cold handshakes.
- What I’d measure continuously: handshake CPU/time (p50/p95/p99), ClientHello size distribution, resumption rate SLI, handshake error rate by client cohort, and “offered PQ but negotiated classical” on protected endpoints (ossification signal).
- What I’d measure for developer friction/toil: number of services with local overrides, time-to-rotate via policy, paging rate during rollouts, and number/age of exceptions with no expiry.
- What I’d page on: CPU step-changes after policy pushes, resumption-rate drops, cohort-correlated handshake failures, and any protected endpoint negotiating classical-only above a low threshold.
- Risk acceptance: accept partial PQ coverage early (canary + partner lag) but do not accept unknown algorithm usage (no inventory), untested rollback, or rotations that require code pushes across teams.
- Stakeholder alignment: set a phased plan with Compliance (audit artifacts + deprecation dates), SRE (guardrails + capacity), Product/Partner Eng (compat matrix + partner comms), Security (threat horizon + minimum bar); enforce exceptions with owners and expiry.
- What I would NOT do (tempting but wrong): widen algorithm support “for agility,” or let each service pick crypto knobs—this creates algorithm confusion risk, policy drift, and makes on-call debugging non-scalable.
- Tie-back: Describe a time you used policy/config to rotate a security control under time pressure.
- Tie-back: Describe how you aligned SRE latency goals with a security-driven protocol rollout.

## Scenario Challenge
- You run an edge TLS termination layer at **300k RPS**; handshake **p99 < 30ms** and availability **99.99%** are non-negotiable SLOs.
- A subset of traffic carries data with **10–15 year confidentiality** requirements; assume adversaries can record encrypted traffic today (“store now, decrypt later”).
- You must support legacy clients (older Android, Java 8) and enterprise middleboxes that may drop unknown extensions or large ClientHello messages; **no flag day**.
- Partners pin TLS settings; some cannot upgrade for **18 months**. You must run dual policy and produce an accurate report of which partners/cohorts block progress.
- A government region must remain **FIPS-aligned**; algorithm changes require audit evidence, change control, and a documented rollback plan (including evidence of what policy was active when).
- Developer friction constraint: **100 internal services** share a common crypto library; teams cannot rewrite call sites. “Rotate the math” must be mostly config/policy-driven.
- You enable hybrid TLS for **10%** canary traffic; edge CPU jumps **40%**, and some clients fail handshakes due to oversized ClientHello / intolerance.
- You have telemetry knobs, but privacy constraints mean logs are sampled; you can still measure handshake negotiation outcomes, ClientHello size, resumption rate, and errors by client cohort.
- On-call twist: you have **15 minutes** to stop availability impact; rolling back hybrid everywhere may violate the confidentiality requirement for the protected data class.
- Hard technical constraint: you cannot patch partner clients or enterprise middleboxes; only edge policy/config and shared-library behavior are changeable in the near term.
- Multi-team twist: Compliance insists on “PQ now” with weekly written progress; SRE insists on no latency regression; Partner Eng insists on zero breakage for top partners.
- Migration/back-compat twist: some services also terminate TLS internally and issue/verify JWTs; inventory is incomplete—so “edge-only hybrid” may not cover the full path unless you choose boundaries carefully.
- Governance constraint: exceptions must be time-bounded and reviewable; you cannot create a manual approval bottleneck that becomes the critical path for every rollout.
- You’re asked to propose: phased enablement, exception governance, and a weekly metrics package that simultaneously tracks security coverage and SLO health.

**Evaluator Rubric**
- Establishes clear assumptions: what traffic is in-scope for 10–15 year confidentiality, how it’s identified (SNI/endpoint classification), and what “FIPS-aligned” operationally constrains.
- Demonstrates risk prioritization under ambiguity: where hybrid provides the most marginal benefit vs where it’s wasted cost, and how to avoid false confidence from partial coverage.
- Proposes an architecture/rollout that is cohort-safe and rollbackable within minutes, with explicit blast-radius control and compatibility strategy for pinned partners.
- Uses SRE-grade telemetry and SLIs: handshake latency distribution, CPU, resumption rate, negotiated group selection, cohort failure rates, JWKS cache hit rates; defines rollback thresholds and alerting.
- Addresses downgrade/ossification explicitly: how to detect “configured hybrid but negotiated classical,” how to enforce minimums on protected endpoints, and how to handle clients that can’t comply.
- Includes an incident response plan for the CPU spike + handshake failures that preserves confidentiality requirements while stopping immediate availability impact.
- Handles compliance/audit trade-offs: captures policy state over time, documents rollback plans, and avoids unreviewable “security exceptions forever.”
- Minimizes developer friction: uses stable abstraction APIs and centralized policy so service teams don’t change call sites; includes CI/runtime controls to prevent drift.
- Shows stakeholder influence: concrete mechanisms to align Compliance, SRE, Security, and Partner Eng on phased milestones, exception expiry, and shared metrics.