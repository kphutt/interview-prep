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

## L4 Trap
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