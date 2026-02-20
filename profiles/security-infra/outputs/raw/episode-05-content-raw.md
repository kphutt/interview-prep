## Title
**BeyondCorp: Building a Zero‑Trust Proxy**  
**Identity‑Aware Access Without the VPN (and without taking the company down)**

## Hook
- VPNs hard-code the trust boundary to “network location,” but users/devices/workloads are mobile; the real boundary is **identity + device posture + request context at L7**.
- Centralizing authn/z in a proxy removes per-app inconsistency, but turns the proxy into **tier‑0 infrastructure** with **latency, SLO, and blast-radius** implications.
- Layer‑7 policy (“who + what device + what risk + what path”) is precise, but the inputs (posture, risk, geo) are **distributed, stale, and ambiguous**; you must prioritize what to trust under partial failure.
- The proxy becomes the choke point for **OIDC redirects, token validation, session cookies, JWKS fetch**, and **policy evaluation**—each a dependency that can page you.
- “Identity assertion” to upstream apps can be secure (signed JWT + mTLS) or catastrophically insecure (spoofable headers); migration pressure often pushes teams toward the insecure shortcut.
- To hit **<20ms p99 added overhead**, you need aggressive caching and careful crypto choices—yet over-caching posture or policy can create **security gaps** and hard-to-debug incident behavior.
- Reliability tension: **fail-closed** is safer for admin/prod but can cause a company-wide outage during posture service degradation; **fail-open** preserves productivity but expands risk and must be auditable and bounded.
- Rollout constraint: you must migrate hundreds of apps with minimal code change; any required per-app library upgrade becomes a **multi-quarter coordination problem** and increases exception debt.
- Compliance/privacy tension: you need **1-year auditability** (policy version + decision factors) while minimizing logged URLs/query strings and stable device identifiers—this impacts debugging and incident response workflows.

## Mental Model
A VPN is passport control only at the border: once inside, movement is implicitly trusted. Zero Trust is passport control at every door: each request must present identity plus a “health certificate” (device posture), and each door decides based on current policy and risk. The hard part is making those door decisions fast, consistent, and resilient even when identity/posture systems are degraded.

- Map “every door” → **central identity-aware proxy** in front of many apps, enforcing uniform policy at **request time**.
- Map “passport” → **OIDC identity** (Authorization Code flow) producing an authenticated session and an identity assertion for upstream.
- Map “health certificate” → device posture from an **MDM/inventory source-of-truth**; cached but security-critical.
- Map “door rules” → policy evaluation on `(user, groups, device_tier, geo, risk, app, path)` with explicit exception/expiry governance.
- Failure/adversary mapping: an attacker with a stolen session cookie tries to “reuse the passport” from an unmanaged device; without **session binding to device posture / key material**, the proxy can be bypassed even if identity is correct.

## Common Trap
- **Red flag:** “Put a login page in front of each app.”  
  Fails at scale because 200+ apps implement auth differently (cookie flags, redirect URIs, token validation), creating inconsistent posture enforcement; causes developer friction via per-team rewrites and increases on-call toil debugging divergent auth bugs and SSO edge cases.
- **Red flag:** “Rely on IP allowlists/subnet ACLs once users are ‘connected.’”  
  Fails because IP is not identity and NAT/proxies blur attribution; increases operational burden maintaining allowlists during migration and breaks scripts when egress paths change, leading to brittle rollouts and emergency exceptions.
- “Just check the user, device can be added later.”  
  Fails because session theft and unmanaged endpoints become the common bypass; retrofitting posture later forces policy churn and back-compat hacks, creating reliability risk as you tighten controls under production load.
- **Red flag:** “Pass `X-User` / `X-Email` headers to apps; apps trust them.”  
  Fails because headers are trivially spoofed if any path bypasses the proxy or if proxy→backend link isn’t authenticated; creates pervasive incident scope (every app compromised) and forces rushed retrofits to mTLS/JWT verification.
- “Fail closed globally if any dependency is down.”  
  Fails because posture/JWKS/IdP hiccups become company-wide outages; generates paging storms and political fallout that pressures security to permanently weaken policy instead of implementing tiered degraded modes.
- “Cache posture indefinitely to meet latency.”  
  Fails because stale posture allows continued access after device compromise or management removal; causes incident ambiguity (was access legitimate?) and privacy/compliance risk if you hoard device identifiers longer than needed.

