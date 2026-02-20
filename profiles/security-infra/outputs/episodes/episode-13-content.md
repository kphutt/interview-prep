## Title
Episode 13 — Frontier Digest A (Feb 2026): **PoP + Signals + Passkeys**  
Sender-constraint + push revocation + WebAuthn, constrained by p99 latency, rollout safety, and interop gaps.

## Hook
- Attackers are winning by **stealing sessions/tokens** (infostealers, AiTM proxies, log/header exfil) while crypto remains intact; the “strong login” story doesn’t stop replay of a stolen bearer credential.
- The ecosystem answer is a **stacked control plane** (DPoP/mTLS PoP + CAEP/RISC revocation + passkeys + App/Universal Links + PKCE), but stacking multiplies **integration seams**: key binding, token formats, event delivery, and client capability detection.
- Sender-constraint (DPoP/mTLS) is conceptually clean yet operationally sharp: it introduces a **hot-path replay cache + signature verification** that competes directly with your gateway’s **+10ms p99** budget and can become an availability incident.
- Shared Signals (CAEP/RISC) gives you a real “kill switch,” but it also creates a new always-on, security-critical ingestion service with **idempotency, replay defense, backlog management, and SLOs**—i.e., something that will page.
- Passkeys reduce phishing, but **recovery, device changes, and platform fragmentation** can produce conversion drops and support escalations; security wins can be undone by product-driven fallback paths if you don’t pre-negotiate assurance tiers.
- Mobile OAuth is where most real-world breakage hides: **custom schemes**, missing PKCE, missing `iss` checks, and app-link verification gaps make “right user, wrong app” a recurring failure mode under partner and legacy constraints.
- You can’t introspect every request (cost/availability), so correctness must come from **local verification + cached state**; that pushes complexity into cache eviction behavior, regional partitions, and “fail open vs fail closed” decisions per scope.
- Privacy/compliance constraints (no raw token logging; minimize device identifiers) reduce debugging visibility, so you must design **structured, non-secret telemetry** that still lets on-call pinpoint whether failures are client capability, replay cache, CAEP lag, or policy mismatch.
- The Staff problem is not choosing “the best standard,” it’s deciding **what to standardize now** (high-risk scopes) vs what stays on a watchlist, with measurable success criteria and a rollback plan that won’t devolve into permanent exceptions.

## Mental Model
Modern identity is a building with layered controls: the front door accepts **phishing-resistant keys** (passkeys), the hallways require a **badge that must match the person holding it** (sender-constrained tokens), and the security desk can **radio an immediate invalidate** when compromise is confirmed (Shared Signals revocation). Mobile app-link verification is the doorman ensuring the badge and entry instructions go to the **real tenant app**, not a convincing lookalike. The hard part at scale is that each layer adds a dependency (client features, caches, event pipelines) that can fail independently and create outages or high-friction fallbacks.

- Passkeys → **keyed entry**: strong initial authentication, but still requires operationally safe recovery paths and platform/version gating to avoid conversion/SLA regressions.
- PoP (DPoP/mTLS) → **badge matches holder**: binds access to a key/cert so stolen tokens can’t be replayed; enforces per-request proof with explicit “fail closed” policy for privileged scopes.
- CAEP/RISC → **security desk radio**: event-driven revocation epoch lets you kill sessions quickly without per-request introspection; reliability and lag become SLO-managed production concerns.
- Failure mode mapping: if the doorman is lax (missing App/Universal Links + PKCE + `iss` validation), an attacker can redirect the user’s “entry process” into a lookalike app/proxy and still obtain valid tokens—your badge system then faithfully authorizes the wrong party.

