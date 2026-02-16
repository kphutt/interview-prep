============================================================
EPISODE 1
============================================================

## Title
**The Binding Problem: mTLS vs DPoP for Sender‑Constrained OAuth Tokens**  
(As-of: Feb 2026)

## Hook
- Bearer JWTs are spendable “anywhere, immediately” once copied (logs, headers, JS); sender-constraint reduces replay, but only if enforcement happens at the right hop (edge vs app) without introducing a new single point of failure.
- The crypto is easy; the hard parts are (a) where TLS actually terminates in your fleet and partner networks, and (b) how to propagate binding material to the component making the authZ decision without creating spoofable headers.
- mTLS binding is operationally “clean” for controlled server-to-server clients, but certificate issuance/rotation/revocation is a full product with pager load; adoption failures tend to be spiky and correlated (one bad renewal script can take out a partner cohort).
- DPoP fits public clients (mobile/SPAs) but shifts cost to the hot path: per-request signed proofs + replay caches + nonce retry logic; at 200k RPS the CPU and p99 budget impact is real, not theoretical.
- Enforcing at the gateway centralizes policy and reduces per-service drift, but concentrates blast radius: a bug in proof verification or cache behavior can brownout the entire API surface and violate 99.95% availability.
- Rollout is inherently mixed-mode (per client_id, per scope): you must accept bearer for a while; the risk question is “which scopes can stay bearer under fraud pressure” and “what’s the earliest safe fail-closed boundary.”
- Token theft incidents rarely arrive with clean forensics: privacy constraints (no raw token logging, no stable device IDs) limit what you can store, so design must include auditability via digests/thumbprints and carefully scoped retention.
- Latency and retry behavior are adversarial to reliability: DPoP nonce adds an RTT; mTLS handshake adds CPU and can interact badly with connection churn—both can amplify tail latency and trigger cascading retries during an incident.
- Partner intermediaries (TLS-terminating appliances, cert rewriting, header mangling) turn a “standards-compliant” plan into a real-world negotiation; choosing fail-open vs fail-closed is a risk acceptance decision that must be explicit, time-bounded, and monitored.

## Mental Model
Bearer tokens are cash: whoever holds it can spend it until it expires. Sender-constrained tokens are a card that only works when presented with the right proof (PIN/device key/certificate), so copying the card number alone isn’t enough. The system design problem is deciding where the “PIN check” happens (edge vs app), how you recover when proofs fail, and how you migrate without breaking existing clients.

- Cash → bearer JWT: possession in headers is sufficient; leaks via logs/XSS are immediately replayable.
- Card + PIN → token + binding: token contains `cnf` (confirmation) and request supplies proof (mTLS peer cert or DPoP JWT).
- PIN check location → enforcement point: edge/gateway offers consistency and observability; per-service enforcement reduces blast radius but increases drift and developer friction.
- Card issuer rules → policy: require sender-constraint for high-risk scopes (write/admin), allow bearer temporarily for low-risk read during migration with explicit sunset.
- Adversary behavior: attacker with log access can replay bearer tokens cross-network; sender constraint blocks this *unless* private key/cert is also exfiltrated (assumption: OS keystore not compromised).

## L4 Trap
- Red flag: “Just shorten token TTL to 5 minutes” → fails because replay still works immediately; at scale it shifts load to the token mint/refresh path, increasing IdP QPS, cache churn, and outage blast radius; dev friction shows up as more auth-related flakes, retries, and higher on-call noise during IdP hiccups.
- Red flag: “Mandate mTLS for all clients” → fails because public clients (SPAs/mobile) can’t reliably protect/manage X.509 client certs; partners behind TLS terminators can’t present stable client cert identity; operationally you create a cert-ops treadmill (issuance, renewal, revocation, expiry paging) and break long-lived app versions.
- “Enforce binding inside each microservice” → fails because you get inconsistent interpretations of RFCs, inconsistent cache behavior, and inconsistent logging/privacy handling; reliability risk is fragmented rollouts and uneven fail-open/fail-closed behavior, producing hard-to-debug partial outages.
- “Add DPoP but ignore replay cache” → fails because without `(jwk_thumbprint, jti)` tracking, proofs are replayable within their lifetime; at scale this becomes a silent security regression plus an operational incident when fraud finds the gap and you scramble to hotfix statefulness into a stateless tier.
- “Always require nonce to be ‘extra secure’” → fails because it adds an RTT and complicates retry/backoff under packet loss; at scale this can violate p99 latency budgets and create retry storms; dev friction: client libraries must implement nuanced retry semantics and clock/iat handling.
- “Log full tokens/proofs for debugging” → fails due to privacy/compliance constraints and increases blast radius of any log leak; on-call reality: you need debuggability via digests/thumbprints and structured rejection reasons, not raw secrets.

