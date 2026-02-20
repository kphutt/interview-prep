## Title
Episode 15 — Frontier Digest C (Feb 2026): Signals, PQC, Keys, and Two‑Person Control  
Evolving detection, crypto agility, data protection, and privileged access under real SLOs, degraded modes, and audit pressure

## Hook
- “We had controls” keeps failing because the controls were designed for steady state: telemetry drops during backlog/maintenance, KMS throttles during rewrap, approval systems partition during incidents—attackers only need the control plane to wobble once.
- Post‑quantum is now a rollout and compatibility problem, not a research problem: hybrid TLS (classical + ML‑KEM) inflates ClientHello bytes and CPU, and ossified middleboxes/legacy clients turn “enable PQC” into a p99 handshake and availability incident.
- Detection is shifting from “add more SIEM rules” to “own a streaming system”: you need schema contracts (OpenTelemetry), enrichment that doesn’t create join storms, and explicit SLOs (freshness, completeness) that can page—otherwise you ship silent blindness.
- AI/LLM triage can reduce SOC toil, but it can also manufacture confidence: attacker-controlled log fields can prompt-inject summaries, and hallucinated narratives become incident decision inputs unless you treat LLM output as a UI layer over immutable evidence.
- Envelope encryption is table stakes, but the hard part is operational misuse resistance and outage tolerance: AES-GCM-SIV helps when nonce uniqueness is operationally fragile, but KMS brownouts force bounded DEK caching and explicit “fail closed vs fail open” tier decisions.
- Privileged access is converging on JIT + multi-party approval + phishing-resistant step-up (WebAuthn/FIDO2), but on-call needs a degraded mode; the design goal is “degraded-but-audited,” not “degraded-to-standing-admin.”
- Compliance deadlines (PQC measurable progress; two-person control in 90 days) collide with developer reality (100+ services, half frozen): controls must land via gateways/sidecars/shared libs and policy, not bespoke per-service rewrites.
- Stakeholder constraints are mutually inconsistent unless you make risk trade-offs explicit: Product wants zero latency regression, SRE wants no new global hard dependencies, Compliance wants “no exceptions,” SOC wants fewer pages—Staff work is turning this into a tier policy + exception governance that survives incidents.

## Mental Model
Treat the security stack as a production feedback system: sensors measure reality (telemetry + integrity), control loops decide policy actions (approvals + crypto policy), and actuators change system state (revocation + rotation). At scale, the system fails when any layer lies or is unavailable—because the loop keeps “stabilizing” the wrong model. Your job is to design for partial failure, with SLOs and rollback levers that keep the loop honest under on-call pressure.

- Sensors → OpenTelemetry log pipelines + audit logs with integrity; you need freshness/completeness SLOs and alerting on missing data, not just alerts on “bad events.”
- Control loops → policy engines for TLS group requirements and multi-party approval workflows; these must have explicit degraded-mode semantics and be measurable (approval latency, bypass rate).
- Actuators → key rotation/rewrap, token/grant expiry, emergency revocation epochs; actuators must work even when dependencies are degraded (local verification, bounded caching).
- Plant → the fleet plus shared dependencies (KMS, approval service, log ingestion); treat them like reliability-critical systems with error budgets, not “security tooling.”
- Real failure mode mapping → attackers can force telemetry gaps (DDoS/backpressure/collector crash) and trigger TLS downgrade paths; if your sensors don’t detect the gap/downgrade, your control loops will confidently do nothing.