## Common Trap
- Red flag: “Ship passkeys, we’re done” — fails at scale because **session/refresh token theft** remains viable and you lack a fast kill switch; it drives recurring fraud incidents and creates **support toil** via recovery edge cases (lost device, cross-platform sync gaps) that product teams will “fix” by weakening assurance.
- Red flag: “Enable DPoP everywhere by default” — fails at scale because client ecosystems (legacy mobile, partners, header-stripping intermediaries) won’t be uniformly compatible; it creates widespread 401s, emergency rollbacks, and **long-lived exception sprawl** that permanently increases on-call burden.
- Red flag: “Treat CAEP/RISC as best-effort telemetry” — fails because compliance turns revocation into a **time-bound commitment**; missing/lagged events become audit findings and force high-severity incidents where teams scramble to invalidate sessions manually (high toil, high blast radius).
- “Relax `htu`/host matching so fewer users break” — fails at scale because gateways see proxies, host rewrites, and multi-tenant routing; overly strict validation causes conversion drops, overly loose validation risks confused-deputy behavior, and you end up with **inconsistent per-service patches** and a permanent debugging tax.
- “Let each microservice implement PoP + revocation checks” — fails at scale because 30 services drift in validation rules, caching semantics, and log hygiene; developer friction rises (every team becomes an auth team) and reliability suffers when a single inconsistent rollout pages the fleet.
- “Solve interop by extending token lifetimes and relying on logout” — fails at scale because it increases attacker dwell time (directly opposing <60s revocation goals), bloats revocation state, and makes incident response harder (larger blast radius when you must invalidate).

## Nitty Gritty
**Protocol / Wire Details**
- Anchor: RFC 9449 — DPoP proof fields + replay semantics.
- DPoP-protected resource call shape: `Authorization: DPoP <access_token>` plus `DPoP: <compact JWS>`; require `typ="dpop+jwt"`, disallow `alg=none`, and allowlist algorithms (commonly ES256) to keep verification cost predictable.
- DPoP proof claim validation: `htu` must match the effective HTTPS URL under a deterministic canonicalization policy, `htm` must match HTTP method, `iat` must be within an explicit skew window, and `jti` must be unique per key for the proof lifetime.
- Token binding correctness: require `ath = BASE64URL(SHA-256(access_token))` when presenting an access token, so a captured proof can’t be replayed with a different token; treat missing/incorrect `ath` as a hard failure for high-risk scopes.
- Key continuity: access tokens must carry confirmation that ties them to the DPoP key (e.g., `cnf.jkt` thumbprint); resource servers must reject proofs whose key thumbprint doesn’t match the token’s `cnf`, otherwise you’ve implemented “signed bearer.”
- mTLS sender-constraint alternative: bind tokens to client cert via `cnf.x5t#S256`; operationally strong when TLS is end-to-end, but incompatible with TLS-terminating partner appliances and high-friction for mobile cert lifecycle—use only where partner class supports it.
- Anchor: RFC 9126 (PAR) — Stops auth params leaking via URLs/logs.
- PAR + JAR posture for high-risk: push authorization parameters via PAR (`request_uri` indirection) and, where multiple intermediaries exist, use JAR (signed `request` JWT) to prevent request tampering/confused-deputy edges without relying on “don’t log query params.”
- Anchor: RFC 9207 (`iss`) — Mix-up defense for multi-issuer OAuth.
- Mobile OAuth integrity: enforce PKCE (`code_challenge_method=S256` only) and prefer `https://` redirect URIs protected by App/Universal Links association; allow legacy custom schemes only with reduced scopes/short TTL and an explicit migration end date.

**Data Plane / State / Caching**
- Replay cache hot path design: cache `(jwk_thumbprint, jti) -> seen` with TTL ≈ proof lifetime (+ skew), implemented as regional in-memory LRU to avoid a new cross-region dependency that would blow p99 and availability.
- Partitioning to avoid eviction storms: hash by `jwk_thumbprint` so a single noisy client cohort doesn’t evict the entire cache working set; track eviction rate as a first-class SLO indicator.
- CAEP/RISC enforcement without introspection: store `revoked_at` / `epoch` per `sub` and optionally `sid`; requests locally compare token issuance time (`iat`) or session auth time to the epoch to decide validity.
- CAEP receiver replay/idempotency: verify SET JWS, then cache event `jti` and apply updates with “latest-wins” semantics (monotonic timestamps) to survive retries and out-of-order delivery without flapping revocation state.
- WebAuthn challenge store: `(challenge_id, user_handle, rpId)` with ~5 minute TTL, strict one-time use; keep it region-local to prevent cross-region latency and avoid turning login into a distributed transaction.
- Data minimization under compliance: do not persist raw tokens/DPoP proofs; prefer thumbprints, subject IDs, and short-lived cache entries with enforced retention to avoid creating a new device-tracking dataset.