## Nitty Gritty
**Protocol / Wire Details**
- Proxy performs **TLS termination** at the edge, then establishes **new TLS** upstream; treat this as a security boundary shift and design for explicit trust contracts.
- Prefer **proxy→backend mTLS**: backend only accepts requests with a client cert issued to the proxy; prevents direct-to-backend bypass and reduces reliance on “source IP” checks.
- OIDC at the proxy: use **Authorization Code** flow; use **PKCE** where applicable (esp. public clients / browser flows) to reduce code interception risk.
- Validate `id_token` strictly: `iss` (exact match), `aud` (expected client_id), `exp`/`iat` (clock skew bounded), `nonce` (session-bound), and signature via JWKS.
- Session management: issue a proxy session cookie with `Secure; HttpOnly; SameSite=Lax/Strict` and explicit `Max-Age`; consider path scoping per-app to limit blast radius.
- Signed identity assertion to app: forward a **JWT** (e.g., `Authorization: Bearer <jwt>` or a dedicated header) containing `sub`, `email`, `groups`, `acr`/`amr`, `exp`, and `kid`; apps verify using JWKS and enforce `aud` = app identifier.
- Bind session to device: include a **device key/cert binding** claim (e.g., hash of device cert public key) or tie session to a device identifier validated via posture service; enforce re-auth/step-up on mismatch.
- For raw TCP (SSH/RDP): use a **TCP proxy/gateway** that performs an identity handshake out-of-band (browser OIDC or device cert auth) then maps identity to a short-lived connection authorization.
- Anchor: OIDC Auth Code + PKCE — reduces interception, standardizes proxy login.
- Anchor: proxy→backend mTLS — blocks header spoofing and backend bypass.
- Anchor: signed identity assertion (JWT) — enables uniform upstream verification.

**Data Plane / State / Caching**
- Cache compiled policies in-memory keyed by `(app_id, policy_version)`; compile to a fast predicate to keep p99 overhead low.
- Use **stale-while-revalidate** for policy and JWKS: serve cached values for a bounded staleness window while refreshing asynchronously to prevent thundering herds during rotations.
- JWKS caching key: `(issuer, kid)`; handle `kid` misses by refreshing JWKS once with rate limiting, then fail appropriately (don’t loop-refresh per request).
- Posture caching: cache per device for a short TTL (1–5 minutes) keyed by `(device_id, posture_version)`; posture_version increments on signal changes to support push invalidation.
- Implement **push invalidation** from posture/MDM system (or via event bus) for high-risk transitions (device unenrolled, disk encryption off) to cut the replay window without shrinking TTL to unusable levels.
- Negative caching: cache denies (e.g., “unknown device” / “inventory unreachable”) for very short TTL with jitter to protect posture backend from retries during incidents, while limiting lockout blast radius.
- Session replay window: keep session lifetime short for high-risk apps; for low-risk apps, longer sessions reduce IdP redirect load and improve UX—explicitly tie to risk tolerance and SLOs.
- Make device posture a **security-critical dependency**: treat wrong data (stale “healthy”) as worse than missing data; this drives degraded-mode choices.
- Anchor: stale-while-revalidate — protects p99 and avoids cache stampedes.

**Threats & Failure Modes**
- Trusting spoofable identity headers: if any caller can reach backend directly (misconfigured firewall) or proxy→backend is plaintext, attacker injects `X-User` to escalate; fix with mTLS + JWT verification + backend network isolation.
- Stolen session cookie replay from unmanaged device: if session is not bound to device key/posture, attacker logs in once then replays elsewhere; mitigate with device binding + step-up auth on posture mismatch + short `exp`.
- Over-caching posture: device gets unenrolled/compromised but cached “healthy” persists; mitigate with short TTL + push invalidation + “high-risk posture change” fast path.
- JWKS/key rotation failure: if proxy can’t fetch new keys, valid tokens start failing (auth outage) or, worse, stale keys accepted too long; set explicit max-staleness and alert on `kid` miss rate.
- **Red flag:** “Fail-open everywhere during posture outages.”  
  Turns a reliability incident into a security incident; also creates irreconcilable audit ambiguity unless you log degraded-mode decisions with `policy_version` and `degraded_reason`.
- **Red flag:** “Global fail-closed on posture/IdP blips.”  
  Converts partial dependency failure into full-company outage; forces exec escalations and leads to policy rollback without learning.
- Policy drift: exceptions without expiry become permanent backdoors; require exception tickets + owner + expiry + automated reaping.
- Privacy failure mode: logging full URLs/query params can leak tokens/PII; enforce structured audit logs with redaction at source, not in downstream log pipelines.
- Anchor: tiered failure behavior — balances safety vs availability per app risk.

