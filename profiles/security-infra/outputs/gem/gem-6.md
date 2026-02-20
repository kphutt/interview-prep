============================================================
EPISODE 11
============================================================

## Title
**Envelope Encryption: Rotate Access to Petabytes by Re‑wrapping Keys, Not Data** (as-of Feb 2026)

## Hook
- Encrypting bytes is the easy part; **rotating access** (annual/compliance + emergency compromise) is the hard part because rewriting **5 PB** is operationally infeasible inside a 24h response window.
- “Secure-by-default” (KMS unwrap on every read) creates a **p99 latency tax** and makes KMS a **global availability dependency**—an SLO anti-pattern when you’re targeting **99.99%**.
- “Fast-by-default” (caching keys aggressively) is a **risk acceptance** decision: you’re trading residual exposure window vs. customer-visible latency; you need explicit, measurable bounds (TTL/size, invalidation, fail-closed tiers).
- Multi-tenant + **per-tenant CMK** means you’re not just rotating keys—you’re rotating **policy boundaries**: a bug in `kek_id` selection or encryption context can become cross-tenant data exposure.
- Rotation must be safe under ambiguity: you rarely know if a key is compromised at first; you need a design that supports **progressive containment** (disable old KEK usage, rewrap prioritization, audit queries) without stopping the world.
- Operational constraints dominate: KMS regional brownouts + retry storms can cascade into widespread timeouts; the system must have **circuit breakers, backpressure, and clear degraded-mode policy** to protect the data plane.
- Developer friction is the scaling limiter: with **40 services**, per-team crypto is a security and reliability liability; you need standardized metadata, shared libraries, and strict parsing/validation to avoid divergent behavior.
- Auditing every unwrap for **7 years** creates cost and privacy risk; logs become security-critical data that must be access-controlled, minimized, and still useful during incident response.
- Migration/back-compat (“legacy AES-CBC shared key”) forces mixed-mode reads/writes; you must make progress measurable and rollback safe without introducing silent downgrade paths.

## Mental Model
Think of each object as a letter sealed in its own envelope (a per-object DEK encrypts the content). That envelope is then locked in a safe (a KEK wraps the DEK, stored/managed by KMS/HSM). When you change the safe’s combination (rotate KEK), you don’t rewrite the letter—you just move the sealed envelopes to the new safe by re-wrapping the DEKs.

- The “letter” → ciphertext of the object/chunk encrypted with an **AEAD** using a **random per-object DEK**; data re-encryption is avoided during rotation.
- The “envelope” → `{wrapped_dek, kek_id/version}` stored next to the object; `kek_id` is part of the security boundary and must be integrity-protected via metadata validation/AAD binding.
- The “safe” → KMS/HSM-held KEK(s) (including **per-tenant CMK**) that wrap/unwrap DEKs; operationally this introduces dependency budgets, quotas, and on-call failure modes.
- The “changing combination” → rotate KEK version + background **rewrap** job; emergency rotation is prioritization + containment, not a 5 PB rewrite.
- Failure mode mapping: if an attacker gets “safe access” (`kms:Decrypt` or CMK grants) or you reuse a GCM nonce, the envelope doesn’t help—your blast radius becomes “everything that KEK can unwrap,” and incident response shifts to permissions revocation + rewrap completion time.

## Common Trap
- **Red flag:** “Use one AES key for all data” → rotation becomes a petabyte rewrite; compromise becomes company-ending; dev friction spikes because every service must coordinate a global re-encrypt cutover and handle mixed states.
- **Red flag:** “Call KMS decrypt on every read” → p99 latency and cost explode at 250k RPS; KMS brownouts become user-visible outages; on-call toil grows from retry storms and quota paging.
- “Store the plaintext DEK on disk for caching” → looks like a performance win; actually creates durable key material sprawl, complex secure deletion requirements, and audit/compliance failure when hosts are forensically recovered.
- “Rely on storage-provider SSE only” → reduces implementation burden; fails per-tenant isolation/CMK semantics and rotation control; creates stakeholder friction when compliance asks for proof of unwrap auditability or rewrap completion metrics you can’t produce.
- “Skip AAD/encryption context; ciphertext is enough” → enables swap/replay across `{tenant_id, object_id}`; incident response becomes ambiguous because you can’t prove binding; on-call gets noisy with hard-to-triage integrity errors or silent data mixups.
- “Implement crypto independently in each of 40 services” → inconsistent metadata, nonce handling, and error semantics; migration becomes combinatorially hard; security review and production debugging become chronic toil.