**Threats & Failure Modes**
- Real adversary model: passkeys blunt credential phishing, but infostealers/AiTM still steal cookies and refresh/access tokens; without PoP + fast revocation, attacker persistence is limited only by token TTLs and user awareness.
- Header/interop brittleness: proxies that strip or duplicate headers can break DPoP in ways that look like random auth failures; if clients retry aggressively, you can turn a validation issue into a self-inflicted load incident.
- `htu` mismatch pitfalls: edge routing, alternate domains, default ports, and normalization differences create false rejects; the “quick fix” of relaxed matching can become an auth bypass if attacker can influence host/origin selection through intermediaries.
- Red flag: “Fail open on PoP errors for availability” — at scale this becomes a stealth downgrade to bearer for privileged scopes, undermining both compliance posture and incident triage (you can’t prove what was enforced).
- Red flag: “Centralize replay cache as a hard request-path dependency” — partitions/outages force an impossible choice between breaking auth or disabling PoP; SRE will choose availability under pressure unless you predefine safe degradation.
- Anchor: RFC 8417 (SET) — Standard envelope for CAEP/RISC events.
- Revocation pipeline failure mode: event receiver lag/backlog silently violates <60s kill-time; you need explicit lag metrics and paging, otherwise compromise response becomes “best effort” with audit risk.
- Partner + legacy friction: TLS termination breaks mTLS and may leak bearer tokens in partner logs; treat partner classes as policy objects (allowed scopes, required controls, audit obligations) rather than “one-off compatibility hacks.”

**Operations / SLOs / Rollout**
- Latency budgeting: DPoP adds JWS verification + replay cache I/O; measure incremental p95/p99 by endpoint and platform, and treat CPU/regression as a security rollout blocker (security features that cause outages will be disabled).
- Telemetry without secrets: emit reason-coded counters and histograms (`dpop_invalid_sig`, `dpop_ath_mismatch`, `revoked_epoch_hit`, `caep_lag_seconds`, `webauthn_not_allowed_error`) with hashed identifiers; ban raw token/proof logging via lint + runtime redaction.
- Rollout discipline: feature-flag enforcement by `client_id` and scope tier; canary by OS/app version; define rollback triggers tied to SLO/error budget and rehearse rollback so on-call can act in minutes.
- CAEP/RISC SLO framing: define “compromise-to-deny” p95/p99; page on sustained breaches and on event ingestion health (queue depth, signature verification errors, issuer JWKS fetch failures) while keeping request path independent of IdP uptime.
- Anchor: draft-ietf-oauth-v2-1 — Turns best practices into CI-enforced defaults.
- Load-shedding during incidents: when replay cache thrashes or CPU spikes, shed by scope/cohort (drop PoP requirement for low-risk reads first), keep `payments:write` fail-closed, and document any temporary policy relaxations as time-bounded, auditable exceptions.

**Interviewer Probes (Staff-level)**
- Probe: Design the DPoP replay cache for 150k RPS and multi-region—key, TTL, eviction, and how you avoid global dependencies.
- Probe: In a multi-IdP app, how do you enforce RFC 9207 `iss` and prevent mix-up without breaking legacy clients?
- Probe: You need <60s revocation but can’t introspect requests and the IdP can be partially down—how do CAEP/RISC epochs work in degraded mode?
- Probe: With “no raw token logging,” what observability signals let you debug DPoP/passkey failures and prove enforcement to Compliance?

