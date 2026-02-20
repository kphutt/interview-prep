## Title
Detection Engineering: Detections‑as‑Code with mTLS Telemetry, SLOs, and On‑Call‑Safe Paging

## Hook
- You need identity- and infra-aware detections (principal, device, service, IP, API key) to stop kill-chain moves, but the inputs are messy: 60 services emit inconsistent JSON/text logs, schema drift is constant, and “just parse it” becomes an unowned reliability problem.
- “More alerts” increases nominal coverage but collapses *effective* coverage: as page volume rises, SOC/on-call response times degrade, suppressions grow ad hoc, and true positives get buried behind routine 403s/exceptions.
- Detection is a **data product** with SLOs (freshness, completeness, precision), yet most orgs treat it as “some SIEM queries” with no owner, no release discipline, and no measurable reliability envelope.
- Security wants rapid iteration on emerging attacker behaviors; SRE wants change control and predictable blast radius; without staged rollout + rollback, a single rule push can page-storm the org and erode trust in the entire pipeline.
- Low-latency requirements (e.g., 2 minutes p95 event→alert) collide with reality: ingestion backpressure, Kafka lag, batchy ETL, and weekly maintenance windows in search/SIEM backends; if you don’t design for late data, you either miss incidents or alert too late to matter.
- Telemetry must be authenticated and tamper-evident (mTLS, integrity validation), but tightening transport/auth often increases developer friction (agent bootstrap, cert rotation, breaking legacy shippers) and can reduce coverage if rollout is not managed.
- High-signal detections require context (asset ownership, service tier, user group, ASN), but naïve enrichment via hot-path joins to inventory/LDAP turns every detection into a dependency on brittle, privacy-sensitive systems.
- Privacy/compliance constraints (no full URLs/query strings/payloads; strict access auditing; retention caps) remove “easy” forensic context, so you must design schemas and runbooks that enable <10-minute triage without hoarding sensitive data.
- The Staff-level tension: ship high-precision behavioral detections quickly **without** creating a fragile, expensive, always-paging dependency that the business quietly learns to ignore.

## Mental Model
Good detections resemble airport security: you don’t try to recognize every bad actor’s face; you look for behavior that is wrong *for the context*—wrong passenger flow, wrong time, wrong tool, wrong gate. The objective is interrupting attacker progress (credential abuse, lateral movement, data staging/exfil), not producing maximal “suspicious event” volume. The success metric is operational: the right small number of alerts that get acted on quickly and correctly, even when parts of the system are degraded.

- “Boarding pass + itinerary” → stable identity context in telemetry (`user.id`, `service.account`, `device_id`, `api_key_id`) so behavior can be judged relative to *who/what* is acting, not just the raw event.
- “Checkpoints with calibrated sensitivity” → a paging bar + SLO-backed precision targets; anything below the bar becomes tickets/dashboards, not pages, to protect on-call effectiveness.
- “Secondary screening with more context” → enrichment (owner/tier, group membership, ASN) and correlation windows to turn weak signals into actionable incidents without exploding page volume.
- “Cameras down / guards diverted” → first-class ingestion-gap detection; adversaries kill agents/block egress and pipelines drop under backpressure—if you don’t alert on missing telemetry, you’re optimizing a detector that may be blind.

## Common Trap
- Red flag: **Junior approach:** alert on raw counts of failed logins/403s/exceptions; **fails at scale:** baseline is dominated by bots, retries, misconfigs, and deploy noise, so precision collapses; **toil/friction:** SOC pages become “ignore by default,” app teams get dragged into constant false-positive triage and start sampling/logging less, reducing true coverage.
- Red flag: **Junior approach:** write/modify detections directly in the SIEM UI; **fails at scale:** no versioning, code review, tests, or reproducible rollback—schema changes and parser tweaks silently break rules; **toil/friction:** on-call can’t bisect regressions, audit/compliance can’t trace changes, and every fix becomes a high-risk manual operation during incidents.
- Red flag: **Junior approach:** enrich in-rule by calling LDAP/inventory/asset DB on the hot path; **fails at scale:** introduces latency spikes and hard dependencies, plus privacy boundary crossings; **toil/friction:** outages in enrichment systems disable detections or cascade failures, and developers/SREs get paged for “security pipeline broke prod dependency.”
- **Junior approach:** assume ingestion time ≈ event time and build strict 5–10 minute windows; **fails at scale:** backpressure, retries, and maintenance create out-of-order/late data, so detections either miss the event or fire in storms when backlog drains; **toil/friction:** brittle windows cause recurring “why did it page now?” investigations and lead to overbroad suppressions.
- **Junior approach:** page on every match and “we’ll suppress later”; **fails at scale:** paging storms train responders to mute alerts, and the suppression logic accretes without governance; **toil/friction:** responders spend time managing alert plumbing instead of incidents, and reliability risk rises as emergency silences become the norm.
- **Junior approach:** optimize for “coverage count” by cloning near-duplicate rules across services; **fails at scale:** inconsistent semantics and drift multiply maintenance, and each rule becomes a schema-coupled snowflake; **toil/friction:** developers lose confidence in requirements (“which field is right?”), and security spends cycles on rule hygiene instead of new threat coverage.