## Nitty Gritty
**Protocol / Wire Details**
- Envelope metadata stored alongside each object: `{ciphertext, wrapped_dek, kek_id, kek_version, alg, iv/nonce, aad, created_at, dek_format_version}`; treat `kek_id/version` as security-critical routing input (not “just metadata”).
- For object stores that support headers/metadata: map fields to HTTP-style headers (example names): `X-Enc-Alg`, `X-Enc-KekId`, `X-Enc-KekVer`, `X-Enc-WrappedDEK`, `X-Enc-IV`, `X-Enc-AAD`, `X-Enc-CreatedAt`, `X-Enc-FormatVer`; enforce canonicalization to prevent ambiguity (duplicate headers, mixed case).
- AEAD choice: AES-256-GCM or ChaCha20-Poly1305; enforce algorithm agility only via explicit `alg` allowlist (avoid “accept anything” parsing that becomes downgrade surface during migration).
- Nonce/IV requirements: **unique nonce per (DEK, encryption)**; store nonce next to ciphertext; if chunking, either use a fresh DEK per chunk or derive per-chunk nonces safely (never reuse nonce with same key).
- AAD binding: include `{tenant_id, object_id, object_version, content_type, dek_format_version}` in AAD to prevent swap attacks; ensure services compute AAD identically (shared lib) or decryption will fail in hard-to-debug ways.
- Wrapping call shape (KMS): `Encrypt(KEK, plaintext=DEK, encryption_context={tenant_id, purpose="objectstore", object_id_prefix?...}) -> wrapped_dek`; or `ReEncrypt(old_wrapped_dek, old_kek, new_kek, context) -> new_wrapped_dek` to avoid exposing plaintext DEK.
- Include `kek_id` and `kek_version` in the envelope to support deterministic unwrap routing and rotation progress metrics; avoid “latest” semantics at read time (causes non-determinism and breaks rollback).
- Anchor: `kek_id` — routes unwrap; wrong value breaks isolation.
- Anchor: `encryption_context` — IAM condition boundary; prevents cross-tenant unwrap.
- Anchor: `AAD` — binds ciphertext to tenant/object; stops swap attacks.
- Industry Equivalent: “KMS/HSM” = AWS KMS/CloudHSM, Azure Key Vault HSM, HashiCorp Vault Transit (where supported).

**Data Plane / State / Caching**
- Data read path (steady state): fetch object + envelope → check DEK cache keyed by `(tenant_id, object_id, object_version, kek_id, kek_version)` → if miss, unwrap via KMS → decrypt via AEAD → return plaintext.
- DEK cache design: in-memory only; strict upper bounds (entries + bytes), TTL (e.g., seconds to minutes, driven by risk tolerance), and eviction (LRU + jitter) to prevent synchronized expiry thundering herds.
- Cache invalidation: on rewrap completion for an object (or when `kek_version` changes), the envelope changes; the cache key includes `kek_version` so old entries naturally miss; optionally proactive invalidation by publishing “rewrap done” events for hot objects.
- Cache negative results: carefully—cache “KMS denied” only briefly to reduce repeated failures; avoid caching transient KMS errors long enough to create self-inflicted outage.
- KMS pressure control: client-side rate limits (per process + per tenant), request coalescing (singleflight) per `(wrapped_dek, kek_version)`, and token-bucket quotas to stay under KMS QPS and cost budgets.
- Circuit breaker behavior: open on elevated KMS p99 / error rate; fail strategy must be tiered—e.g., serve from cache if present, otherwise fail closed for writes and for reads requiring fresh unwrap.
- Connection pooling to KMS: bounded pools + timeouts; avoid unbounded retries; include exponential backoff with jitter and max attempt caps to prevent retry storms during brownouts.
- Background rewrap pipeline: scans objects, reads envelope, calls KMS re-encrypt (preferred) or unwrap+wrap (fallback), writes updated `wrapped_dek` + `kek_version` atomically; ensure idempotency and resumability.
- Rewrap prioritization: hot objects/tenants first (reduce cache miss dependency), then long tail; for compromise, prioritize affected CMK tenant(s) and objects on compromised KEK version.
- Mixed-mode migration: reader tries v2 (AEAD + envelope) first; if absent, falls back to legacy (CBC shared key) with explicit metrics and a sunset plan; writer should emit only v2 after a cutover flag per tenant/service.
- Hard constraint reality: you cannot “call KMS for every read” at 250k RPS and +5ms p99; caching + coalescing is mandatory, so risk controls must move to IAM conditions, short TTLs, and rapid rewrap.