**Operations / SLOs / Rollout**
- SLO targets drive architecture: **99.99% availability** implies multi-region active/active or fast failover; avoid single regional dependencies for posture/JWKS.
- Latency budget: enforce per-hop budgets; measure `added_latency_ms{p95,p99}` and break down into `authn`, `policy_eval`, `posture_lookup`, `upstream_connect`.
- Degraded-mode policy: define per-app risk tiers (prod/admin vs read-only) controlling behavior when posture/inventory is degraded: `fail-closed`, `fail-open`, or `step-up required`.
- Rollout safety: canary proxy changes by cohort/app; require instant rollback toggles (config flags) and freeze windows during key rotations/IdP changes.
- Parallel run with VPN: ensure deterministic routing (PAC files, DNS split-horizon, explicit endpoints) so debugging isn’t “sometimes VPN, sometimes proxy.”
- Metrics to page on: `policy_denied_total{reason}` spikes, `inventory_lookup_latency`/timeouts, `auth_redirect_rate` increases, `proxy_upstream_connect_errors`, and proxy CPU/GC (crypto load).
- Audit log requirements: include `policy_version`, decision inputs (user group, device tier, risk bucket, app/path category), decision outcome, and a request ID; omit query strings and minimize device identifiers (pseudonymize or hash with rotation).
- Compliance trade-off: 1-year retention for audit logs vs privacy minimization; implement field-level retention (keep decision metadata longer than raw request metadata).
- Industry Equivalent: ZTNA / Identity-Aware Proxy gateway + device posture service + policy engine (OPA/Rego/CEL).

**Interviewer Probes (Staff-level)**
- Probe: How do you prevent identity header/JWT spoofing when some apps can’t change code quickly?
- Probe: What’s your degraded-mode matrix when posture inventory is slow/partial—how do you bound risk and preserve 99.99% availability?
- Probe: How do you design caching (policy/JWKS/posture) to hit <20ms p99 without creating unsafe replay windows?
- Probe: What telemetry would you use to distinguish “true risk denies” from “misconfig/bug denies” during rollout?

**Implementation / Code Review / Tests**
- Coding hook: Enforce strict JWT validation (`iss`, `aud`, `exp`, `nbf`, `nonce`) with bounded clock skew; reject on missing claims.
- Coding hook: Implement JWKS fetch with singleflight + rate limiting; unit test `kid` miss storm behavior.
- Coding hook: Add replay protections for auth codes/state/nonce; test reuse attempts and parallel callback races.
- Coding hook: Session cookie invariants: `Secure`, `HttpOnly`, `SameSite`, scoped `Domain/Path`; negative tests for downgrade on HTTP.
- Coding hook: Posture cache correctness: TTL + jitter + push invalidation; tests for “unenroll then immediate deny” and “backend outage then recovery.”
- Coding hook: mTLS enforcement to upstream: backend rejects if client cert absent/invalid; integration test bypass attempts direct-to-backend.
- Coding hook: Degraded-mode toggle tests: simulate posture backend outage and verify per-app tier behavior + audit logging of degraded decisions.
- Coding hook: Log redaction tests: ensure query params and sensitive paths are not emitted; include structured fields (`policy_version`, `decision_reason`) for debugging.

## Staff Pivot
- Competing approaches:
  - **A) VPN + subnet ACLs:** simple operationally at first, but “inside=trusted” collapses under device compromise and remote workforce; lateral movement risk remains high and policy is coarse.
  - **B) Per-app authn/z:** flexible and avoids central choke point, but inconsistent across 200 owners, slow migration, and forces every team to become identity experts; on-call load spreads but doesn’t shrink.
  - **C) Central identity-aware proxy + posture service (+ TCP proxy adjunct):** consistent enforcement and minimal app change, but becomes tier‑0 and must meet strict SLO/latency.
- Decisive trade-off: pick **C** for most internal web/apps because **uniform enforcement + centralized observability** beats bespoke implementations; accept choke-point risk and mitigate with multi-region, caching, and explicit degraded modes.
- Non-HTTP reality: keep a **TCP proxy/gateway** path for SSH/RDP/jump hosts with identity-bound connection authorization; avoid “just keep VPN for legacy” as a permanent escape hatch.
- What I’d measure (and gate rollouts on):
  - **p99 added latency** and breakdown (authn vs posture vs upstream).
  - Proxy **error budget burn** and dependency SLOs (IdP, posture backend).
  - Posture cache **hit rate** and invalidation lag (security vs latency).
  - Deny-rate by reason: misconfig/rollout vs true policy risk; alert on spikes.
  - Time-to-onboard per app (self-serve success rate), and exception count/expiry compliance.
- Risk acceptance (explicit, auditable): allow **fail-open** only for low-risk read apps during posture outages, but require logs tagged `degraded_mode=true` and auto-expiring exceptions; never fail-open for prod/admin paths.
- Policy/compliance trade-off: keep 1-year decision logs with `policy_version` and reason codes, but avoid sensitive URLs/query params; accept reduced forensics detail in exchange for lower privacy risk and simpler compliance posture.
- Stakeholder alignment mechanics:
  - IT/MDM: define device tier signals and SLIs; agree on push invalidation for high-risk posture changes.
  - SRE: set proxy SLOs/error budgets, dependency budgets, and clear paging policies; prove degraded-mode prevents company-wide outages.
  - App owners: publish a “golden path” (mTLS + JWT verification) and a backward-compatible mode with clear deprecation deadlines.
  - Privacy/Legal: agree on log schema + retention + access controls; pre-approve redaction rules to avoid incident-time debates.
