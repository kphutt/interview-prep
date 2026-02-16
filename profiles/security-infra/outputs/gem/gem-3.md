============================================================
EPISODE 5
============================================================

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

## L4 Trap
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

============================================================
EPISODE 6
============================================================

## Title
**ALTS in Practice: Workload Identity mTLS for Service‑to‑Service Zero Trust**  
**Caller-ID for RPC at scale: secure by identity, survivable in outages**

## Hook
- East‑west traffic is where compromises become incidents: once a single pod is owned, IP-/subnet-based trust collapses and lateral movement becomes “normal traffic,” so containment depends on identity—not topology.
- Mutual auth + encryption must be *data-plane local*; any per‑RPC dependency on IAM/CA becomes an availability outage disguised as a “security check.”
- Workload identity is easy to specify (“only Payments can call Charge”) but hard to operate: cert minting, rotation, hot reload, and debugging turn into on-call toil without strong guardrails.
- Latency budgets are unforgiving: mTLS handshakes are expensive at p99 unless you enforce connection reuse (HTTP/2 pooling) and session resumption; “secure” that adds +10ms is a product rollback.
- Reliability tension: short-lived certs reduce impersonation window but create CA/identity-plane load and renewal storms; long-lived certs improve availability but widen blast radius after node compromise.
- Rollout safety is non-trivial: turning on strict mTLS instantly can strand legacy services and create cascading failures; you need staged enforcement (audit → permissive → strict) with measurable escape hatches.
- Debuggability becomes a first-class feature: without “who called me” and reason-coded handshake failures, teams will bypass controls (exceptions) to restore service during incidents.
- Compliance/forensics tension: you need auditable caller→callee logs retained 180 days without logging payloads/secrets; that pushes identity extraction into telemetry and increases privacy review surface.
- Organizational constraint: platform teams dislike sidecars, product hates latency regressions, security wants strictness—decisions must be driven by explicit metrics, risk acceptance, and exception policy with expiry.

## Mental Model
Instead of “you’re allowed because you’re in this building (subnet),” it’s “you’re allowed because you’re Alice from Payments (workload identity).” Every RPC is a phone call where both sides see verified caller ID, and the network can’t lie about who’s calling. The operational reality is you’re running a global caller-ID system: provisioning identities, rotating credentials, and keeping calls up when the identity system is partially down.

- Map “verified caller ID” → peer identity derived from the TLS handshake (SAN URI/DNS), not from app headers that an attacker can spoof from a compromised pod.
- Map “phone system directory” → IAM/authz policy mapping principals (e.g., `spiffe://prod/ns/payments/sa/charge`) to allowed RPC methods; versioned, reviewable, and deployable without app code changes.
- Map “call setup overhead” → TLS 1.3 handshake CPU + latency; mitigated by HTTP/2 connection pooling and session resumption so steady-state p99 stays within budget.
- Map “directory outage” → CA/identity-plane outage; design so existing calls continue (certs cached; renew before expiry with jitter) and your SLO doesn’t hinge on control-plane availability.
- Failure mode/adversary mapping: an attacker with any foothold can forge headers and spoof source IP to pivot; only cryptographic peer identity (mTLS) prevents “I am Payments” impersonation until credentials/node are contained.

## L4 Trap
- **Red flag:** “Just trust the VPC / cluster network.” Fails at scale because one compromised workload can pivot laterally within the same flat trust zone; it creates toil because every new service needs brittle IP allowlists and on-call firefights when autoscaling or region failover changes IPs.
- **Red flag:** “We’ll enforce security with namespace IP allowlists and shared API keys.” Breaks under churn (pods/ENIs rotate, NAT changes) and increases incident blast radius (shared keys leak = broad access); developers end up hardcoding secrets, rotating keys manually, and paging security during releases.
- “Put identity in headers (e.g., `X-Caller-Service`) and trust it.” At scale, any compromised service can spoof headers; it also causes reliability risk because different libraries/teams implement inconsistent header parsing and canonicalization, leading to production-only auth bugs.
- **Red flag:** “Make certs super short-lived everywhere (minutes) to be safe.” You will DoS your own CA/identity plane with renewal storms, create correlated outages during CA degradation, and force developers/SREs into constant incident response for renewal failures and clock skew.
- “Do per-request token introspection against IAM.” It fails latency/SLO budgets and introduces a hard dependency that turns IAM slowness into global tail latency and error spikes; developers will cache incorrectly or bypass checks to stop paging.
- “Roll out strict mTLS globally in one change.” At scale, unknown legacy and misconfigurations will cause cascading failures; you get emergency exception creep (“temporary” disables) that become permanent policy debt and audit risk.