**Threats & Failure Modes**
- Explicit threat: attacker obtains `kms:Decrypt` (or CMK grant) for a KEK → envelope encryption does not protect; blast radius equals all DEKs wrapped under that KEK; containment = revoke/disable key usage + rewrap to new KEK + audit.
- Nonce reuse in AES-GCM (same key + nonce) → catastrophic confidentiality/integrity failure; enforce nonce generation centrally; validate nonce length and uniqueness assumptions (e.g., random 96-bit nonce with per-object DEK).
- Swap attack: attacker swaps `{ciphertext, wrapped_dek}` between objects/tenants → prevented by AAD binding and encryption context; without it, you get silent data substitution or confusing auth failures.
- Metadata tampering: modify `kek_id/version` to force unwrap under different key → must be mitigated by strict allowlists, IAM conditions on encryption context, and rejecting unexpected `(tenant_id, kek_id)` combinations.
- Replay/stale envelope: old `wrapped_dek` reintroduced (rollback) → decryption might succeed but violates rotation/compliance; detect via `created_at`/format version, object versioning, and metrics on “objects on old KEK %”.
- KMS brownout failure mode: elevated latency triggers timeouts; naive retries amplify load; without circuit breakers, the entire read fleet can cascade-fail and page SREs across regions.
- Audit log risk: unwrap logs become a map of sensitive operations; must be protected (least privilege, tamper-evident storage), retained 7 years, and scrubbed of plaintext/DEKs; logging too much can violate privacy policies.
- **Red flag:** “Fail open when KMS is slow by skipping decryption checks” → turns reliability mitigation into a data exposure bug; the only safe fail-open is **serving already-decrypted data from bounded in-memory cache** with explicit TTL risk acceptance.
- **Red flag:** “Accept legacy AES-CBC indefinitely during migration” → permanent downgrade path + inconsistent integrity; creates ongoing incident ambiguity and increases on-call toil with dual-stack bugs.
- CMK tenant isolation failure mode: mis-scoped encryption context (missing `tenant_id`) allows a principal with CMK access to unwrap other tenants; enforce mandatory context fields and KMS policy conditions.

**Operations / SLOs / Rollout**
- SLO budgeting: treat KMS as a partial dependency—reads should succeed from cache for hot paths; set explicit targets for DEK cache hit rate to keep crypto overhead within **+5ms p99**.
- Metrics to page on: KMS p99 latency, KMS error rate by code (permission denied vs unavailable), DEK cache hit rate, singleflight wait time, decrypt failure rate (AEAD tag failures), rewrap backlog age, % objects on old KEK, time-to-rewrap for compromise.
- Canary/rollout: ship shared crypto library behind feature flags; enable per-service/per-tenant; canary in a small region/tenant slice; rollback by toggling writer to emit old format only if absolutely necessary (but keep readers dual-stack).
- Backward compatibility: versioned envelope format; strict parsing; reject unknown versions unless explicitly enabled—prevents “accept garbage” vulnerabilities.
- Emergency rotation runbook (compromise): (1) freeze writes or force new KEK on writes, (2) disable old KEK usage (policy) while allowing reads via cache where safe, (3) start prioritized rewrap, (4) audit query for unwraps on compromised key, (5) comms plan for CMK tenants.
- Reliability policy decision: define which tiers fail closed vs serve from cache—e.g., metadata-only reads might proceed; object reads require decrypt; writes should fail closed on inability to wrap (never write plaintext).
- Cost control: batch rewrap KMS calls; amortize unwraps via cache; measure KMS QPS per tenant and set budgets; finance alignment requires showing “cost per 1M reads” under various TTLs.
- Compliance trade-off: “audit every unwrap” at 250k RPS is expensive; minimize fields logged (key IDs, tenant, outcome, latency), sample only where policy allows (often it doesn’t), and separate security audit logs from general app logs with stricter access.
- On-call hygiene: predefine dashboards and “brownout mode” toggles; ensure rate limiting/circuit breakers are centralized in the shared library to avoid 40 teams implementing different retry logic.
- Anchor: `rewrap backlog` — measures rotation progress; drives emergency response.
- Anchor: `DEK cache TTL` — explicit performance vs exposure window knob.

**Interviewer Probes (Staff-level)**
- Probe: How do you set DEK cache TTL/size to meet +5ms p99 while bounding compromise exposure—what metrics and what rollback plan?
- Probe: During a KMS regional brownout, what exact read/write behaviors do you choose (serve-from-cache vs fail-closed), and how do you prevent retry storms across 40 services?
- Probe: How do you design envelope metadata + AAD/encryption-context so cross-tenant swaps and misrouting of `kek_id` are provably prevented?
- Probe: What does “<24h response on key compromise” mean operationally—what steps complete in minutes vs hours, and what do you measure to know you’re done?

**Implementation / Code Review / Tests**
- Coding hook: Reject envelopes with unknown `alg`, unexpected nonce length, or missing mandatory AAD fields; fail closed with explicit error codes.
- Coding hook: Implement canonical AAD serialization (stable field order, encoding, versioning) in the shared library; add golden tests shared across languages.
- Coding hook: Singleflight unwraps by `(tenant_id, wrapped_dek, kek_id, kek_version)` to prevent KMS stampede; load test under 1% cache miss at 250k RPS.
- Coding hook: Circuit breaker unit tests: simulate KMS timeouts and verify (a) no unbounded retries, (b) bounded queueing, (c) correct tiered fail behavior.
- Coding hook: Rewrap job idempotency tests: rerun rewrap on same object and assert envelope remains consistent; handle partial failures without corrupting metadata.
- Coding hook: Migration tests: mixed-mode reader decrypts both legacy CBC and new AEAD; verify no silent downgrade—writer format is controlled only by explicit flags.
- Coding hook: Negative crypto tests: tamper with `ciphertext`, `wrapped_dek`, `kek_id`, and AAD; assert AEAD tag failure or policy rejection (not garbage plaintext).
- Coding hook: Logging tests: ensure audit logs include key IDs/outcomes but never plaintext/DEKs; verify log access controls and retention tagging are applied by pipeline.
- Coding hook: Parser hardening: defend against oversized `wrapped_dek` fields, duplicate headers, and malformed base64; fuzz the envelope decoder.