## Common Trap
- Junior approach: “Enable hybrid/PQC everywhere now”; fails at scale because ML‑KEM key shares increase handshake bytes/CPU, breaking legacy clients and middleboxes and blowing handshake p99/availability; the resulting rollback whiplash creates permanent allowlists and exception debt.
- Junior approach: “Require two-person approval for every privileged action”; fails when the approval service partitions or approvers aren’t reachable during P0s; on-call invents shadow bypasses (shared accounts, copied tokens), increasing toil and making audit trails incomplete.
- Red flag: “Success = more SIEM rules / more AI triage”; fails because schema drift + enrichment joins create latency/backpressure, and false positives page the wrong teams; developers respond by sampling logs, removing fields, or disabling exporters to protect SLOs.
- Red flag: “KMS for every read with no caching because ‘security’”; fails under KMS brownouts/throttling and cascades into fleet-wide outages; teams then add ad hoc caches without TTL/invalidation invariants, creating long-lived key exposure and incident ambiguity.
- Red flag: “Let the LLM close alerts or run remediation”; fails under prompt injection (attacker-controlled log strings) and hallucinated root cause; it increases incident risk and post-incident audit pain because decision rationale isn’t tied to immutable evidence.
- Junior approach: “Rewrap/rotate everything with a big batch job”; fails by spiking KMS load and throttling critical paths, creating partial migration states and emergency pause/runbook toil; reliability teams will block future security migrations if this causes outages.

## Nitty Gritty
**Protocol / Wire Details**
- Detection pipelines standardize event structure: OpenTelemetry Logs with stable `resource.*` identifiers (e.g., `service.name`, `cloud.region`, `host.id`), plus explicit `event.schema_version` so detections-as-code can be reviewed and canaried against a contract.
- “Detections as code” governance: Sigma-like rule definitions map to normalized OTel attributes; PR review enforces schema compatibility, and rule canaries run on a sampled stream before full enablement to control paging blast radius.
- Hybrid TLS 1.3 negotiation mechanics: the client advertises PQC + classical in `supported_groups`, sends corresponding `key_share` entries, and the server selects; you must log negotiated group (and resumption vs full handshake) to detect silent downgrade and quantify cost.
- PQC hybrid cost reality: ML‑KEM key shares are ~kilobytes; ClientHello growth can trigger fragmentation/MTU/middlebox limits and increase CPU on both sides, so rollout must be segmented by client fingerprint and network path, not just “% traffic.”
- Session resumption as the p99 lever: lean on TLS tickets/PSK (`pre_shared_key`, `psk_key_exchange_modes`) to keep hybrid KEM cost off steady state; track resumption rate as a first-class SLO input (low resumption = hybrid cost hits every request).
- JIT privileged access tokens: mint short-lived OIDC tokens (minutes) with `aud`, `exp`, and step-up strength in `acr`/`amr` (e.g., WebAuthn); gateways/sidecars enforce claims when services can’t change code.
- SSH for privileged ops: use OpenSSH certificates with `valid_before`, constrained `principals`, and restrictions like `source-address` / `force-command`; log cert serial + principal for attribution without logging payloads.
- Anchor: `supported_groups` — Detect PQC downgrade by negotiated group
- Anchor: `acr/amr` — Encode step-up strength for JIT enforcement

**Data Plane / State / Caching**
- Streaming detection architecture: collectors → broker/queue → normalizer → rule engine; measure event-time vs processing-time delay (watermarks) to enforce the <2 min p95 event→alert SLA under backlog and maintenance.
- Hot-path enrichment without join storms: precompute and cache mappings (asset tier, service owner, principal→team, IP→ASN) in-memory at the rule engine; TTLs must balance staleness vs dependency load, and cache misses must degrade gracefully (tag as “unknown,” don’t block).
- Revocation as a low-latency control: propagate a monotonic `revocation_epoch` (or similar) so enforcement points can invalidate cached grants/tokens without synchronous calls during incidents; one integer bump becomes an emergency kill switch.
- Anchor: `grant_id` — Stable key joining approval, enforcement, audit logs
- Envelope encryption metadata discipline: store `{kek_id, dek_id, alg, nonce, wrapped_dek}` alongside ciphertext; rotation/rewrap workflows use these fields to track progress and to bound blast radius during rollback.
- Anchor: `kek_id/dek_id` — Track rotation status and decrypt dependencies safely
- KMS outage tolerance pattern: bounded in-memory DEK cache keyed by `{kek_id, dek_id}` with strict TTL + size caps; circuit-break KMS on error bursts to protect fleet SLOs while making “stale DEK use” an explicit, logged risk acceptance for low-risk reads.
- Tamper-evident audit trails: append-only/WORM storage plus hash chaining (and/or vendor integrity features) for 1-year retention; log decision metadata (who/what/when/why via IDs) but never raw tokens or sensitive URLs.