- What I would NOT do (tempting but wrong): mandate immediate per-app code changes for all 150 web apps before retiring VPN—this fails the 9‑month timeline and guarantees exception sprawl and brittle partial adoption.
- Tie-back: Describe a time you operated tier‑0 auth/proxy infrastructure—what SLOs and paging signals mattered most?
- Tie-back: Describe a migration where security controls tightened over time—how did you manage exceptions and expiry?
- Tie-back: Describe an incident involving a hard dependency outage—what degraded-mode decision did you make and how did you communicate risk?

## Scenario Challenge
- Retire VPN access for **80k employees** in **9 months** while meeting **99.99% availability** and **<20ms p99** proxy overhead end-to-end.
- App inventory: **150 web apps**, **30 internal APIs**, plus **legacy SSH/RDP** access to jump hosts; many apps cannot change code quickly (hard constraint against “just add JWT verification everywhere”).
- Security requirement: enforce `Allow IF (user group + device tier + geo/risk)` at L7 before traffic reaches apps; must reduce lateral movement compared to VPN.
- Replay defense requirement: prevent stolen session cookies from being replayed on unmanaged devices (forces session/device binding or step-up on posture mismatch).
- Privacy/compliance: keep auditable access logs for **1 year** (policy version + decision inputs), but avoid logging sensitive URLs/query params and avoid stable device identifiers unless necessary; impacts debugging during rollout and incidents.
- Developer friction constraint: **200 app owners**; must provide self-serve onboarding with minimal per-app changes (proxy does most work) and clear deprecation timelines for insecure modes (e.g., header trust).
- Migration/back-compat: must run VPN and ZT proxy in parallel; some scripts depend on IP allowlists—must offer a deprecation path (e.g., proxy egress IPs or identity-based alternatives) without locking into permanent allowlist debt.
- Reliability constraint: SRE refuses new hard dependencies without clear budgets; posture inventory backend and IdP must have defined SLIs, caching, and degraded behaviors to protect proxy SLOs.
- Incident/on-call twist: posture inventory backend has a **regional outage**; deny rate spikes; executives can’t reach critical tools. You must decide where to fail open/closed, what to cache, and how to contain blast radius while maintaining auditability.
- Multi-team/policy twist: Security demands “managed devices only,” HR requires contractor support, SRE demands no global fail-closed. You must propose tiered policy + exception governance with expiry and rollback triggers that leadership can accept.
- Hard technical constraint: many legacy apps cannot validate JWTs or mTLS quickly; you must still prevent header spoofing and bypass paths at the infrastructure layer during the migration window.
- Rollout constraint: changes must be reversible quickly; canary/rollback strategy must prevent widespread lockouts due to policy misconfig or posture signal bugs.
- Availability vs security tension: a strict posture check everywhere may violate 99.99% during upstream dependency flaps; a relaxed check everywhere violates the replay-defense goal—must choose per-app tiering and document risk acceptance.

**Evaluator Rubric**
- Establishes clear assumptions (traffic volumes, dependency SLIs, what “<20ms p99” measures) and identifies the hardest constraint that breaks textbook solutions (legacy apps + minimal code change).
- Produces an architecture that cleanly separates **control plane** (policy compilation, exception governance) from **data plane** (fast eval, caching, mTLS, JWT mint/verify) and addresses blast radius.
- Defines a degraded-mode matrix tied to risk tiers (prod/admin vs low-risk) with explicit audit logging of degraded decisions and bounded time windows.
- Specifies concrete telemetry and paging signals (deny-rate by reason, posture lookup latency, redirect rate, p99 overhead, key rotation errors) and connects them to rollout gates and rollback triggers.
- Handles privacy/compliance explicitly: structured logs with redaction, retention strategy, access controls, and incident-time debugging trade-offs.
- Provides a pragmatic migration plan: self-serve onboarding, compatibility modes with deprecation, parallel VPN/proxy routing clarity, and a plan to retire IP allowlists without breaking automation.
- Demonstrates incident leadership: immediate containment steps during posture outage, communication to execs, and a post-incident plan to reduce recurrence without weakening core security goals.
- Shows stakeholder influence: resolves Security vs HR vs SRE constraints via tiered policy + exception expiry + measurable risk acceptance, rather than vague “we’ll collaborate.”