## Staff Pivot
- Competing approaches under these constraints:
  - A) Storage-provider SSE only: simplest operationally, but limited control over per-tenant CMK semantics, unwrap auditing, and deterministic rewrap progress reporting.
  - B) App-layer encrypt with a static key: fastest and cheapest in the short term, but rotation/compromise becomes a 5 PB rewrite and a catastrophic blast radius.
  - C) **Envelope encryption with KMS-managed KEK + bounded in-memory DEK caching + background rewrap**: more moving parts, but best balance of rotation speed, isolation, and latency.
- Decisive trade-off: choose **C** because it optimizes for what you cannot “buy later”: emergency rotation (<24h) and compromise containment, while meeting **+5ms p99** via cache hit rate + unwrap coalescing; it also converts KMS from a per-read dependency into a **miss-path dependency**.
- Treat caching as a first-class security design: short TTL, in-memory only, bounded size, cache key includes `kek_version`, and explicit “serve-from-cache only” degraded mode—this is risk prioritization under ambiguity, not an accidental implementation detail.
- What I’d measure weekly (and in incident): KMS QPS + p99, cache hit rate, decrypt overhead p99, unwrap failure rate by reason, % objects on old KEK, rewrap backlog age, time-to-rewrap for top N tenants, number of brownout-induced circuit breaker opens, on-call pages attributable to KMS.
- Reliability stance: avoid global hard dependency on KMS by ensuring hot reads succeed from cache; for cold reads, fail closed if unwrap unavailable rather than inventing unsafe fallbacks.
- Policy/compliance stance: enforce least privilege using IAM conditions + encryption context (`tenant_id`, `purpose`), audit unwrap operations with 7-year retention, and lock down audit log access as tightly as KMS access.
- Developer friction reduction: mandate a shared library with strict envelope validation, standardized AAD/context serialization, and centralized retry/circuit-breaker logic; reduce the number of “crypto choices” teams can make.
- Risk acceptance (now vs later): accept short-lived in-memory DEK caching now to hit latency/SLO; defer more complex options (e.g., broader re-encrypt orchestration optimizations) until after baseline correctness + observability are in place.
- What I would NOT do (tempting but wrong): “cache plaintext DEKs on disk to survive restarts” — it converts transient exposure into durable secret sprawl and complicates incident response and compliance.
- Stakeholder alignment plan: Security defines threat model + cache bounds; SRE defines dependency budgets + brownout behavior; Compliance defines audit requirements + rotation SLO; Data Platform owns metadata schema; Finance/Product sign off on KMS cost vs performance with explicit knobs (TTL, rewrap rate) and reporting.
- Tie-back: Describe a time you reduced a global dependency by adding caching + circuit breakers without weakening security.
- Tie-back: Describe how you got compliance and SRE to agree on a concrete rotation SLO and a degraded-mode policy.
- Tie-back: Describe how you ran a mixed-mode migration with measurable progress and a rollback plan.

## Scenario Challenge
- You operate a multi-tenant object store with **5 PB** stored, serving **250k RPS reads / 50k RPS writes**; you have a strict **+5ms p99** crypto overhead budget and must maintain **99.99%** availability.
- Security requirements: encrypt all customer data at rest; support **per-tenant customer-managed keys (CMK)**; annual rotation mandated; emergency compromise response requires **containment + progress within <24h**.
- Reliability constraint: KMS occasionally has **regional brownouts** (latency spikes + intermittent failures); reads must continue safely without turning KMS into a global hard dependency or causing retry storms.
- Privacy/compliance: audit **every unwrap action** with **7-year retention**; logs must not contain plaintext, DEKs, or customer content; audit logs require tight access controls and must be usable during incident investigations.
- Developer friction constraint: **40 services** read/write objects; you must provide a shared library and standardized envelope metadata (headers/fields) rather than allowing per-team crypto implementations.
- Migration constraint: ~50% of data is legacy **AES-CBC with a shared key**; you must migrate online with mixed mode, measurable progress, and no data rewrite wave that blows capacity or SLOs.
- Hard technical constraint that breaks the textbook approach: at 250k RPS, doing KMS unwrap/decrypt on every read is infeasible for latency/cost and creates a global dependency—yet compliance still expects strong controls and auditing.
- Incident/on-call twist: a KMS latency spike causes timeouts; naive retries cascade into elevated error rates across services—what do you circuit-break, what backpressure do you apply, and what tier(s) fail closed vs serve from cache?
- Security incident twist: a tenant reports suspected CMK compromise; you must limit blast radius, prioritize rewrap, and produce audit evidence without violating privacy logging constraints.
- Leadership twist: Finance demands lower KMS cost, Compliance demands stronger controls + CMK isolation, Product demands “no perf regression”; you must propose a phased rollout, caching strategy, rewrap rate plan, and weekly reporting metrics.
- Rollout safety: you must define canarying, rollback strategy, and “mixed-mode” reader/writer behavior so the fleet can upgrade gradually without data loss or silent downgrade paths.
- Operational excellence requirement: define dashboards, paging thresholds, and a runbook that an on-call can execute under pressure (including “brownout mode” toggles and rewrap prioritization).