## Nitty Gritty
**Protocol / Wire Details**
- Telemetry transport: OTLP over gRPC on HTTP/2; require TLS 1.3 with ALPN `h2` to prevent downgrade to plaintext collectors.
- mTLS mechanics: client certificate auth where the collector validates the agent cert chain + SAN (agent/workload identity) and enforces that identity→tenant/environment mapping; avoid “shared collector token” patterns that enable spoofing.
- Concrete crypto knobs: prefer ECDHE key exchange (X25519 or P‑256) with AEAD cipher suites (e.g., `TLS_AES_128_GCM_SHA256`); signatures via ECDSA P‑256 or RSA‑PSS—opt for short-lived certs over revocation checks to reduce handshake latency/toil.
- Collector hardening: enforce max message size, decompression limits, and gRPC deadlines/timeouts to avoid a single misbehaving agent causing backpressure and dropping high-value events.
- Event envelope: normalize to a stable schema (ECS/OpenTelemetry-style) with fields like `event.category`, `event.type`, `user.id`, `source.ip`, `http.request.method`, `dns.question.name`, `process.parent.name`; schema consistency is an availability dependency for detections.
- Audit log integrity validation: where available (e.g., CloudTrail log file integrity), verify SHA‑256 hash chaining across delivered log files + provider signatures; alert on broken chains, missing sequence/time gaps, and signature failures as “possible tampering or pipeline loss.”
- Anchor: mTLS agent identity — prevents spoofed telemetry poisoning detections.

**Data Plane / State / Caching**
- Correlation at scale: use event-time windowed aggregations (with watermarks) for patterns like `count_distinct(device_id) > N in 10m`, impossible travel, rare parent→child process; keep state keyed by `(principal_id, host_id, api_key_id)` to bound fanout and preserve identity context.
- Stateful implementation detail: use a streaming engine with an embedded state store; define state TTLs aligned to detection windows + late-data tolerance to avoid unbounded growth and surprise memory/cost blowups.
- Enrichment cache: cache asset/identity lookups (host→service owner/tier, user→group, IP→ASN) with TTL in minutes; include negative caching to avoid thundering herds on “unknown host” and to keep latency predictable.
- Cache invalidation strategy: allow async refresh on “asset changed” events and cap staleness via TTL; record `enrichment.version` in the alert for post-incident explainability (“decision used inventory snapshot vX”).
- Dedup/suppression cache: key by `(rule_id, entity_id, time_bucket)` with TTL (e.g., 30–120m) to emit one page + rollup details; store `first_seen`, `last_seen`, and `count` to preserve incident context without paging storms.
- Replay/out-of-order handling: design idempotence keys (e.g., `event.id` or `(source, seqno, timestamp)`) and a replay window so replays don’t inflate counters and trigger false exfil/ATO spikes.
- Rule performance: avoid hot-path joins on massive tables; precompute cheap features (DNS entropy score, eTLD+1 extraction) and store as event fields so detection evaluation is O(1) per event.
- Anchor: Telemetry contract — schema stability is detection availability.
- Anchor: Dedup key — prevents paging storms while preserving incident counts.

**Threats & Failure Modes**
- Adversary action: kill/disable EDR or log shipper, block egress to collectors, or poison logs; treat “telemetry stopped” as a detection category with its own paging bar and containment runbook.
- Pipeline failure: backpressure/drop policies in agents/collectors silently lose events; require explicit counters for dropped events and “ingestion gap” alerts (per service/collector) to avoid false confidence.
- Red flag: assuming “provider audit logs are complete by default” fails—without integrity verification and gap detection, you can’t distinguish “no bad activity” from “no data,” creating systemic blind spots during real incidents.
- Red flag: allowing unauthenticated/weakly authenticated log ingestion (shared API tokens, no mTLS) enables spoofing that can both hide attacker activity and generate decoy pages that burn on-call time.
- Schema drift failure mode: field renames/types change (`user.id` becomes `user.email`, IP becomes string/array), causing rules to silently stop matching or match everything; you need schema conformance checks and break-glass rollback.
- Privacy/control constraints: minimize PII (no full URLs/query strings/payloads) and enforce least-privilege access to raw events; audit rule changes and alert access to satisfy compliance without blocking incident response.
- Anchor: Ingestion gap SLI — detects silent telemetry loss and tampering.