## Nitty Gritty
**Protocol / Wire Details**
- Workload identity naming: represent the caller as a stable principal, e.g. `spiffe://prod/ns/payments/sa/charge`; treat namespace/env as part of the security boundary and keep names immutable across pod IP churn.
- Certificate minting request: workload generates keypair locally and submits a CSR (PKCS#10) to the node/identity agent; CSR must include SAN URI/DNS entries for the workload principal (not CN).
- Node attestation gate: CSR approval is bound to node identity (e.g., attested node agent) so a random pod can’t mint arbitrary principals; this is a control-plane trust root you must monitor and protect.
- Issuance response: CA returns leaf X.509 cert + intermediate chain + trust bundle (roots); workload stores key+cert and updates trust bundle atomically.
- mTLS handshake: TLS 1.3 with client authentication; verify certificate chain, signature algorithms, and validity window (`NotBefore/NotAfter`), then extract peer principal from SAN URI/DNS.
- Strict identity checks: reject peers with missing SAN, unexpected SAN type, or multiple conflicting identities; do not “fallback to CN” because legacy ambiguity becomes an impersonation vector.
- ALPN / protocol negotiation: for HTTP/2 gRPC, enforce ALPN `h2` to avoid protocol downgrade confusion that complicates telemetry and policy enforcement.
- Identity propagation: authorization decisions key off the authenticated peer principal from the TLS session; if you propagate identity into request context, mark it as derived (not caller-supplied) and prevent overwrite by headers/metadata.
- Method-level authz binding: policy should target RPC service/method names (e.g., `payments.Charge/Create`) rather than URL paths that are inconsistent across stacks; enforce at the proxy/library so apps don’t re-implement authz.
- Anchor: **SAN URI principal** — canonical workload identity source of truth.
- Anchor: **PKCS#10 CSR** — issuance boundary; validate requested SANs.
- Industry Equivalent: service mesh mTLS with SPIFFE/SPIRE identities; Envoy SDS; Istio/Linkerd-style mutual TLS.

**Data Plane / State / Caching**
- Credential cache: store current cert+key in memory and on disk (optional) with strict file permissions; support atomic swap to avoid serving mixed key/cert pairs during rotation.
- Rotation policy: renew at ~50% lifetime with jitter per instance to prevent thundering herd; treat renewal as a background task and alert on sustained failures, not transient retries.
- Hot reload: proxies/libraries must reload certs without process restart; otherwise rotation becomes an availability event (deploy) and raises developer friction.
- Trust bundle updates: cache trust roots/intermediates with versioning; roll forward before rotating leafs to avoid chain validation failures during CA transitions.
- Handshake amortization: use HTTP/2 connection pooling (keepalive) so handshake is not on the request critical path; enforce max concurrent streams and connection reuse to control latency and CPU.
- TLS session resumption: enable session tickets or PSK resumption to reduce CPU on reconnects; monitor resumption rate to detect misconfig or ticket key rotation issues.
- Cache keying for authz: if doing policy evaluation in-proxy, cache allow/deny decisions by (peer principal, local service, method) with short TTL; invalidate on policy version change to avoid stale authorization.
- Replay/TOCTOU window: avoid per-request “freshness” checks that depend on the CA; instead bound risk via cert lifetime + rotation and rely on rapid quarantine for compromised nodes.
- Anchor: **Connection pooling** — keeps TLS cost off p99 path.

**Threats & Failure Modes**
- Explicit threat: without workload identity, a compromised pod can spoof source IP and pivot via allowed subnets; with mTLS, attacker must steal usable credentials (node agent keys, leaf cert+key) to impersonate until expiry.
- Compromised node agent: if the node attestation/agent is owned, attacker can mint certs for workloads on that node; containment requires node quarantine + revocation strategy (or short cert lifetime) and rapid scheduling evacuation.
- Stolen leaf key material: impersonation lasts until cert expiry; risk acceptance ties directly to cert lifetime—shorter reduces window but increases renewal toil and outage risk.
- **Red flag:** “Rely on revocation (CRL/OCSP) in the hot path.” At scale, revocation checks add latency and external dependencies; during outages you either fail-open (security gap) or fail-closed (availability outage).
- **Red flag:** “Log full certificates for debugging.” This leaks unnecessary identity/infra details and creates compliance/privacy risk; it also bloats logs and increases retention cost—log the extracted principal + reason codes instead.
- Clock skew gotcha: cert validity errors often come from bad time sync; treat NTP/chrony as part of the identity SLO and page the infra owner when skew crosses a threshold.
- Failure mode: trust bundle mismatch during CA rotation causes handshake failures across a fleet; mitigate via staged rollouts (trust-first, then leafs) and metrics on chain validation failures by issuer.
- Header confusion: if apps/proxies accept both “mTLS-derived principal” and “header principal,” an attacker can overwrite identity; enforce single-source identity and strip/overwrite user-provided identity headers at ingress to the service.
- Policy misbinding: authorizing by namespace rather than principal (or by DNS names that can be reassigned) creates privilege creep; prefer stable SPIFFE-like principals tied to workload service accounts.

**Operations / SLOs / Rollout**
- On-call goal: keep steady-state success independent of CA availability; during CA outage, existing certs must remain valid long enough to maintain SLO while paging the identity/CA team, not every product team.
- Cert lifetime choice as risk dial: e.g., accept ~24h lifetimes to survive CA incidents; require compensating controls (node hardening, rapid quarantine runbook, anomaly detection on unusual caller principals).
- Rollout stages: (1) audit-only: collect peer principals and “would-have-denied” stats; (2) permissive: allow plaintext with metrics and targeted exemptions; (3) strict: enforce mTLS required per namespace/env (prod first).
- Exception policy: allow explicit owners + sunset dates + automated reporting of outstanding exceptions; treat exceptions as risk debt with quarterly review to satisfy compliance without blocking delivery.
- Metrics (reason-coded): `mtls_handshake_failures{reason}`, `cert_renewal_errors{cause}`, `rbac_denies{method,peer}`, `cert_expiry_seconds` (min/quantiles), `tls_handshake_cpu_seconds`, `session_resumption_rate`, and `h2_connection_reuse_ratio`.
- Logging for audit (180 days): emit structured logs “service X principal called service Y principal method Z outcome allow/deny” without payload; ensure log access controls and retention align with privacy/compliance.
- Paging triggers: page on sustained handshake failure rate or cert expiry < N hours across a shard; avoid paging on single-instance renewal failures to reduce noise and prevent exception sprawl.
- Blast radius control: enforce by namespace/env with canaries per region; ability to rollback to permissive mode quickly (feature flag) is part of operational excellence.
- Anchor: **Reason-coded handshake metrics** — debuggability prevents unsafe exceptions.

**Interviewer Probes (Staff-level)**
- Probe: How do you choose cert lifetimes and renewal thresholds to balance CA outage survival vs compromise window, and what metrics tell you it’s working?
- Probe: Where exactly do you extract and store the peer principal (proxy, library, app), and how do you prevent header/metadata spoofing across frameworks?
- Probe: What failure modes do you expect during CA root/intermediate rotation, and what staged rollout plan prevents global handshake failures?
- Probe: With a +3ms p99 budget, what concrete mechanisms keep mTLS off the critical path (connection pooling, resumption), and how do you enforce them platform-wide?
- Probe: If node attestation is the minting gate, what is your incident containment strategy when a node is compromised and can mint identities?

**Implementation / Code Review / Tests**
- Coding hook: Enforce SAN-only identity: reject certs missing SAN URI/DNS or containing unexpected principal formats; never fall back to CN.
- Coding hook: CSR validation: ensure requested SAN exactly matches workload identity assigned by the node agent; deny “arbitrary SAN” requests even if CSR is well-formed PKCS#10.
- Coding hook: Hot-reload invariant: rotation must not require process restart; add a test that rotates certs mid-traffic and asserts no connection drops beyond acceptable retry budget.
- Coding hook: Connection reuse test: load test verifies HTTP/2 pooling keeps handshake rate below threshold per instance; fail build if handshake/QPS ratio regresses.
- Coding hook: Session resumption correctness: test ticket key rotation does not disable resumption fleet-wide; monitor resumption rate and handshake CPU.
- Coding hook: Clock skew simulation: integration test with skewed system time causes `NotBefore/NotAfter` failures; verify alerting routes to infra/NTP owner and rollback plan is documented.
- Coding hook: Policy cache correctness: cache decisions by (peer principal, method) with TTL; test invalidation on policy version bump to avoid stale allows/denies.
- Coding hook: Telemetry privacy: ensure logs include peer principal + method + allow/deny + reason code; verify payload and full cert PEM are never logged (unit test on log sanitization).
- Coding hook: Rollout safety: feature-flag strictness per namespace; test rollback to permissive mode restores traffic without redeploy.

## Staff Pivot
- Competing approaches under these constraints:
  - A) IP allowlists + shared secrets: low latency and simple initially, but brittle under autoscaling/multi-region and enables lateral movement; operationally it devolves into exception sprawl and key rotation incidents.
  - B) Per-request JWT at app layer: fine-grained and mesh-free, but adds per-service parsing/validation overhead, inconsistent libraries, and high developer friction—plus token issuance/verification failure modes on every request.
  - C) **Workload identity mTLS via mesh/library**: uniform mutual auth + encryption and centralized policy enforcement; introduces identity-plane operations, but keeps per-RPC overhead low with connection reuse and avoids per-team code changes.