**Implementation / Code Review / Tests**
- Coding hook: Reject DPoP proofs unless `typ=="dpop+jwt"` and `alg` is allowlisted; require strict JWS parsing and explicit header handling (no permissive fallbacks).
- Coding hook: Canonicalize `htu` deterministically and unit-test proxy/edge variants (host rewrites, default ports, trailing slashes) with explicit accept/reject vectors to avoid accidental bypass.
- Coding hook: Enforce `iat` skew windows (e.g., ±300s) and negative-test far-future/far-past proofs; ensure client clock drift errors are observable and actionable, not silent drops.
- Coding hook: Replay cache correctness: implement atomic “insert-if-absent,” race-test concurrent duplicates, and validate eviction metrics (evictions vs misses) so you can distinguish attack/replay from cache thrash.
- Coding hook: Verify `ath` against the exact access token bytes; add substitution tests (valid proof + different token) and ensure missing `ath` is rejected when policy requires it.
- Coding hook: CAEP receiver: verify SET JWS signature, validate `aud`, cache event `jti`, and apply idempotent latest-wins updates; fuzz out-of-order, duplicate, and malformed events.
- Coding hook: PKCE enforcement tests: reject `plain`, validate verifier length/charset, and add downgrade attempts (missing PKCE) that must fail for high-risk scopes while allowing controlled legacy paths.
- Coding hook: WebAuthn tests: one-time challenge use, correct `origin`/`rpIdHash` verification, and `userVerification="required"` gating for privileged scopes; add replay and cross-origin negative tests.

## Staff Pivot
- Approach A: **Passkeys-only** — best-in-class phishing resistance at login, but stolen session cookies/refresh tokens still replay; revocation becomes “wait for expiry,” which fails the <60s requirement and increases incident ambiguity.
- Approach B: **PoP-only (DPoP/mTLS)** — reduces replay of stolen access tokens, but doesn’t materially reduce ATO via phishing/social engineering; also adds client friction and hot-path cost without fixing login vector.
- Approach C: **Layered (passkeys + PoP + CAEP/RISC)** — highest security coverage (phishing + replay + kill switch) but introduces multiple production dependencies (caches, event pipelines, client capability matrix) that must be SRE-grade.
- Decisive trade: choose **C**, but **tier enforcement by scope and cohort**—`payments:write`/admin gets passkeys (UV required) + sender-constrained tokens + CAEP revocation first; low-risk reads can remain bearer temporarily with explicit end dates and monitoring.
- Centralize enforcement: implement PoP validation, PKCE/`iss`/PAR policy, and revocation epoch checks at the **gateway/edge** with a golden-path SDK; allow per-service only as a fallback with strict conformance tests to avoid policy drift.
- Reliability stance: CAEP must not be a synchronous dependency for each request; request-time decisions must work from locally cached epoch state during IdP partial outages, with documented “degraded but safe” behavior.
- Measurement plan (adopt/pause criteria): **ATO rate by vector**, DPoP replay blocks, CAEP time-to-kill p95/p99, gateway auth overhead p99 and CPU, WebAuthn/passkey error rates by platform, login conversion, support tickets per 10k logins, and on-call pages attributable to auth.
- Risk acceptance: accept **partial ecosystem coverage** (bearer + short TTL for low-risk scopes, legacy redirect schemes for old app versions) only with time-bounded exceptions, compensating monitoring, and a deprecation calendar that leadership signs.
- What I would NOT do: depend on per-request introspection or a new global replay-store dependency to “simplify correctness”—tempting for purity, but incompatible with latency/availability constraints and guarantees an outage-driven rollback.
- Stakeholder influence: align Product (conversion), Compliance (phishing-resistant + kill-time), Partners (capability constraints), and SRE (dependencies/latency) around an **assurance matrix**, explicit rollback triggers, and an exception workflow with expiry and auditability.
- Tie-back: Describe a prior rollout where a new auth check threatened p99—what SLOs/metrics and rollback triggers did you use?
- Tie-back: Describe how you negotiated a tiered security policy with Product/Compliance/Partners and kept exceptions from becoming permanent.

