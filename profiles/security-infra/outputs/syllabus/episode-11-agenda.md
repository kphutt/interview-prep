**Episode 11 — Envelope Encryption: Rotate Access to Petabytes by Re‑wrapping Keys, Not Data**

2) **The Hook (The core problem/tension).**
- Encrypting data is easy; **rotating keys at scale** without downtime is the hard part.  
- Calling KMS on every read is secure-but-slow; caching keys is fast-but-risky.  
- Staff-level challenge: design a key hierarchy + rotation process that meets compliance **and** stays within latency/SLO budgets.

3) **The "Mental Model" (A simple analogy).**  
You put a letter in an envelope (DEK encrypts data), then put the envelope in a safe (KEK encrypts the DEK). When you change the safe’s combination (rotate KEK), you don’t rewrite every letter—you just move the envelopes to the new safe.

4) **The "L4 Trap" (Common junior mistake + why it fails at scale).**
- “Use one AES key for all data.” Security-only thinking makes rotation a petabyte rewrite and turns compromise into a company-ending event.  
- “Call KMS decrypt for every read.” It tanks p99 latency, increases cost, and makes KMS a global availability dependency.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Envelope format:** store `{ciphertext, wrapped_dek, kek_id/version, alg, nonce/iv, aad, created_at}` alongside the object; treat `kek_id` as part of the security boundary.  
- **Crypto detail (AEAD):** encrypt data with an AEAD (AES‑GCM or ChaCha20‑Poly1305); ensure **unique nonce per DEK** and bind AAD to `{tenant_id, object_id, version}` to prevent swap attacks.  
- **Crypto detail (wrapping):** generate a random DEK per object/chunk; wrap it with a KEK held in KMS/HSM (e.g., `Encrypt(DEK, EncryptionContext)` → `wrapped_dek`).  
- **Rotation mechanics:** rotate by issuing a new KEK version and **re-wrapping DEKs** (background job); data stays untouched. Prefer KMS “re-encrypt” semantics when available to avoid exposing plaintext DEKs.  
- **Data-plane/caching #1 (DEK cache):** cache decrypted DEKs in memory for hot objects with strict TTL/size limits; key cache entries by `(object_id, version)` and invalidate on rewrap/version change.  
- **Data-plane/caching #2 (KMS pressure control):** implement circuit breakers + rate limits for KMS calls; batch unwraps for scans; avoid retry storms that amplify an outage.  
- **Reliability design:** reads should not synchronously depend on KMS for every request; decide degraded mode when KMS is slow (serve from cache vs fail closed by tier).  
- **Operational detail #1 (monitoring):** dashboards for KMS latency/error rate, DEK cache hit rate, rewrap backlog, “objects on old KEK %,” and encryption/decryption p99 overhead.  
- **Operational detail #2 (incident runbooks):** key compromise playbook: disable old KEK usage, force rewrap priority, audit access logs, and coordinate customer comms for CMK tenants.  
- **Policy/control (access & separation):** constrain `kms:Decrypt` with IAM conditions and **encryption context** (e.g., `tenant_id`, `purpose`) so a stolen permission can’t decrypt arbitrary tenants’ data.  
- **Audit hygiene:** log key IDs and operation outcomes (wrap/unwrap) but never plaintext DEKs; treat audit logs as security-critical data.  
- **Explicit threat/failure mode:** if an attacker gains KMS decrypt rights (or you reuse GCM nonces), envelope encryption won’t save you—blast radius becomes “everything that key can unwrap.”

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** Storage-provider SSE only (simple; limited control/tenant isolation and rotation semantics).  
  - **B)** App encrypts with a static key (fast; catastrophic rotation/compromise story).  
  - **C)** **Envelope encryption with KMS-managed KEK + controlled DEK caching** (best balance; more moving parts).  
- I choose **C** and treat caching as a first-class design: bounded TTL/size, tiered fail-open/closed, and measured dependency on KMS.  
- Decisive trade-off: optimize for **rotation latency and compromise containment** while keeping p99 within budget via DEK caching and connection pooling to KMS.  
- What I’d measure: KMS QPS and p99, DEK cache hit rate, encryption overhead per request, % data rewrapped, and time-to-complete emergency rotation.  
- Risk acceptance: I’ll accept short-lived in-memory DEK caching for performance, but not long-lived disk caches of plaintext keys.  
- Stakeholder/influence: align Compliance (rotation/audit), SRE (dependency budgets), Data Platform (metadata formats), and Product/Finance (cost/perf) on an agreed rotation SLO and failure-mode policy.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You run a multi-tenant object store with **5 PB** of data, **250k RPS reads / 50k RPS writes**; added crypto overhead budget is **+5ms p99**; availability is **99.99%**.  
- Security: encrypt all customer data at rest; support **per-tenant customer-managed keys (CMK)**; require annual rotation and **<24h** response on key compromise.  
- Reliability: KMS has occasional regional brownouts; reads must continue safely without turning KMS into a global hard dependency.  
- Privacy/compliance: audit every unwrap action for 7 years; don’t log plaintext, DEKs, or customer content; tight access controls on logs.  
- Developer friction: 40 services read/write objects; you need a shared library + standardized metadata, not per-team crypto implementations.  
- Migration/back-compat: half the fleet uses legacy AES-CBC with a shared key; you must migrate online with mixed mode and measurable progress.  
- Incident/on-call twist: KMS latency spikes cause timeouts and retry storms; error rates cascade—what do you circuit-break, and what tier fails closed?  
- Multi-team/leadership twist: finance wants lower KMS cost, compliance wants stronger controls + CMK, product wants zero perf regression—propose phased rollout, caching strategy, and weekly reporting metrics.

---

1) **The Title (Catchy and technical).**