## Nitty Gritty
**Protocol / Wire Details**
- mTLS-bound access tokens (RFC 8705): client presents X.509 cert in TLS handshake; AS includes `cnf` claim with `x5t#S256 = base64url(SHA-256(DER(leaf_cert)))`.
- Resource server enforcement (mTLS): extract TLS peer leaf cert thumbprint from the connection; compare to `access_token.cnf["x5t#S256"]`; reject on mismatch or missing `cnf` when policy requires binding.
- TLS termination reality: if TLS terminates at edge proxy/LB, binding must be enforced at that termination point **or** forwarded as non-spoofable metadata (e.g., proxy→backend mTLS + signed/attested `X-Client-Cert-SHA256`).
- DPoP proof (RFC 9449): each request includes `DPoP: <JWT>`; JWS header contains `typ:"dpop+jwt"`, `alg:"ES256"` (or EdDSA), and an embedded `jwk` (public key for proof verification).
- DPoP payload claims: `htu` (target URL), `htm` (HTTP method), `iat` (issued-at), `jti` (unique ID); when presenting an access token include `ath = base64url(SHA-256(access_token))`.
- URL canonicalization is part of correctness: `htu` matching must be consistent with gateway routing (scheme/host/port/path normalization) or you’ll create false rejects and on-call escalations.
- Anchor: `cnf.x5t#S256` — binds token to a specific leaf certificate.
- Anchor: `DPoP` header — per-request proof that limits token replay.
- Anchor: `ath` claim — binds proof to a specific access token.

**Data Plane / State / Caching**
- HTTP/2 multiplexing nuance (mTLS): many requests share one TLS session; binding is per-connection, so edge enforcement must map “request’s Authorization token” to “current connection’s peer cert” without cross-stream confusion.
- Token verification caching: cache validated token metadata (`sub`, `scope`, `exp`, `cnf`) keyed by a token digest (e.g., SHA-256 of token string); avoids repeated signature verification at high QPS; never store/log raw token.
- DPoP replay defense: cache seen `(jwk_thumbprint, jti)` for proof lifetime (often 1–5 minutes); use local LRU for fast path, optionally a shared store (e.g., Redis) for restart resilience—explicitly quantify false negatives on restart as risk acceptance.
- Cache key specifics: `jwk_thumbprint` should be RFC-consistent (JWK thumbprint over normalized JSON); store as fixed-length bytes/base64url to keep memory bounded.
- Replay window tuning: align `(jti)` retention with acceptable clock skew and `iat` validation window; too short increases false accepts (replay), too long increases memory and false rejects under retries.
- Nonce liveness option: server returns `DPoP-Nonce: <rnd>` on 401/400; client retries with `nonce` claim—improves proof freshness but adds an RTT and complicates idempotency and retry handling.
- CPU budgeting: DPoP adds per-request JWS verification + hash; mTLS adds handshake overhead but amortizes over connection reuse; under 200k RPS, the “shape” of cost matters (steady per-request vs spiky per-connection).
- Anchor: `(jwk_thumbprint, jti)` cache — primary data-plane replay control.

**Threats & Failure Modes**
- Threat: bearer token exfiltration via logs, browser memory, proxy headers → immediate replay from anywhere; sender constraint blocks replay unless attacker also steals private key/cert (explicit assumption: OS keystore not compromised).
- Failure mode (mTLS): intermediary cert rewriting/termination means the gateway sees the appliance cert, not the client cert → `x5t#S256` mismatch and sudden partner outage; on-call decision: tiered failover vs fail-closed with scoped allowlist.
- Failure mode (DPoP): incorrect `htu` canonicalization across gateways (e.g., external host vs internal host, http→https termination) → widespread false rejects and p99 spikes due to retries.
- Failure mode (DPoP): missing or weak replay cache → attacker replays captured `(DPoP, Authorization)` pair within lifetime; appears as “legit” traffic unless you track `jti` reuse metrics.
- Failure mode (nonce): packet loss or client retry storms after `DPoP-Nonce` challenges → elevated `nonce_retry_rate`, increased tail latency, and potential self-inflicted DoS; requires backoff and circuit-breaking.
- Red flag: “Forward client cert via plain header to backend” → spoofable by any client unless the hop is mutually authenticated and the header is cryptographically protected; creates an easy bypass and messy incident response.
- Red flag: “Store stable device identifiers to ‘strengthen’ DPoP” → violates privacy/compliance constraints; creates long-term tracking risk and expands breach impact; prefer ephemeral thumbprints/digests with scoped retention for fraud.
- Policy/control: require sender-constraint for high-risk scopes (e.g., `payments:write`, admin) at gateway; explicitly reject tokens missing `cnf` or missing/invalid DPoP proof; keep least-privilege scopes to reduce blast radius during mixed-mode.
- Auditability constraint: log only digests/IDs (`token_digest`, `x5t#S256`, `jwk_thumbprint`, `jti`) plus structured rejection reason; set retention to minimum necessary for fraud investigations.
- Anchor: `binding_mismatch_rate` — early signal for rollout breakage and attacks.