**Operations / SLOs / Rollout**
- Define detection SLIs/SLOs like a service: freshness (event→available), completeness (expected events received), precision (TP/(TP+FP) for paging rules), and latency (event→alert p95); tie them to on-call error budgets.
- Rollout discipline: feature-flag detections with stages—dry-run (count would-have-fired), canary (limited scope/entities), then paging; predefine rollback triggers (precision drop, page rate spike, latency regression).
- Maintenance windows: if the SIEM/search backend is periodically unavailable, buffer in the streaming layer (durable queue) and decide policy for “late alerts” (e.g., page only if still actionable; otherwise ticket + dashboard + retro review).
- Paging bar governance: only rules with an owner, a runbook, and measured precision/SNR can page; everything else is ticketed or dashboards to preserve responder trust and manage risk explicitly.
- Triage readiness: every paging rule includes “why bad,” “validate in <10 minutes,” “containment,” and “known false positives,” plus links to the exact fields used in the decision (so responders aren’t hunting in raw logs).
- Cost/latency trade-offs: precompute/enrich once, cache aggressively, and avoid per-event remote calls; measure $/TB and p95 latency to prevent “detection” from becoming the top infra cost driver.
- Access control: restrict who can change detections-as-code via CODEOWNERS/approvals; log and audit rule deployments as security-relevant changes (incident forensics needs to answer “did we change the detector?”).
- Anchor: Paging bar — protects on-call health while scaling coverage.

**Interviewer Probes (Staff-level)**
- Probe: How do you set and enforce SLOs for detection freshness/completeness/precision when producers (60 services) don’t share reliability goals?
- Probe: What’s your design for late/out-of-order data so windowed detections remain correct during Kafka lag and backend maintenance?
- Probe: How do you implement suppression/dedup so you reduce pages *without* hiding distinct incidents (e.g., multiple victims, multiple API keys)?
- Probe: How would you validate and operationalize audit log integrity (hash chaining/signatures) and define escalation for “possible log tampering vs pipeline drop”?

**Implementation / Code Review / Tests**
- Coding hook: Add schema conformance tests in CI that validate required fields/types (`user.id` string, `source.ip` IP) and fail builds on breaking changes; ship a compatibility shim only with explicit owner sign-off.
- Coding hook: Compile Sigma-style YAML to the target query/stream processor with deterministic outputs; unit-test compilation with golden files to prevent “minor edit changed semantics” regressions.
- Coding hook: Add negative tests for high-noise inputs (deploy spikes, health checks, known bots) to ensure rules don’t page on expected baseline behavior.
- Coding hook: Property-test dedup/suppression cache correctness: idempotence under retries, TTL expiry behavior, and “one page + rollup” invariants keyed by `(rule_id, entity, bucket)`.
- Coding hook: Implement replay protection using `event.id` (or stable composite key) with a bounded replay window; test that replays don’t increase distinct counts or trigger exfil thresholds.
- Coding hook: Add performance tests that simulate 3 TB/day throughput; fail CI if rule evaluation adds hot joins or pushes p95 latency beyond budget.
- Coding hook: Canary safety tests: in dry-run mode, emit “would have paged” metrics and validate rollback triggers fire before paging is enabled; include an emergency kill switch.
- Coding hook: Parser hardening tests for legacy text logs: fuzz key/value extraction, enforce max field lengths, and verify malformed lines don’t crash the pipeline or poison downstream schema.

## Staff Pivot
- Approach A: SIEM UI queries optimize for speed-to-first-alert but are operationally brittle (no review/tests/rollback) and don’t scale with schema churn or multiple teams contributing rules.
- Approach B: detections-as-code + CI + staged rollout treats detection like software (versioned, reviewed, tested, revertible) and aligns with SRE-style reliability, but requires upfront investment in tooling and governance.
- Approach C: “ML anomaly detection for everything” can surface unknown patterns, but without strong baselines + explainability it tends to be high-FP and hard to operationalize under paging constraints.
- I’d pick **B** as the backbone: deterministic, reviewable detectors with explicit context requirements and runbooks; use targeted ML/heuristics only as enrichment (risk scoring, prioritization), not as the only gate for paging.
- Decisive trade-off: prioritize **precision + operational safety** over maximal early coverage; in practice, responders act on a small number of high-confidence alerts faster than a broad set of low-signal alerts they’ve learned to ignore.
- Measurement plan (to keep ambiguity honest): MTTD, event→alert p95 latency, alert precision for paging rules, alert→incident conversion, ingestion gap rate, dropped-event counters, page volume per on-call shift, and enrichment cache hit rate (proxy for dependency risk/cost).
- Risk acceptance (explicit): tolerate uncovered low-signal TTPs for a quarter if that avoids alert fatigue and protects pipeline reliability; track them as backlog with required telemetry/precision prerequisites.
- Stakeholder alignment: create a shared schema contract and “paging bar” process with SOC (triage needs), SRE (pipeline SLOs/error budgets), app teams (instrumentation SDK + conformance), and Privacy/Legal (PII minimization + access auditing) so constraints are negotiated once, not per-incident.
- Operational excellence: define ownership for each paging rule (primary + secondary), require runbooks, and enforce staged rollout; treat “detection pipeline degradation” as an incident with its own playbook and comms.
- What I would NOT do: declare victory by shipping dozens of UI-only SIEM alerts or blanket ML anomalies—tempting because it looks like progress, but it externalizes cost to on-call and creates invisible reliability debt.
- Tie-back: Describe a time you had to set a paging threshold (precision/SNR) under ambiguous data quality.
- Tie-back: Describe how you handled stakeholder conflict (SOC vs SRE vs Privacy) on logging/enrichment.