**Evaluator Rubric**
- Clearly states assumptions and identifies which constraints dominate (p99 +5ms, 99.99%, <24h compromise response, audit retention) and how that shapes architecture.
- Presents an envelope encryption design with correct metadata, AEAD + nonce uniqueness, and binding via AAD/encryption context; explicitly addresses cross-tenant isolation and swap/replay risks.
- Describes a data-plane that remains available during KMS degradation (cache, coalescing, circuit breakers, rate limits) with explicit fail-open/closed policy choices and their risk acceptance rationale.
- Provides an online migration plan from legacy CBC to AEAD envelope with mixed-mode reads, controlled writes, measurable progress, and rollback safety without permanent downgrade.
- Defines concrete observability: metrics, dashboards, paging triggers, and a way to prove rotation/rewrap progress and audit completeness.
- Demonstrates incident response readiness: compromise playbook steps, prioritization logic, stakeholder comms considerations for CMK tenants, and evidence gathering without logging sensitive data.
- Addresses developer friction: shared library invariants, strict parsing/validation, centralized retry logic, and how to prevent 40 divergent implementations.
- Handles stakeholder trade-offs: shows how to align Finance (cost), Compliance (controls/audit), SRE (dependency budgets), and Product (latency) with explicit knobs and weekly reporting.

============================================================
EPISODE 12
============================================================

## Title
Insider Risk: JIT + Multi‑Party Authorization (MPA) Without Breaking On‑Call (Feb 2026)

## Hook
- Standing privileges keep MTTR low, but they turn “one compromised laptop” or “one coerced admin” into full prod compromise + data export, with attribution gaps that make containment and compliance evidence painful.
- MPA sounds simple (“two people approve”), but at 2,000 engineers and 150 rotations it becomes a distributed-systems problem: correctness (separation of duties) under churn, paging, and follow‑the‑sun handoffs.
- JIT moves risk from long-lived keys to an issuance + enforcement pipeline; now your access system is production-critical and must be engineered like a tier‑0 service (multi-region, low tail latency, tested degraded modes).
- Approval latency is not just “slower”; *variance* breaks incident runbooks—on-call can tolerate 60–120s predictable overhead more than a 1–10 minute roulette wheel.
- If “approved” is enforced only in one plane (web console) but not in others (SSH, `kubectl exec`, cloud role assumption), attackers and stressed responders will route through the weakest path; inconsistency creates toil and outages.
- Strong assurance requirements (`acr`/`amr` step-up, device posture) reduce approver ATO/collusion risk, but add friction; the Staff-level job is deciding where friction buys real risk reduction vs just angering on-call.
- Auditing must be both compliance-grade (1-year retention, dual control evidence) and privacy-preserving (no customer payloads); logs that are incomplete or uncorrelatable are operational debt that explodes during incidents.
- Degraded mode determines culture: if the approval service is unreachable, either you block access (outage amplifier) or you allow bypass (permanent backdoor). The only workable answer is a bounded, noisy break-glass path with forced review.
- Rollout safety is a constraint: legacy root SSH keys and long-lived cloud keys exist; if you break automation or incident playbooks, you’ll get “temporary” standing-access exceptions that never expire.

## Mental Model
Two-person control on a submarine: one person can start the launch sequence, but cannot complete it alone; an independent operator must also turn a key, and the system records exactly who did what. JIT is a key that only works for a short window; MPA is requiring an independent second key-turn. The engineering challenge is making those key-turns fast and reliable during incidents while preventing duplication (self-approval), forgery (unbound approvals), and bypass (alternate access paths).

- The first key-turn maps to creating a structured *request record* (`resource`, `role`, `reason`, `duration`, `ticket_id`) that becomes the audit and enforcement root.
- The second key-turn maps to an independent approver producing a *signed approval artifact* that enforcement points can verify without trusting the requester.
- The “key expires” maps to short-lived SSH certs / OIDC tokens with tight `valid_before`/`exp`, plus constraints like `source-address` and required step-up (`acr`/`amr`).
- The submarine launch log maps to tamper-evident audit trails that correlate `request_id → approvals → issued creds → enforcement events` for incident response and compliance.
- Adversarial mapping: if both keys live in the same pocket (requester can approve, or approvals don’t require strong step-up), a single compromised account collapses MPA into single-party control.