**Operations / SLOs / Rollout**
- Metrics to wire day 0: `binding_mismatch_rate`, `dpop_nonce_retry_rate`, `mtls_handshake_failure_rate`, DPoP verify CPU time, token cache hit rate, and “replay blocked” counters (e.g., `jti_reuse_detected`).
- Pager thresholds: sudden step-function in `binding_mismatch_rate` or `mtls_handshake_failure_rate` for a partner cohort implies cert rewriting/expiry; sudden spike in `dpop_nonce_retry_rate` implies nonce misconfig, clock skew, or client library bug.
- Rollout strategy: mixed-mode by `client_id` and/or scope; canary at gateway with per-client policy config; bake in a time-bounded exception process with expiry to prevent permanent fail-open.
- Reliability discipline: keep a kill-switch for sender-constraint enforcement (per client/scope) with audited access; require rollback drills because verification bugs are high-blast-radius.
- SLO coupling: DPoP verification in gateway must be budgeted into p99 (+20ms) and availability (99.95%); do load testing with realistic key distributions and HTTP/2 connection reuse patterns.
- Key lifecycle ops: DPoP keys live on-device (Secure Enclave/Keystore) → plan for “key lost” recovery and account binding behavior; mTLS requires cert issuance/renewal/revocation pipelines plus expiry monitoring and partner guidance.
- Industry Equivalent: “edge/gateway” = Envoy/Nginx/HAProxy/API Gateway; “IdP/AS” = OAuth Authorization Server.

**Interviewer Probes (Staff-level)**
- Probe: Where exactly do you enforce mTLS binding if TLS terminates at the edge, and how do you prevent spoofing when forwarding identity to backends?
- Probe: For DPoP at 200k RPS, what replay cache design meets p99 +20ms without sacrificing restart resilience—what do you accept as residual risk?
- Probe: How do you canonicalize `htu` in a multi-host gateway (external hostnames, internal routing, http→https termination) to avoid false rejects?
- Probe: What’s your decision framework for fail-open vs fail-closed when partners start failing due to cert rewriting—how do you time-box exceptions and measure abuse?
- Probe: What telemetry do you need to prove to fraud leadership that replay protection is working under privacy constraints (no raw token logging)?

**Implementation / Code Review / Tests**
- Coding hook: Reject if policy requires sender-constraint and token lacks `cnf` (mTLS) or request lacks valid `DPoP` proof; ensure error is explicit and meterable.
- Coding hook: Implement strict `cnf.x5t#S256` comparison using constant-time compare on decoded bytes; add negative tests for base64url padding/encoding variants.
- Coding hook: Validate DPoP JWT header: `typ == "dpop+jwt"`, `alg` allowlist (ES256/EdDSA), embedded `jwk` required; reject `none` and unexpected key types.
- Coding hook: Verify `ath` equals SHA-256 over the *exact* access token string presented; negative test: same proof reused with different token must fail.
- Coding hook: Implement `htu` normalization tests covering scheme/host/port defaults, path encoding, and query handling consistent with gateway routing; add regression tests for host header vs SNI.
- Coding hook: Replay cache invariants: `(jwk_thumbprint, jti)` must be unique within TTL; add concurrency tests (simultaneous requests) to ensure atomic “check-then-set”.
- Coding hook: `iat` window validation: enforce max skew (e.g., ±5 min) and proof lifetime; negative tests for far-future and stale proofs; ensure clock issues don’t cause mass outage without clear metrics.
- Coding hook: Nonce flow test: server challenges with `DPoP-Nonce`, client retries once with nonce; ensure bounded retries/backoff to prevent infinite loops under packet loss.
- Coding hook: Token metadata cache: key by token digest; ensure eviction respects `exp`; add test: revoked/rotated signing keys don’t cause indefinite accept due to stale cache (bounded TTL).
- Coding hook: Logging/privacy tests: assert logs contain only digests/thumbprints and structured reasons; forbid raw `Authorization`/`DPoP` headers via linting or runtime guards.

## Staff Pivot
- Compare approaches under constraints (200k RPS, +20ms p99, 99.95%):  
  - **A)** Bearer + short TTL: simplest rollout, but doesn’t stop “right now” replay; increases IdP/token endpoint load and incident coupling.  
  - **B)** mTLS-bound tokens: strong, low per-request CPU when connections are reused; heavy cert lifecycle ops and breaks with TLS-terminating intermediaries.  
  - **C)** DPoP-bound tokens: works for public clients and hostile networks; adds per-request verification and replay-cache state; nonce introduces RTT and retry complexity.