**Threats & Failure Modes**
- Silent downgrade combo-failure: hybrid TLS negotiated away (client/middlebox ossification) while telemetry gaps hide the downgrade; mitigation is dual—log negotiated group per segment + page on ingestion gaps so “no data” is treated as “no control.”
- Telemetry integrity attacks: attackers can flood or crash collectors to force sampling/drops; integrity controls (hash chain, immutable retention) only matter if you alert on missing sequences/backlog, not just on bad events.
- LLM-assisted triage threat model: treat all log fields as attacker-controlled; prompt injection can rewrite summaries/runbooks unless the model is constrained to retrieval over approved internal context and cannot take actions—LLM output must never be the source-of-truth for evidence.
- Nonce misuse at scale: AES-GCM nonce uniqueness failures happen under retries, concurrency bugs, or state loss; adopting AES-GCM-SIV (RFC 8452) reduces catastrophic misuse risk but still requires key/nonce handling invariants and performance validation.
- Red flag: Degraded-mode “break-glass” that uses shared static admin creds becomes permanent bypass
- Red flag: Running PQC canary and large rewrap jobs together couples CPU/KMS risk unnecessarily
- Anchor: `ingestion_gap_minutes` — Pages when detections are untrustworthy

**Operations / SLOs / Rollout**
- Define explicit SLOs (touchpoints E9–E12): detection freshness p95 (<2 min), ingestion gap rate, TLS handshake p99 (<30 ms) and failure rate by client segment, resumption %, KMS p99/throttle rate, approval latency p95, break-glass rate + post-hoc review completion.
- Page on “missing control inputs”: collector down/backlog > threshold, integrity chain break, or audit log write failures are security incidents because they invalidate downstream conclusions (“no alerts” ≠ “no attack”).
- Rollout strategy: canary hybrid TLS by client fingerprint/region/network path with an immediate kill switch; require negotiated-group telemetry coverage before enforcing policy; rollback criteria include handshake failures, CPU saturation, and resumption collapse.
- Dependency budgets and circuit breakers: KMS and approval systems must be treated as shared reliability dependencies; add backpressure, request hedging limits, and fail-open/closed decisions by tier so a brownout doesn’t become a global outage.
- Game days as a requirement, not a nice-to-have: simulate SIEM/search maintenance, collector gaps, KMS throttling, and approval-service partitions; validate that runbooks preserve auditability and that degraded modes don’t silently expand privilege.
- Policy artifacts that survive audits: tier matrix (data class/action → required controls like hybrid, MPA, audit retention), explicit exception register (owner + expiry + compensating controls), and measurable PQC migration progress (inventory + enabled % per tier).
- Reduce developer friction deliberately: ship default OTel exporters, TLS policy, token/grant enforcement in gateways/sidecars/shared libs; provide CI checks for schema/rule compatibility and a paved path for teams that can’t change application code.

**Interviewer Probes (Staff-level)**
- Probe: How do you detect “silent downgrade” of hybrid TLS at scale, and what do you do when legacy clients break the handshake p99 budget?
- Probe: What telemetry SLOs and paging triggers make “missing data” a first-class incident, and how do you prevent alert fatigue from ingestion-gap paging?
- Probe: Design bounded DEK caching for KMS brownouts—what are the invariants (TTL, size, audit), and which tiers fail closed vs fail open?
- Probe: How do you implement JIT + multi-party approval with a degraded mode that supports P0 response without turning into standing admin?