## Common Trap
- **Junior approach:** “We trust admins; background checks are enough.” **Why it fails at scale:** ATO, coercion, and human error are probabilistic certainties across large orgs. **Friction/toil risk:** you pay later via longer IR, ambiguous root cause, and repeated “who touched prod?” investigations that pull in multiple teams.
- **Junior approach:** “Require approvals for everything, always.” **Why it fails at scale:** approval queues become the new global lock; responders optimize for speed by bypassing controls. **Friction/toil risk:** you create a shadow-access culture (shared secrets, backchannel group adds) and inject tail latency into incident response.
- **Red flag:** “Approvals happen in chat (‘LGTM’, emoji) not cryptographically bound to a specific `request_id`/`resource`.” **Why it fails at scale:** you can’t prove what was approved vs executed; approvals become replayable and non-auditable. **Friction/toil risk:** post-incident compliance becomes manual log archaeology and blocks operational learning.
- **Red flag:** “MPA is implemented only in the web console; SSH/kubectl paths still accept standing keys.” **Why it fails at scale:** security is only as strong as the weakest enforcement point. **Friction/toil risk:** inconsistent runbooks and wasted on-call time figuring out which path works under pressure.
- **Red flag:** “Break-glass is a shared root key / wiki secret.” **Why it fails at scale:** it becomes the default access path and is impossible to contain if leaked. **Friction/toil risk:** constant key rotations, unclear accountability, and recurring incidents driven by uncontrolled access.
- **Junior approach:** “Make tokens ultra-short (e.g., 5 minutes) to be secure.” **Why it fails at scale:** clock skew, issuance flakiness, and step-up prompts explode; automation becomes brittle. **Friction/toil risk:** responders re-mint creds mid-mitigation and start lobbying for permanent exemptions to meet MTTR.

## Nitty Gritty

**Protocol / Wire Details**
- SSH JIT: issue OpenSSH user certificates of type `ssh-ed25519-cert-v01@openssh.com` signed by an internal CA; encode `key_id` as `request_id:grant_id` and set `valid_after/valid_before` to 10–60 minutes (shorter for break-glass).
- Constrain SSH certs with critical options: `source-address=<corp egress CIDR>` to reduce reuse from stolen laptops; `force-command=<session-wrapper>` to ensure consistent server-side enforcement and metadata capture.
- Keep SSH principals policy-shaped (not user-shaped): `principals=["prod-mutate-k8s", "prod-debug-readonly", "data-export"]` so enforcement maps to action categories and doesn’t require bespoke per-user configuration.
- Web/API JIT: mint short-lived OAuth/OIDC access tokens; enforcement checks `Authorization: Bearer <token>` plus claims `iss`, `aud`, `sub`, `exp`, `nbf`, `iat`, `jti`, and privilege/role scopes derived from the approved grant.
- Assurance gating: require `acr`/`amr` to meet the action’s policy (e.g., step-up requiring WebAuthn user verification); gateways reject validly-signed tokens that lack required assurance for high-risk actions.
- Request record schema (stored server-side, referenced everywhere): `{ "request_id", "resource", "role", "reason", "duration_seconds", "ticket_id", "requester", "created_at" }`; treat `reason`/`ticket_id` as required for privileged actions to keep audit reviews actionable.
- Approval artifact as an immutable signed blob (often JWT-shaped): `{ request_id, grant_id, approvers[], policy_version, not_before, not_after, constraints{resource, role, source_ip, max_actions} }` signed so enforcement can verify without online calls.
- Anchor: request_id — Correlates approvals, credentials, and audit events.
- Anchor: acr/amr — Enforces step-up; reduces approver/requester ATO impact.

**Data Plane / State / Caching**
- Cache approver eligibility (group membership + on-call rotation) with short TTL (e.g., 30–120s) to bound p95 latency; require push invalidation on termination/role change to prevent stale privilege.
- Termination/role-change kill switch: publish an `entitlement_epoch` bump; enforcement points deny if a presented grant was minted under an older epoch than currently active for the subject or organization.
- Cache active JIT grants at enforcement points keyed by `grant_id` until expiry; validate `not_before/not_after` locally to avoid synchronous dependency on central services.
- Emergency revocation: maintain `revocation_epoch` (global or per-resource) that enforcement points consult; bumping it invalidates cached grants without enumerating them.
- Enforce context binding: a grant for `resource="prod-k8s"` and `role="prod-mutate"` must not be accepted by data-export endpoints even if signature is valid; require exact `aud` and `resource` match.
- Multi-region considerations: replicate policy keys/epochs regionally; design conservative behavior under partitions (deny normal grants if freshness is uncertain; allow only bounded break-glass with audit noise).
- Anchor: grant_id — Stable handle for caching, revocation, and debugging.