- Decisive split aligned to client reality: **mTLS for server-to-server + managed enterprise devices**, **DPoP for mobile/public clients**, **bearer only for low-risk read scopes during migration** with an explicit sunset.
- Enforcement placement: bias to **gateway/edge** to centralize policy, observability, and conformance; accept that this concentrates blast radius, so invest in kill-switches, canaries, and strict performance budgets.
- Latency argument: mTLS cost is front-loaded in handshake; DPoP cost is per request—choose based on connection reuse and client type; for mobile where connections churn, DPoP may be more predictable than repeated mTLS handshakes plus cert UX.
- Reliability argument: a bad DPoP verification release can take out all traffic; mitigate with staged rollout by `client_id`, shadow-verify mode (measure-only), and rollback triggers on mismatch/nonce retry rate.
- What I’d measure (success + safety): p95/p99 auth overhead, gateway CPU per RPS, `dpop_nonce_retry_rate`, `mtls_handshake_failure_rate`, `binding_mismatch_rate`, `jti_reuse_detected` (replays blocked), adoption time by partner/mobile cohorts, and on-call pages/week attributable to auth.
- Risk acceptance statement: allow bearer tokens for low-risk read scopes for **1–2 quarters** to avoid freezing product, but set a hard deadline to require sender-constraint for admin/write scopes; document residual risk and compensating controls (shorter TTL only as a stopgap, anomaly detection).
- Stakeholder alignment plan:  
  - Identity team owns token format (`cnf`, DPoP requirements) → agree on standards-compliant claims and key rotation posture.  
  - Gateway team owns enforcement cost/SLO → agree on performance budgets, caching, and safe rollout mechanics.  
  - Mobile/Partner teams own client changes → provide reference SDK + conformance tests so correct implementation is the default, not bespoke.
- Policy/compliance trade-off: privacy limits logging and device identifiers; design observability around thumbprints/digests with minimal retention that still supports fraud investigations and audits.
- On-call posture: predefine failover modes (per client/scope) and an exception process with expiry; avoid “permanent fail-open” by making exceptions observable and leadership-reviewed.
- What I would NOT do (tempting but wrong): “flip a global switch to require binding for all traffic” without per-client canary and partner readiness signals—this violates availability and creates a crisis-driven rollback that erodes security credibility.
- Tie-back: Describe a time you shipped a high-blast-radius auth change—what were your rollout gates and rollback triggers?
- Tie-back: Describe how you negotiated a time-bounded risk acceptance with fraud/product while meeting SLOs.

## Scenario Challenge
- You operate an API gateway handling **200k RPS**, with a strict **p99 latency budget of +20ms** attributable to auth changes and an overall **99.95% availability** target; today traffic uses **bearer JWT access tokens with 1-hour TTL**.
- A partner incident: access tokens were leaked into logs; fraud demands **replay protection within 90 days** (not “reduced window,” actual sender-constrained semantics across networks).
- Client mix constraints: iOS/Android apps, SPAs, and server-to-server partners; some partners are behind **TLS-terminating appliances** where end-to-end mTLS may be impossible or cert identity is rewritten.
- Security constraint: attacker can read HTTP headers/logs and replay from a different network; assume attacker **cannot compromise OS keystores** (so DPoP private keys on-device remain protected).
- Privacy/compliance constraint: cannot log raw tokens or stable device identifiers beyond what’s necessary; must support fraud investigations with minimal retention (digests/thumbprints only).
- Developer friction constraint: cannot require weekly app updates; long-lived app versions must continue working during rollout; partner upgrades are slow and need clear conformance requirements.
- Migration/back-compat constraint: must accept existing bearer tokens during rollout; must support **mixed mode per client_id and/or scope** with explicit deprecation timelines and safe rollback.
- Hard technical constraint: TLS terminates at the gateway, but some partners also terminate TLS upstream; you can’t assume the gateway ever sees the “real” client certificate even if the partner claims mTLS.
- On-call twist: after enabling mTLS for a pilot cohort, a subset of partners starts failing because an intermediary rewrites client certs; traffic drops and the partner escalates—decide **fail open vs fail closed vs tiered failover**, under a running incident, while preserving fraud goals.
- Multi-team twist: product leadership insists “no UX change,” gateway team is concerned about CPU cost and tail latency from DPoP verification + replay caches, and Identity controls the token format and issuance timeline.
- Policy twist: fraud wants binding for all tokens immediately; compliance rejects any plan that logs raw auth artifacts; SRE wants a provable rollback plan that keeps 99.95%.
- Success metrics constraint: must define what “replay protection delivered” means in telemetry without logging secrets (e.g., `jti_reuse_detected`, mismatch rates, adoption % by scope/client).
- Rollout constraint: you need staged enforcement and “shadow” validation modes to quantify breakage before fail-closed, while ensuring attackers don’t get a permanent bypass window.

**Evaluator Rubric**
- Clearly states assumptions (TLS termination points, client capabilities, attacker model) and identifies which assumptions are fragile/need validation with partners.
- Prioritizes risk under ambiguity: which scopes/client cohorts get sender-constraint first, and what residual risk is accepted for how long (time-bounded, documented).
- Presents an architecture that fits constraints: where enforcement lives (gateway vs services), how binding metadata is obtained safely, and how performance is kept within +20ms p99.
- Provides an operational rollout plan: mixed-mode policy, canary strategy, explicit rollback triggers (mismatch/nonce retry/CPU), and an exception process with expiry.
- Demonstrates incident readiness: predefined failover modes (tiered fail-open/closed), on-call runbooks, and how to avoid retry storms and cascading failures during nonce/mTLS issues.
- Addresses privacy/compliance concretely: what is logged (digests/thumbprints), retention, auditability, and how fraud investigations remain possible without raw tokens or stable identifiers.
- Shows stakeholder influence: how to align Identity, Gateway/SRE, Mobile/Partner, Fraud, and Product on timelines, SDK/conformance, and risk acceptance with measurable outcomes.
- Tie-back: Explain a time you balanced security enforcement with SLOs during a rollout or incident—what metrics drove decisions?