## Scenario Challenge
- You ingest **3 TB/day** across **60 services**; leadership wants “detect account takeover (ATO) + data exfil within **5 minutes**,” with detections firing **≤2 minutes p95** from the triggering event.
- Detection pipeline availability target is **99.9%**; define what “available” means (freshness/completeness SLIs), because “pipeline up” is meaningless if ingestion is lagging or dropping.
- The SIEM/search backend has weekly maintenance windows; you must buffer and still meet detection latency SLO for high-severity rules, plus define policy for “late alerts” when the backend returns.
- Security constraint: attacker may kill agents or block egress; telemetry gaps must be first-class signals with their own thresholds, paging policy, and containment guidance.
- Transport/auth constraint: logs must be shipped over **TLS/mTLS**; you need a plan for agent identity, cert rotation, and what happens when a cert expires at 2am (operational reality, not theory).
- Privacy/compliance constraint: you **cannot store full URLs/query strings or raw payloads**; retention is **180 days** with strict access auditing—design detections and runbooks that remain actionable with minimized fields.
- Developer friction constraint: **20 teams** emit inconsistent logs; you need a golden schema + SDK and automated conformance checks (CI gates/metrics), not bespoke per-team rule exceptions.
- Migration constraint: legacy services emit unstructured text logs; you must onboard them without a flag day while still producing useful normalized events and keeping old rules working (versioned schemas/parsers).
- Hard technical constraint: you cannot rely on expensive hot-path joins (inventory/LDAP) at 3 TB/day while meeting 2-minute p95; enrichment must be cached/precomputed with bounded staleness and explicit failure behavior.
- Incident twist: Kafka/stream backlog spikes and event lag grows to **30 minutes**; window-based detections stop behaving—what signals do you shed/degrade, and what do you page on to avoid both misses and storms?
- Operational twist: a new high-severity rule rollout causes a page-rate spike; what kill-switch/rollback mechanisms exist, and how do you preserve learning without burning on-call?
- Multi-team/policy twist: CISO demands “more detections,” SOC demands “more context,” SRE demands “fewer pages,” Privacy demands “less data”—propose a prioritization rubric and a weekly metrics report that makes trade-offs explicit and auditable.
- Compliance/control constraint: rule changes and raw event access must be auditable; define who can deploy paging rules, how approvals work, and how you prevent bypass during emergencies while still enabling rapid response.

**Evaluator Rubric**
- Clear assumptions and explicit definitions of SLIs/SLOs (freshness, completeness, precision, latency) with error-budget thinking and paging implications.
- Architecture that separates concerns: ingestion/authenticated transport, normalization/schema contract, enrichment/caching, correlation/state, and alerting outputs—with explicit failure behavior for each layer.
- A late-data/backpressure strategy (watermarks, buffering, degradation modes) that preserves correctness and responder trust during maintenance and lag spikes.
- Operational rollout plan: dry-run → canary → paging, rollback triggers, dedup/suppression design, and “pipeline health” alerting (including ingestion gaps) with runbooks.
- Privacy/compliance-aware design that minimizes sensitive data while enabling <10-minute triage, plus access auditing and least-privilege controls for both data and rule changes.
- A prioritization rubric that balances coverage vs precision vs toil (including what gets paged vs ticketed), and a metrics report that aligns Security/SOC/SRE/Privacy around the same scoreboard.
- Incident response readiness: how responders validate alerts quickly, what containment steps exist, and how to communicate during partial telemetry loss or suspected tampering.
- Tie-back: Explain a concrete strategy you’ve used to prevent alert fatigue while increasing true incident detection.