## Scenario Challenge
- You run a global auth + API gateway serving **150k RPS**, with a hard budget of **+10ms p99** for auth processing and **99.99% availability**.
- Fraud has shifted: attackers steal **access tokens and session cookies** via infostealers; they can read logs/headers, but **cannot compromise OS secure key stores** holding private keys.
- Compliance mandates **phishing-resistant auth** (passkeys/WebAuthn) for money movement and **<60s revocation** after confirmed compromise.
- Reliability constraint: your APIs must remain available during **IdP partial outage**; you **cannot introspect every request** and cannot introduce a new global synchronous dependency in the request path.
- Security constraint: prevent replay of stolen access tokens for `payments:write` (sender-constrained tokens required); mTLS is inconsistent because partners terminate TLS.
- Privacy/compliance constraint: **no raw token logging**; device identifiers must be minimized and purpose-bound (you must be able to justify any stable identifier retention).
- Developer friction constraint: **30 microservices + 3 mobile apps + partners**; enforcement must be at the gateway with a **golden path SDK**—no bespoke per-service auth logic.
- Migration constraint: legacy mobile versions still use `myapp://` redirects and bearer tokens; mixed-mode must work per `client_id`/scope for **12–18 months** with a clear deprecation plan.
- OAuth hardening requirement: in a multi-IdP environment, you must adopt **PKCE** and **RFC 9207 `iss`** validation (and likely PAR/JAR for high-risk) without breaking conversion.
- Revocation requirement: integrate **CAEP/RISC**; events can be delayed/duplicated/out of order, and the receiver must be production-grade (signature verification, replay defense, idempotency).
- Incident twist: after enabling DPoP for a large mobile cohort, gateway CPU spikes and `dpop_jti_replay_cache_miss` climbs due to cache evictions; **p99 latency breaches** and error budget burn starts.
- Hard technical constraint: SRE says “no new hard dependency,” so “just use a centralized replay cache store” is not acceptable; you must pick what to shed and how to degrade safely.
- Leadership twist: Product demands “no UX change,” Compliance wants “phishing-resistant now,” Partners want “no client changes,” and SRE wants “reversible rollout with bounded blast radius.”
- Decision request: specify which cohorts get passkeys first, which scopes require PoP, your CAEP kill-time SLO (p95/p99), where you fail closed vs open in degraded modes, and the explicit exception process (owners, expiry, audit, compensating controls).

### Evaluator Rubric
- Demonstrates risk prioritization under ambiguity: ties controls to **threat vectors** and scopes, with time-bounded exceptions instead of permanent “special cases.”
- Proposes an architecture that is **locally verifiable on the request path** (PoP + JWT + cached epoch) and resilient to IdP partial outages, with explicit degraded-mode semantics.
- Provides concrete replay-cache and CAEP state designs (keys, TTLs, idempotency), plus how to monitor and page on **cache thrash** and **revocation lag** against SLOs.
- Shows SRE-grade rollout planning: feature flags by `client_id`/scope, canary cohorts, rollback triggers, dashboards segmented by platform/app version, and rehearsed emergency actions.
- Addresses privacy/compliance constraints with operational practicality: structured non-secret telemetry, minimal identifiers, retention limits, and auditable exception handling.
- Handles stakeholder conflict with a clear mechanism: assurance tier policy, deprecation calendar, partner capability classes, and decision logs that survive audit and incident review.
- Treats incident response as first-class: defines paging thresholds, runbooks for CPU/cache incidents and CAEP lag, and pre-approved “shed load vs fail closed” decisions for `payments:write`.
- Uses measurable success criteria: ATO reductions by vector, replay blocks, time-to-kill, p99 overhead, conversion, and on-call toil attribution.