============================================================
EPISODE 2
============================================================

## Title
**The Session Kill Switch:** Event‑Driven Revocation with CAEP/RISC (without per‑request introspection)

## Hook
- Long-lived sessions reduce login prompts and support mobile/offline UX, but they materially increase the blast radius of compromised tokens unless you can revoke quickly (Time‑to‑Kill becomes the security KPI).
- Stateless JWT validation is O(1) and locally cacheable; revocation is inherently stateful, and “where does that state live?” becomes an availability and latency design choice.
- “Instant logout” is rarely instantaneous across regions: you’re fighting event delivery lag, cache propagation lag, and clock skew while still meeting an auth-path budget (e.g., <5ms p99 overhead).
- If you fix revocation by calling the IdP on every request, your API availability becomes coupled to an external dependency (and your on-call will page on IdP incidents you don’t control).
- CAEP/RISC gives you push-based security events, but then your webhook ingestion, replay protection, idempotency, and ordering rules become part of your security boundary (and your pager rotation).
- Revocation needs policy semantics (what triggers kill, what scopes/apps/devices it affects), which creates stakeholder tension: product wants fewer forced re-logins; compliance wants “immediate”; SRE wants no new hard dependencies.
- Microservice sprawl (50+ services) turns “just check revocation” into a platform problem: inconsistent enforcement creates bypasses, and bespoke logic creates toil and rollout risk.
- Operationally, the hardest moment is a real compromise campaign: event bursts + cache hotspots can DoS your own auth tier; you need tiered fail modes and explicit approvals to fail-open vs fail-closed.
- Privacy/compliance constraints collide with debugging needs: you must be able to audit revocations without storing raw tokens or unnecessary PII, while still proving enforcement within an SLA/SLO.

## Mental Model
TTL is “waiting for the battery to die”: you accept access until the token’s `exp`. Revocation is “pulling the plug”: an external signal flips the system from “allowed” to “denied” before natural expiry. The engineering problem is building a reliable plug-pull mechanism that doesn’t require inspecting the battery on every use, and that behaves safely under failure and load.

- The “battery” maps to access token `exp` (and refresh token lifetime); the “plug” maps to an event-driven revocation state update (CAEP/RISC → cache).
- The “hand on the plug” is your webhook ingest + durable queue; if it’s slow or drops events, time-to-kill degrades and incident severity rises.
- The “appliance” is every API request path; you want local JWT verification + a fast revocation check that doesn’t add global dependencies.
- The “extension cord across rooms” is cross-region replication and cache propagation; it introduces seconds of inconsistency you must quantify and accept (or tighten for privileged scopes).
- Adversarial mapping: an attacker with a stolen refresh token can keep “recharging batteries” (minting new access tokens) unless revocation also blocks future refreshes, not just current access tokens.

## L4 Trap
- **Junior approach:** “Make access tokens 2 minutes and refresh constantly.” **Why it fails at scale:** pushes huge QPS to IdP/refresh endpoints and increases tail latency during spikes; you still have a window where a stolen access token is valid. **Friction/toil:** auth outages now impact every user every few minutes; on-call becomes dominated by refresh storms and rate-limit tuning.
- **Junior approach:** “Add a DB/Redis lookup to check revocation on every request.” **Why it fails at scale:** turns a low-latency local verify into a network hop + shared-state dependency; increases p99 and creates a global bottleneck. **Friction/toil:** every microservice now depends on the auth store; partial outages create cascading failures and brittle client retries.
- **Red flag:** “We’ll just introspect tokens centrally; security > latency.” **Why it fails at scale:** you’ve created a mandatory synchronous dependency and a single point of failure; availability/SLO becomes gated by the introspection service. **Friction/toil:** SRE pushback, frequent emergency exception requests, and pressure to bypass checks under incident conditions.
- **Red flag:** “Revocation is just deleting refresh tokens server-side; access tokens will expire soon.” **Why it fails at scale:** doesn’t stop current access tokens; also fails if refresh tokens are opaque but cached/replicated slowly across regions. **Friction/toil:** user-visible inconsistency (“I logged out but still can access from another device”) generates support tickets and escalations.
- **Red flag:** “We’ll store the full token in logs/DB for auditing and denylisting.” **Why it fails at scale:** raw token storage increases breach impact and violates minimization; also complicates rotation/retention. **Friction/toil:** compliance review churn, redaction bugs, and incident scope expansion when logs are accessed.
- **Junior approach:** “Implement per-service revocation logic; each team can decide.” **Why it fails at scale:** inconsistent semantics and gaps become bypass vectors; updates require coordinated rollout across dozens of services. **Friction/toil:** long-tail migrations, repeated security reviews, and unbounded on-call blast radius when one service mis-implements checks.