**Implementation / Code Review / Tests**
- Coding hook: Enforce `event.schema_version` in log normalization; add golden tests that schema changes don’t break detections.
- Coding hook: Add negotiated TLS group + resumption boolean to structured logs; reject logging any raw secrets/URLs; unit test redaction.
- Coding hook: Implement hybrid TLS feature flag with canary targeting (client fingerprint/region) and a hard kill switch; integration-test rollback under elevated handshake failures.
- Coding hook: Build enrichment caches with explicit TTLs, size bounds, and fallback behavior; load-test to prove you didn’t introduce a join storm/backpressure.
- Coding hook: Implement a `revocation_epoch` check in enforcement; test that epoch bump invalidates cached grants within bounded time.
- Coding hook: KMS circuit breaker: cap concurrent KMS calls, exponential backoff, and “serve from cache within TTL” only for allowed tiers; chaos-test brownouts + throttling.
- Coding hook: Audit log writer: append-only semantics + hash chain verification; negative tests for missing/duplicated entries and replayed `grant_id`s.
- Coding hook: LLM triage guardrails: escape/untrust all log fields, constrain retrieval to approved corpora, and disable tool execution; test prompt-injection strings in logs.

## Staff Pivot
- Approach A (tool-first, team-by-team): SIEM rules in a UI, ad hoc crypto choices, standing admin roles; low upfront coordination but inconsistent coverage, weak change control, and incident/audit failures when dependencies wobble.
- Approach B (maximum strictness everywhere): hybrid/PQC on all endpoints, KMS on every read, MPA for every action; “secure on paper” but blows latency/availability, creates exception factories, and incentivizes shadow bypasses during P0s.
- Approach C (tiered platform guardrails with measurable SLOs): detections-as-code + telemetry integrity, hybrid TLS where confidentiality horizon justifies it, envelope encryption with misuse-resistant defaults + bounded caching, JIT/MPA for high-risk actions with signed grants and audited break-glass.
- Decisive trade-off: accept partial coverage early (highest-value data paths + highest-risk actions first) to protect SLOs and credibility; make gaps explicit via inventory + expiring exceptions instead of pretending universal enforcement.
- Operating principle: don’t enforce what you can’t measure and roll back—start with visibility (negotiated TLS group telemetry, ingestion-gap alerting, approval latency metrics), then ratchet policy with canaries and kill switches.
- “What I’d measure weekly” (to drive risk decisions under ambiguity): detection latency p95 + precision, `ingestion_gap_minutes` rate, TLS handshake p99 + failure rate by segment + resumption %, KMS p99 + throttle %, % objects on old KEK + rewrap backlog slope, time-to-access p95 for on-call, break-glass frequency + post-hoc audit completeness.
- Reliability-first security: define tiered fail-open/closed behavior (e.g., allow low-risk reads with cached DEKs within TTL; never allow exports/prod mutations without signed grant), and practice it in game days so incident behavior matches policy.
- Risk acceptance (now vs later): allow LLM summarization with strict guardrails (RAG over approved internal context, redaction, no auto-actions); deploy hybrid TLS first to long-horizon confidentiality customers/paths; expand as compatibility inventory and resumption rates stabilize.
- What I would NOT do: make the approval service or KMS a synchronous global hard dependency for all request paths; it’s tempting for uniformity but it creates cascading outages and forces emergency bypasses that destroy auditability.
- Stakeholder alignment plan: negotiate and publish a tier matrix + paging bar that Product can budget latency against, SRE can budget dependency risk against, Compliance can audit (FIPS/PQC roadmap + WORM retention + two-person control evidence), and SOC can operate with fewer, higher-signal pages.
- Tie-back: Describe a system you owned where “missing data” was the incident—what did you page on?
- Tie-back: Describe a rollout that regressed p99—what were your rollback signals and kill switches?