- Decision: pick **C** as default for 3,000 services because it eliminates topology-based trust and standardizes authN at L4/L7 boundary; then add method-level authz in-proxy for sensitive RPCs where needed.
- Decisive trade-off argument: accept identity/control-plane complexity *once* (with SRE-grade reliability) to reduce system-wide ambiguity and lateral movement risk; mitigate latency with pooling/resumption and mitigate toil with reason-coded metrics + self-serve debugging.
- Reliability stance: no per-RPC calls to CA/IAM; design for “CA outage == degraded renewals, not traffic outage” by caching certs locally and choosing lifetimes that cover realistic control-plane outages.
- Risk acceptance: accept ~24h-ish cert lifetimes initially to survive CA incidents and reduce renewal storms; compensate with node hardening, strong isolation, and rapid quarantine procedures on suspected compromise.
- What I’d measure to keep everyone honest:
  - Security efficacy: unauthorized call attempts blocked (`rbac_denies`), reduction in lateral movement paths (policy coverage), exception count and mean age.
  - Performance: p99 latency delta per hop, handshake CPU per instance, handshake rate/QPS, session resumption rate, connection reuse ratio.
  - Reliability/toil: cert renewal success rate, CA error budget consumption, MTTR for “mTLS broke prod,” pages per week attributable to identity issues, and rollback frequency.