**Threats & Failure Modes**
- Collusion / compromised approver account: require step-up for approval actions (WebAuthn UV), device posture checks for approvers, and out-of-band notifications for high-risk approvals to reduce silent rubber-stamping.
- Separation of duties: enforce `requester != approver`; for critical actions require approver independence (different role/team) and sometimes 2 approvals; encode in policy evaluation, not just UI.
- Stale entitlements: cached on-call/HR data can over-grant after org changes; mitigate with short TTL + push invalidation + “deny if cache age > bound” at enforcement points.
- “Approval system down” failure mode: if normal path blocks, engineers will seek permanent bypass; require a degraded mode that’s faster than workarounds but bounded (very short TTL), noisy (paging), and review-triggering (auto-ticket).
- Audit gaps: missing `request_id`/`grant_id` correlation breaks IR and compliance evidence; treat missing logs as a production defect with alerts and ownership.
- Red flag: “Approver identity checked only during approval UI flow, not embedded in the signed grant.” Breaks non-repudiation and enables substitution/replay.
- Red flag: “Break-glass issues the same TTL/scopes as normal access, just skipping approval.” Converts emergency access into an invisible permanent bypass.
- Anchor: revocation_epoch — Fast global kill switch for cached grants.

**Operations / SLOs / Rollout**
- Access SLOs: track `time_to_access` p50/p95 (on-call separately), approval success rate, denial breakdown (policy vs system), and “system-caused denial” error budget; page when p95 blows the 5-minute constraint.
- Hot-path reliability: enforcement points must validate signed grants locally and avoid synchronous IdP/approval calls on every privileged request (especially during major outages).
- Break-glass operations: issue 15-minute grants, page Security + duty manager immediately, and auto-create an audit/postmortem ticket; force a structured reason referencing the incident.
- Tamper-evident auditing: append-only logs capturing who requested, who approved, what was accessed, when, where (enforcement point), and outcome; retain 1 year; explicitly avoid customer payload logging (log identifiers/counts, not data).
- Alerting on integrity: missing audit events, enforcement points that stop emitting logs, or actions outside the grant window should page as “control failure,” not just be dashboard noise.
- Exception control: every exception has owner + expiry; measure exception volume/age and treat “exceptions > break-glass” as a control anti-pattern that needs leadership intervention.
- Anchor: break-glass — Short-lived, loud access that forces follow-up.

**Interviewer Probes (Staff-level)**
- Probe: How do bastions/gateways enforce MPA if the approval service or IdP is unreachable (offline-verifiable artifacts, cache freshness, revocation)?
- Probe: What does your privilege taxonomy look like, and how do you prevent it from becoming unmaintainable policy sprawl that on-call can’t reason about?
- Probe: How do you mitigate “compromised approver rubber-stamps” without making approvals unusably slow (step-up, device posture, notifications)?
- Probe: Which metrics detect bypass culture early (exception creep, break-glass rate, out-of-band access paths), and what actions do you take when they regress?

**Implementation / Code Review / Tests**
- Coding hook: Enforce invariants `requester != approver` and (if 2 approvals) `approver1 != approver2`; verify independence constraints in policy evaluation, not only UI.
- Coding hook: Validate `duration_seconds` against policy maxima per action category; reject missing `reason`/`ticket_id` for privileged roles; negative tests for boundary values.
- Coding hook: Token claim validation: strict checking of `aud/iss/sub/exp/nbf/iat/jti` plus required `acr/amr`; include clock-skew tolerance tests and “weak assurance” rejection tests.
- Coding hook: SSH cert issuance tests: verify `valid_before-valid_after` bounds; ensure required critical options (`source-address`, `force-command`) are present; reject if principals are not in an allowlist.
- Coding hook: Replay protection: bounded replay cache keyed by `jti`/`grant_id`; test duplicate approval submissions, concurrent approvals, and idempotency semantics.
- Coding hook: Revocation correctness: bump `revocation_epoch` and assert cached grants are denied within defined propagation bounds; test partial region failure and stale-cache behavior.
- Coding hook: Audit completeness tests: for every privileged enforcement decision, assert an audit record exists with `request_id`, `grant_id`, enforcement point ID, and decision; test that customer payload fields are redacted by default.
- Coding hook: Degraded-mode chaos tests: simulate approval service outage; confirm only break-glass succeeds and that it triggers paging + auto-ticket + shorter TTL.

## Staff Pivot
- Evaluate competing models explicitly:
  - **A)** Standing admin roles + quarterly reviews: lowest friction, highest insider/ATO blast radius, weakest attribution.
  - **B)** JIT but single-party approval/self-approval: reduces standing exposure, still collapses under single compromised account or coercion.
  - **C)** JIT + MPA + audited break-glass: strongest for high-risk actions, but adds latency and creates a new reliability-critical service.