## Nitty Gritty
- **Protocol / Wire Details**
  - CAEP/RISC event delivery is push: IdP sends security events via HTTPS `POST` to your event delivery endpoint (webhook); you must treat it like an external-facing API with strict authn/z and abuse controls.
  - Wire header: `Content-Type: application/secevent+jwt` (enforce exact match or robust parser with allowlist; reject unknown content-types to avoid smuggling).
  - Payload is a signed JWT (JWS), commonly `alg=ES256`; verify signature using IdP JWKS and enforce algorithm allowlist (never accept `alg=none`).
  - Verify required claims: `iss` (exact expected issuer), `aud` (your webhook audience), `iat` (event issuance time), `jti` (unique event id for replay detection).
  - `events` claim is a JSON object keyed by event-type URI (e.g., `.../caep/event-type/session-revoked`); code must not assume only one key, and must ignore unknown keys safely.
  - JWKS handling: cache keys by `kid`; support rotation by re-fetching on unknown `kid` with rate limits/backoff; pin to expected `iss` to prevent key confusion across tenants.
  - Enforce clock skew windows on `iat` (e.g., accept within ±N minutes) with an explicit policy; skew too tight causes false drops during incident traffic; skew too loose increases replay window.
  - Transport: require TLS with modern ciphers; optionally require mTLS if IdP supports it—improves sender authentication but increases cert ops and rotation complexity (RRK: decide based on risk tier and operational maturity).
  - Anchor: `application/secevent+jwt` — narrows parser surface and routing.
  - Anchor: `events` claim — drives revocation semantics and fanout.
  - Anchor: `kid` rotation — common real-world outage trigger.

- **Data Plane / State / Caching**
  - Pattern A (epoch check): maintain `revoked_at:{issuer}:{sub}` → timestamp in Redis/memory; accept access token only if `token.iat >= revoked_at` (strictly, `>=` vs `>` depends on time granularity and clock skew policy—choose and test).
  - Epoch check is minimal state and scales: one key per principal; supports “revoke all sessions” for an account (password reset, HR termination, confirmed compromise).
  - Pattern B (denylist): maintain `deny:{issuer}:{sid}` or `deny:{issuer}:{jti}` for high-risk targeted kills; key TTL must exceed max token lifetime (and consider refresh minting windows).
  - Local hot cache: per-instance LRU for recently revoked `sub/sid` to avoid Redis on every request; negative caching for “not revoked” can reduce load but must be bounded to avoid extending exposure during revocation bursts.
  - Cache TTL guidance: keep revocation state longer than max session lifetime (e.g., 30 days + safety margin) to prevent “resurrection” after Redis eviction; manage memory via compact values and bounded keyspace.
  - Cross-region: replicate `revoked_at` via active-active Redis replication or event fanout per region; quantify replication lag and incorporate into time-to-kill SLO (RRK: accept seconds for low-risk, tighten for privileged).
  - Token fields to use: `sub` for user, `sid` for session identifier (if present), `aud`/`client_id` for app-specific kills; device identifier only if you already have a privacy-reviewed stable identifier.
  - Refresh token stopping: event-driven revocation must update the refresh-token issuance path too (e.g., deny refresh when `sub` epoch advanced, or rotate refresh token family); otherwise attacker keeps minting fresh access tokens post-“logout.”
  - Key design: `revoked_at` epoch uses a monotonic “latest wins” rule; on out-of-order events, set `revoked_at = max(current, event.iat)` to avoid rollback.
  - Anchor: `revoked_at epoch` — O(1) compare, low latency.
  - Anchor: `sid denylist` — surgical kill for high-risk sessions.

- **Threats & Failure Modes**
  - Replay attacks: attacker replays old CAEP/RISC events to force logouts (availability attack) or cause cache churn; mitigate by caching seen `jti` for a replay window ≥ max retry horizon.
  - Ordering bugs: out-of-order delivery can “unrevoke” if you naïvely set `revoked_at` to event `iat`; must enforce monotonic updates and idempotency.
  - Confused deputy: accepting events with wrong `iss`/`aud` lets another tenant’s IdP revoke your users; strict `iss` and per-tenant config, with alerts on unexpected issuers.
  - Key confusion: trusting JWKS URL from token header or untrusted metadata can let attacker choose verification key; JWKS endpoint must be configuration, not data-driven.
  - Cache stampede: if Redis slows, services thundering-herd on misses; apply request coalescing, circuit breakers, and bounded local negative caching.
  - Data-plane bypass: legacy services that only check `exp` will keep accepting tokens even after revocation; require gateway/shared lib enforcement and track “coverage” as a rollout metric.
  - Red flag: “We can’t drop any events; just block webhook until Redis write succeeds.” This couples ack latency to backend health, triggers IdP retries/amplification, and can cascade into an outage during compromise bursts.
  - Red flag: “If Redis is down, we’ll fail-open everywhere to keep uptime.” This silently disables the kill switch during the exact high-risk period; tiered fail mode must be explicit, reviewed, and observable.
  - Privacy failure: storing raw access/refresh tokens in revocation tables or logs increases breach impact; store only derived identifiers (`sub`, `sid`, hashed `jti` with salt) and minimal event metadata.
  - Compliance/audit failure: not retaining enough evidence of “who was revoked when and why” causes audit findings; retain event IDs, timestamps, actor/system trigger, and scope of revocation with strict retention policies.
  - Anchor: `time-to-kill` — security control effectiveness under incident load.