- Rollout plan as a risk-management tool: audit → permissive → strict by namespace/env (prod first), with canaries per region and automated exemption workflow with expiry to avoid permanent bypass.
- Stakeholder alignment mechanics:
  - Product: commit to +3ms p99 budget with concrete performance controls (pooling/resumption) and an SLO-backed rollout; show canary dashboards.
  - Platform/SRE: treat CA/identity plane as a tier-0 dependency with explicit SLOs, capacity planning for renewal storms, and runbooks; provide “who am I / who called me” tooling to reduce pagers.
  - Legal/Compliance/Privacy: design caller→callee audit logs without payloads, with retention/access controls; document exception process and periodic reviews.
- What I would NOT do (tempting but wrong):
  - Fail-closed globally on CA/OCSP checks in the request path (turns identity plane blips into global outages).
  - Require every team to implement app-level JWT checks this half (adoption failure, inconsistent security, and debugging chaos).
  - Enforce ultra-short cert lifetimes before proving renewal SLO and clock sync health (self-inflicted DoS).
- Tie-back: Describe a time you chose a security control that preserved availability during control-plane outages; what metrics justified it?
- Tie-back: Describe how you handled exception policy (owner + expiry) without creating permanent bypasses under on-call pressure.
- Tie-back: Describe a rollout where latency regressions blocked security enforcement; how did you instrument and negotiate trade-offs?