- Choose **C** for high-risk actions (prod mutations, data exports, key disables, break-glass) and allow a lighter **B-tier** for low-risk debugging (read-only introspection) to protect MTTR.
- Decisive trade-off: accept small, **predictable** access latency to buy reduced blast radius + strong attribution; unpredictability (tail latency, flaky approvals) is worse than modest overhead because it breaks incident response muscle memory.
- Architecture argument to meet constraints: use offline-verifiable signed grants and local enforcement caches so access decisions don’t require a live centralized call path during outages.
- Risk prioritization under ambiguity: start where expected loss is highest (data export, production mutation paths) and defer less critical hardening until workflow adoption is stable—otherwise you’ll ship a perfect policy nobody uses.
- What I’d measure: `time_to_access` p50/p95 (on-call vs non), approval latency and variance, approval failure rate by cause, break-glass frequency/duration, % privileged actions covered by MPA, exception count/age, and audit correlation completeness.
- On-call/SRE reality: treat the access system as tier‑0 with its own SLO/error budget; if it’s unreliable you are directly increasing MTTR and risking availability regressions.
- Stakeholder alignment: co-author a tiered policy matrix with SRE (speed/MTTR), Compliance (dual control evidence), Security (blast radius reduction), and Product (availability); define what qualifies for break-glass and the enforcement for after-the-fact review.
- Policy/compliance trade-off: keep 1-year tamper-evident metadata logs and explicit separation-of-duties evidence, while forbidding customer payload logging to stay within privacy boundaries and reduce sensitive log handling.
- Risk acceptance: allow break-glass for true P0s with strict TTL + immediate paging + mandatory follow-up; do not accept “temporary standing access” because it becomes the default and is rarely removed.
- What I would NOT do: disable MPA during incidents or grant permanent on-call admin “for speed”—it’s tempting, but it converts rare emergency risk into continuous high-privilege exposure.
- Tie-back: Describe how you used p95 latency + error budgets to drive a security control rollout.
- Tie-back: Describe mechanisms you used to prevent exception processes from becoming the default access path.

## Scenario Challenge
- You have **2,000 engineers** and **150 on-call rotations**; responders must reach prod within **5 minutes p95** during incidents while maintaining **99.99%** platform SLO.
- Security constraint: eliminate standing admin roles; require **multi-party approval** for prod mutations and data exports; assume some engineer laptops will be compromised.
- Reliability constraint: the access system must be **multi-region** and must function during major outages; it cannot depend on a **single IdP call-path** at request time.
- Hard technical constraint: enforcement points (SSH bastions, K8s admission for `kubectl exec`/`port-forward`, API gateways, cloud role assumption) must make allow/deny decisions even when central services are unreachable—“just call the approval service” is not an option.
- Privacy/compliance: keep **1-year auditable logs** of privileged access and approvals without logging customer payloads; meet SOX/PCI-style dual control expectations for sensitive systems.
- Developer friction: engineers use SSH, kubectl, and web consoles; you need one coherent JIT workflow (CLI/SDK + minimal retraining) or people will create backchannels.
- Migration/back-compat constraint: legacy root SSH keys and long-lived cloud access keys exist; phase out over **6 months** without breaking automation and scheduled jobs.
- Incident/on-call twist: a P0 outage hits and the approval service is unreachable; on-call needs immediate access—design break-glass that is fast, bounded, noisy, and doesn’t create a permanent bypass culture.
- Multi-team/leadership twist: SRE leadership fears slowed MTTR, compliance demands strict dual control, security demands “no standing access,” product wants faster deployments—propose tiered controls, degraded modes, and success metrics everyone can sign.
- Operational integrity twist: approvals are being rubber-stamped under pressure—define how you detect this via metrics/logs and how you correct it without exploding on-call toil.
- Rollout safety twist: an enforcement point starts denying valid access due to clock skew or stale caches—explain how you prevent a cascading outage and avoid a rollback to standing access.
- Auditability twist: you discover gaps where privileged actions lack `request_id` correlation—describe how your system surfaces, alerts, and remediates this as a control failure.

**Evaluator Rubric**
- Shows explicit assumptions and a tiered privilege taxonomy mapping actions → approvals → TTL → logging, avoiding unmaintainable policy sprawl.
- Designs offline-verifiable enforcement (signed grant artifacts, local validation, revocation epochs, cache freshness bounds) and handles partitions/multi-region failure modes concretely.
- Prioritizes risk under ambiguity (what must be MPA immediately vs what can be lighter-weight) while protecting MTTR and reducing bypass incentives.
- Defines SLOs/metrics and operational hooks (paging triggers, dashboards, audit gap alerts) and treats the access system as a production service with error budgets and incident playbooks.
- Provides a degraded-mode/break-glass plan that is bounded (short TTL), loud (paging + auto-ticket), reviewable (forced follow-up), and culturally resistant to becoming the default.
- Addresses privacy/compliance explicitly (metadata-only logs, retention, separation of duties evidence) without expanding customer data handling footprint.
- Includes a migration/rollout plan with canary/rollback safety, automation compatibility strategy, and exception governance (owner + expiry + visibility).
- Demonstrates stakeholder influence by translating trade-offs into SRE/Product/Compliance/Security terms and proposing alignment mechanisms (policy matrix, exception process, success criteria).