- **Operations / SLOs / Rollout**
  - Webhook handler behavior: ACK fast (e.g., <200ms) after validation + enqueue to durable queue; do not synchronously update all caches in the request thread.
  - Idempotency: use `jti` as idempotency key in durable storage; retries should be no-ops after first successful process.
  - Monitoring: track event delivery lag (`now - iat`), processing lag (enqueue→apply), replay rate (duplicate `jti`), and apply success rate; page on sustained lag that breaches kill SLO.
  - SLOs: define tiered kill-time SLOs (e.g., privileged scopes p95 < 30s, standard p95 < 60s) and error budgets; align with product/compliance expectations explicitly.
  - Fail mode policy: pre-define per-scope behavior when revocation signal path is degraded—fail-closed for admin/money-movement/write scopes; fail-open (with rate limits and anomaly detection) for low-risk reads; require approval + runbook for overrides.
  - Rollout: start with “observe-only” mode—compute revocation decisions and log metrics without enforcing, to find false positives and coverage gaps before flipping enforcement.
  - Back-compat: for legacy services, enforce revocation at gateway/edge authz layer; gradually migrate to shared auth library that performs local JWT verify + cache epoch check.
  - Incident playbook: during burst campaigns, protect Redis with admission control (limit writes/sec), shard by tenant/sub, and prioritize epoch updates over per-session denylists (risk trade-off: broader revocation but cheaper).
  - Industry Equivalent: “API Gateway/Edge proxy + shared auth middleware + Redis/Memcache + durable queue (Kafka/PubSub).”

- **Interviewer Probes (Staff-level)**
  - Probe: How do you set and validate `iat` skew windows without creating either false drops or replay exposure, and what metrics tell you it’s wrong?
  - Probe: Compare epoch-based revocation vs `sid/jti` denylist under 100k RPS: what are the cache key cardinalities, hit rates, and worst-case failure behaviors?
  - Probe: When webhook delivery is delayed 5 minutes in one region, what is your documented time-to-kill SLO story, and what do you fail-closed vs fail-open?
  - Probe: How do you stop future refresh minting without storing refresh tokens, while meeting privacy minimization constraints?
  - Probe: What’s your strategy for rolling this out across 50 services with no flag day, and how do you measure “revocation coverage” and bypass risk?

- **Implementation / Code Review / Tests**
  - Coding hook: Enforce `Content-Type == application/secevent+jwt` (case/params handling explicit) and reject everything else.
  - Coding hook: JWT verification invariants: `alg` allowlist, `iss` exact match, `aud` contains expected value, required claims present, and `kid` must map to cached/configured JWKS.
  - Coding hook: Implement `jti` replay cache with TTL ≥ max(IdP retry window, accepted `iat` skew) and unit-test duplicates/out-of-order delivery.
  - Coding hook: Idempotent apply logic: `revoked_at = max(existing, event.iat)`; add tests where older event arrives after newer event (must not decrease).
  - Coding hook: Redis key schema tests: ensure per-tenant isolation (`{issuer}:{sub}`), TTL > max session lifetime, and values are compact (int64 epoch seconds).
  - Coding hook: Request-path microbench: measure added latency of revocation check with local hot cache hit vs Redis miss; enforce budget (<5ms p99 overhead) with CI perf gate.
  - Coding hook: Chaos tests: drop 1% of events, delay 2 minutes, replay same `jti`, and rotate `kid` mid-stream; verify time-to-kill SLO and no outage amplification.
  - Coding hook: Failure-mode tests: simulate Redis partial outage; verify tiered behavior by scope (admin fails closed) and that “override” requires explicit config with audit log.
  - Coding hook: Logging/privacy tests: assert logs contain event `jti`, `iss`, revocation type, and timestamps—but never raw tokens; enforce via structured logging allowlist.

## Staff Pivot
- Architecture options under the stated constraints (100k RPS, <5ms p99 overhead, IdP may be unreachable):
  - **A)** Short TTL stateless JWTs + frequent refresh (simple client/server model, but shifts load to IdP and doesn’t guarantee immediate kill).
  - **B)** Central introspection on every call (strong enforcement, but turns auth into a synchronous dependency and crushes tail latency/availability).
  - **C)** Event-driven revocation (CAEP/RISC) + local JWT verification + cached revocation state (best balance; complexity moves to event ingestion + cache correctness).