## Scenario Challenge
- You run a global SaaS where edge TLS terminates ~250k RPS; handshake p99 must stay <30 ms and overall availability is 99.99%, so any crypto/identity change that increases handshake CPU/bytes risks a customer-visible outage.
- Your telemetry volume is ~4 TB/day; detections must meet <2 minutes p95 event→alert, so “more rules” is irrelevant unless ingestion, normalization, and enrichment are engineered like a production streaming system.
- Compliance imposes two deadlines: (a) a PQC migration plan with measurable progress for gov customers in 2 quarters, and (b) two-person control for prod mutations + data exports in 90 days—both require evidence you can show under audit.
- Security assumptions: attackers can record traffic now (store-now-decrypt-later), steal session tokens from endpoints, and compromise an engineer laptop; your controls must reduce blast radius across crypto, session/identity, and privileged ops.
- Reliability constraints: SIEM/search has weekly maintenance (read-side periodically unavailable), KMS has occasional regional brownouts, and the privileged-access approval service must have a degraded mode that doesn’t block P0 response.
- Privacy/compliance constraints: you cannot log raw tokens or sensitive URLs; you still need tamper-evident audit trails retained for 1 year, and approvals/key operations must be attributable without leaking customer content.
- Developer friction constraints: 100+ services, and roughly half can’t change code this half; controls must ship via gateway/sidecar/shared libs and policy (not bespoke changes in every service).
- Migration/back-compat constraints: legacy clients (Java 8, older Android, enterprise middleboxes) may fail hybrid TLS due to ClientHello size/ossification; legacy storage includes AES-CBC + shared keys in parts of the fleet; standing admin roles exist and must be phased out without a flag day.
- Data protection constraint: rewrap/rotation jobs compete for KMS capacity with online traffic; you need an envelope encryption migration plan that won’t trigger KMS throttling or partial ciphertext states during rollback.
- Privileged access constraint: two-person control must cover prod mutations and data exports; enforcement must be backed by phishing-resistant step-up (WebAuthn/FIDO2) and signed, short-lived grants that enforcement points can validate even if the approval service is degraded.
- Incident/on-call twist: you canary hybrid TLS at 10% and see handshake failures + CPU spikes; simultaneously, a rewrap job increases KMS load and you hit throttling; a P0 outage starts and the approval service is partially unreachable—decide what to roll back, what to circuit-break, and what must fail closed vs break-glass.
- Multi-team/leadership twist: Compliance demands “no exceptions,” Product demands “no latency regressions,” SRE demands “no new global hard dependencies,” and SOC demands “fewer pages”—you must drive a tiered decision, success metrics, and an exception register with explicit owners and expirations.
- Hard technical constraint: you must prove audit completeness/tamper evidence for approvals and key ops for 1 year, while not logging raw secrets or sensitive URLs—your audit schema must preserve attribution and verifiability without violating privacy.

**Evaluator Rubric**
- Clearly scopes the problem with an explicit tier model (data classes, action criticality) and ties each tier to concrete controls (hybrid TLS, envelope encryption, MPA/JIT) and explicit fail-open/closed semantics.
- Proposes an architecture that works under developer constraints (gateway/sidecar/shared libs) and avoids creating new global hard dependencies without circuit breakers and error budgets.
- Defines measurable SLOs/error budgets and paging triggers for telemetry freshness, TLS handshake performance/failure by segment, KMS latency/throttling, and approval latency/break-glass usage; treats “missing data” as a security incident.
- Describes a phased rollout plan with canaries, client segmentation, and rollback criteria; avoids coupling high-risk changes (e.g., hybrid TLS rollout + large rewrap batch) and explains how progress is measured for compliance.
- Demonstrates incident-ready thinking for the twist: what to pause, what to roll back, what to circuit-break, and how to keep response unblocked while preserving auditability and limiting privilege expansion.
- Balances compliance with operational reality via evidence artifacts: WORM/hash-chained audit trails, expiring exception register with owners and compensating controls, and a PQC roadmap with measurable progress.
- Treats LLM triage as a constrained UI over immutable evidence (no auto-actions), addresses prompt injection via attacker-controlled log fields, and shows how to reduce SOC toil without hiding risk.
- Shows stakeholder influence: converts “no exceptions / no latency regressions / no dependencies / fewer pages” into an explicit, versioned tier policy with shared metrics and agreed rollback/paging bars.