## Scenario Challenge
- You operate **3,000 microservices** across **5 regions** with **2M RPS** east‑west; auth overhead budget is **+3ms p99** end-to-end for the added controls.
- Current controls are **namespace IP allowlists** plus some **shared API keys**; you’ve already had a **lateral movement incident** (attacker pivoted inside the cluster).
- Requirement: enforce **mutual authentication + encryption** for service-to-service traffic; source IP must be irrelevant to authorization.
- Requirement: **no per-RPC calls** to IAM/CA/identity services; authentication must keep working through identity-plane outages (control plane may be degraded).
- Requirement: support **per-method authorization** for sensitive RPCs (e.g., allow principal X to call `payments.Charge/Create` but not other methods).
- Privacy/compliance constraint: produce **auditable “service X called service Y” logs** retained **180 days**; do **not** log payloads or secrets; ensure logs are access-controlled and reviewable.
- Developer friction constraint: most teams **will not change application code** this half; solution must be **sidecar/mesh or drop-in library** with centralized defaults and minimal per-service config.
- Migration/back-compat constraint: **10% legacy raw TCP** services cannot speak TLS for **6 months**; you must design **bridging** and **phased enforcement** without creating a permanent plaintext bypass.
- Hard technical constraint: product leadership refuses visible tail-latency regression; platform leadership dislikes sidecars; security demands strict mTLS—your proposal must include enforceable metrics and a policy/exceptions mechanism.
- Incident/on-call twist: **cert renewal fails** for a subset of workloads due to **clock skew**; error rates spike in one region. You must define rollback levers, blast-radius containment, and how to avoid “turn it off globally” as the only safe move.
- Reliability twist: CA experiences partial outage during peak; renewals are failing but existing certs are still valid—decide paging thresholds, comms, and how to prevent cascading restarts from exhausting cert TTL.
- Rollout twist: a subset of services uses long-lived HTTP/1.1 connections without pooling; handshakes spike after a deploy. You need enforcement that doesn’t accidentally amplify reconnect storms.
- Policy twist: security wants “no exceptions,” but business needs temporary exemptions for the TCP legacy set; define exception ownership, expiry, and audit reporting without blocking the migration.

**Evaluator Rubric**
- Clear assumptions and prioritization: explicitly ranks risks (lateral movement vs outage risk) under ambiguity and states what is accepted temporarily (e.g., cert lifetime, legacy bridges).
- Architecture coherence: clean separation of control plane (issuance/policy distribution) vs data plane (cached credentials, local authz) with no per-RPC dependencies.
- Latency realism: identifies handshake amortization (HTTP/2 pooling, session resumption) and proposes concrete metrics/guardrails to stay within +3ms p99.
- Operational excellence: defines SLOs for identity plane, paging triggers, dashboards with reason-coded failures, and a rollback strategy that limits blast radius (namespace/region canaries).
- Migration/compat plan: staged enforcement (audit→permissive→strict), explicit handling for raw TCP (bridging with sunset), and prevents permanent plaintext “shadow paths.”
- Incident response depth: addresses clock skew renewal failures with containment, owner routing (NTP as identity dependency), and avoids global disablement as default.
- Policy/compliance handling: auditable caller→callee logs without payloads, retention/access controls, and an exception process with owner+expiry and periodic review.
- Stakeholder influence: proposes a decision framework that aligns product/platform/security with measurable commitments and explicit trade-offs rather than ideology.