- Decisive trade-off argument: pick **C** because it preserves request-path isolation (no synchronous IdP calls), meets latency budgets via local checks, and achieves near-real-time revocation bounded by event+cache propagation; the complexity is operational but can be measured and gamedays can harden it.
- Security realism: accept “seconds, not milliseconds” revocation for standard sessions if it avoids a brittle global dependency; tighten to fail-closed + faster propagation for privileged scopes and high-risk actions.
- RRK prioritization: explicitly rank risks—(1) attacker keeps access post-compromise, (2) auth tier outage due to revocation load, (3) forced relogins harming UX—and design controls that degrade safely under (2) while still mitigating (1) for high-risk scopes.
- What I’d measure (and page on):
  - Time-to-kill p50/p95/p99 by scope tier and region (measured end-to-end from event `iat` to first denied request).
  - Event delivery lag and processing lag; backlog depth in durable queue; webhook 2xx rate.
  - Revocation cache hit rate (local vs Redis) and incremental per-request latency; Redis CPU/mem and eviction rate.
  - False revokes / customer-impact metrics (unexpected logouts) and rollback time.
  - Coverage/adoption: % traffic behind gateway/shared lib enforcement; top legacy endpoints still only checking `exp`.
  - On-call toil: pages per week tied to revocation pipeline; mean time to mitigate cache overload.
- Stakeholder influence plan:
  - Align on tiered kill-time SLOs and fail-mode policy with Product (UX impact), SRE (dependencies and paging), and Legal/Compliance (auditability + “immediate” semantics defined as SLO).
  - Codify exception governance: which teams can request fail-open for specific endpoints, approval chain, and time-bounded waivers with monitoring.
- What I would NOT do (tempting but wrong):
  - Don’t require per-request introspection to IdP “for correctness”; you’ll violate latency budgets and inherit IdP outages.
  - Don’t centralize revocation checks in each microservice with bespoke logic; it guarantees drift, gaps, and endless migrations.
- Migration strategy framing: gateway/shared library first for coverage, then progressively enrich tokens (`sid`) and services for granular kills; avoid flag day by making revocation enforcement additive and observable.
- Incident posture: design for compromise bursts—rate limit event apply, prioritize epoch updates, and have a documented “security vs availability” toggle that is pre-approved for privileged scopes only.
- Tie-back: Describe a time you reduced a security dependency to protect availability while preserving control goals.
- Tie-back: Describe an incident where retries/backpressure amplified an outage; what guardrails would you add here?
- Tie-back: Describe how you got Product/SRE/Compliance to sign off on a tiered SLO and exception process.

## Scenario Challenge
- You issue JWT access tokens (`exp=1h`) plus refresh tokens (lifetime 30d); API traffic is **100k RPS**; auth-path overhead budget is **<5ms p99** including any revocation check.
- Requirement: upon confirmed compromise, revoke access within **60 seconds** across **all regions** (time-to-kill SLO must be measurable and auditable).
- Reliability constraint: APIs must remain available even if the IdP is unreachable; revocation cannot require synchronous IdP calls per request (no introspection gating).
- Security constraint: attacker may have stolen refresh tokens; you must stop both (a) current access tokens and (b) future refresh minting without waiting for natural expiry.
- Privacy/compliance constraint: revocation logs must be auditable (who/what/when/why), but must not store raw access/refresh tokens or unnecessary PII; retention limits apply.
- Developer friction constraint: 50 microservices; no per-service bespoke revocation logic; enforcement must be centralized (gateway) or via a shared auth library with consistent semantics.
- Migration/back-compat constraint: some legacy services only understand `Authorization: Bearer <jwt>` and validate only signature + `exp`; you must roll out without a flag day and without breaking existing clients.
- Hard technical constraint: cross-region replication can lag under load; you cannot assume strongly consistent revocation state globally within 60 seconds without designing for it explicitly.
- On-call twist: webhook receives a burst (possible compromise campaign), Redis CPU spikes, and auth checks begin timing out; you start failing requests—what load do you shed, what do you degrade, and where do you fail closed vs fail open?
- Policy/leadership twist: compliance insists “immediate,” SRE rejects new hard dependencies, product rejects broad forced relogins; propose tiered policies (by scope/action) and a governance process for exceptions and emergency overrides.
- Rollout twist: initial deployment shows increased 401s due to clock skew and malformed events; you must decide whether to loosen validation, add skew tolerance, or block events—under active incident pressure.
- Auditability twist: six months later, you must prove that a specific user’s sessions were revoked within the SLO across regions without exposing token material—what evidence exists and how is it queried?

**Evaluator Rubric**
- Demonstrates a clear architecture that meets <5ms p99 overhead by keeping request-path verification local and using cached revocation state, not synchronous IdP calls.
- Explicitly addresses both access-token invalidation and refresh-token future minting, including how revocation propagates and how “latest wins” prevents out-of-order regressions.
- Defines measurable SLOs (time-to-kill, event lag, cache hit rate, false revokes) plus paging thresholds and dashboards tied to user/security impact.
- Provides a failure-mode policy that is tiered by privilege and documented with approvals, including what happens during Redis degradation and event delivery disruption.
- Includes a rollout plan with backward compatibility (gateway/shared library, observe-only mode, coverage metrics) and a rollback strategy that preserves safety.
- Handles privacy/compliance with minimization (no raw tokens), auditable logs (event `jti`, timestamps, scope), and retention policies.
- Shows incident leadership: clear actions during burst load (backpressure, prioritization, circuit breakers) and communication trade-offs to Product/SRE/Compliance.
- Surfaces assumptions and ambiguity explicitly (replication lag, clock skew, IdP retry behavior) and proposes validation experiments/gamedays to harden the control before relying on it.