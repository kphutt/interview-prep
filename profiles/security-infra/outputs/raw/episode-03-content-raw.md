## Title
Mobile OAuth Without Confused Deputies: Universal/App Links + PKCE Under Real SLOs

## Hook
- Mobile OAuth breakages at scale usually aren’t “crypto failed”; they’re “the OS handed the redirect to the wrong app,” which turns a correct protocol into a confused-deputy incident.
- Custom URL schemes (`myapp://callback`) are globally claimable on-device; any installed app can “wear the uniform,” so redirect capture becomes a probabilistic, user-dependent security boundary.
- Proving *app identity* requires an OS-verifiable binding between an app’s signing identity and a domain (Universal Links / App Links); that pushes security correctness into infra ownership (DNS/TLS/CDN) and multi-team change control.
- PKCE fixes code interception for public clients, but it does not fix “wrong app got the redirect” UX/confusion; you need both, and you need to know which failure you’re debugging on-call.
- Latency targets (e.g., p95 <1.5s) fight the reality of system browser hops, cold starts, TLS handshakes, and IdP latency spikes; you have to budget time per funnel stage and decide what to fail fast vs retry.
- Availability targets (e.g., 99.99%) are dominated by *dependencies you don’t own*: IdP uptime/latency, CDN behavior, OS caching of association files; your SLO needs explicit error budgets and clear “who pages whom.”
- Domain association files are “prod config”: a 302 redirect, wrong `Content-Type`, or caching regression can break login for hours due to OS caching—even after you fix the origin—creating high-severity incidents with limited mitigations.
- Privacy/compliance demands (fraud-auditable logs, no raw codes/tokens, minimal device identifiers) directly constrain observability; without deliberate event modeling you either lose debuggability or violate policy.
- Standardizing across multiple mobile teams and branded apps forces a “golden path” (SDK + CI validation + IdP registration hygiene); otherwise you accumulate divergent redirect strategies that are impossible to audit or deprecate safely.

## Mental Model
A uniform isn’t identity; a badge is. In mobile OAuth, a redirect URI looks like a uniform—any app can claim it—so the OS can accidentally empower the wrong “deputy” to receive an authorization response. Universal/App Links are the badge check: the OS verifies that the app’s signing identity is explicitly bound to a domain before delivering the redirect.

- The “uniform” → `redirect_uri` (especially custom schemes): it signals intent, not identity.
- The “badge check” → OS link verification using domain-hosted association metadata + app signing identity (bundle ID / package + cert fingerprint).
- The “bouncer” → iOS/Android link resolver that decides whether to open the app or stay in the browser; its caching/heuristics become part of your reliability model.
- Adversarial mapping: a malicious app “wears the same uniform” by registering the same URL scheme, intercepts codes, and creates user confusion that support/on-call must triage without clear telemetry.

## Common Trap
- Red flag: “Use `myapp://callback` (custom scheme) because it’s easy.” It fails at scale because scheme namespace is not exclusive; installed apps can collide and intercept, turning authentication into a device-dependent lottery; it drives chronic support tickets and hard-to-reproduce on-call escalations (“only happens on some phones”).
- Red flag: “Hide a `client_secret` in the app and treat it like a confidential client.” It fails because mobile binaries are extractable; you end up in a key-rotation treadmill after the first leak, plus brittle obfuscation/scan tooling that slows releases and creates false confidence.
- Red flag: “Use an embedded WebView to control the flow.” It fails because it breaks SSO and cookie sharing, increases phishing surface, and can trigger IdP/platform blocks; operationally it causes OS-update regressions and forces app hotfixes instead of server-side mitigations.
- “Skip Universal/App Links because the web/domain team is slow.” It fails because you never actually establish app identity; teams ship inconsistent workarounds (extra prompts, custom schemes, manual copy/paste) that balloon developer friction and still don’t meet the redirect-hijack requirement.
- “Allow wildcard redirect URIs so multiple apps/environments work.” It fails because you can’t reason about which app/path is authorized (classic confused-deputy footgun) and audits become non-actionable; it increases incident blast radius and makes deprecation/migration nearly impossible.
- “PKCE is enough, so omit strict `state`/`nonce` handling.” It fails because CSRF/account-swapping and token replay become plausible, and the failures present as “wrong account logged in” which is high-cost to investigate under privacy constraints.

## Nitty Gritty

**Protocol / Wire Details**
- Use OAuth for Native Apps BCP: Authorization Code + PKCE in a *system browser* (iOS `ASWebAuthenticationSession`, Android Chrome Custom Tabs); this preserves SSO and leverages OS-level isolation instead of inventing one in-app.
- Authorization request must include: `response_type=code`, `client_id`, exact `redirect_uri` (claimed HTTPS), `scope`, `state` (CSRF), plus PKCE `code_challenge` and `code_challenge_method=S256`; for OIDC add `nonce` and validate it in the ID Token.
- PKCE details that matter in code review: generate `code_verifier` with CSPRNG (43–128 chars), compute `code_challenge = BASE64URL(SHA256(code_verifier))` with no padding; reject `plain` in policy for anything beyond low-risk.
- Token exchange: `POST /token` with `Content-Type: application/x-www-form-urlencoded`; include `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier` (and `client_id` if the server requires); do **not** send `client_secret` for public clients.
- OIDC ID Token validation is not “optional hardening” when `nonce` is used: verify JWT signature via JWKS (`kid` lookup), enforce expected `alg` (e.g., RS256/ES256 as configured), check `iss`, `aud`, `exp`, and match `nonce` to the stored value.
- Redirect URI strategy: prefer `https://login.example.com/oauth/callback/<brand>` claimed by the app; register exact values in the IdP (no wildcards), so you can audit “which binaries can receive which redirects.”
- iOS Universal Links: enable Associated Domains entitlement `applinks:login.example.com`; host `https://login.example.com/apple-app-site-association` (no redirects) containing `applinks.details[].appID` (TeamID.BundleID) and `paths` allowlist.
- Android App Links: declare `android:autoVerify="true"` intent-filter for `https://login.example.com/...`; host `https://login.example.com/.well-known/assetlinks.json` with `target.package_name` and `sha256_cert_fingerprints` for the signing cert.
- Association endpoints must be boring HTTP: `200 OK`, `Content-Type: application/json`, no auth, no geo/locale negotiation, no 3xx; otherwise the OS will treat the domain as unverified and silently fall back to the browser.
- Anchor: PKCE S256 — Stops code redemption after redirect interception.
- Anchor: Claimed HTTPS redirect — OS enforces domain→app binding.

**Data Plane / State / Caching**
- `state` and `nonce` should be high-entropy, single-use, and time-bounded (e.g., 5–10 min); store only what you need to resume UX (e.g., return route), and treat reuse as suspicious signal for fraud and as a correctness bug.
- Persist `code_verifier` across the browser hop (process death happens): store in Keychain/Keystore keyed by an internal `login_attempt_id`, expire aggressively, and wipe on success/cancel to reduce forensic/log exposure.
- OS caches association files aggressively and opaquely; even after fixing the origin, devices may remain “stuck” for hours—plan for overlap windows during rollout and avoid relying on instant invalidation as an incident mitigation.
- CDN and origin caching knobs still matter: serve stable ETags, avoid `Vary` that splits caches, and pin these paths to a “no redirect rules apply” config; a single CDN change can become a global auth outage.
- Privacy-preserving correlation: log an opaque `login_attempt_id` and funnel stage transitions; if you need to correlate with `state`, log only an HMAC(state) (server-held key) so auditors can validate integrity without storing raw values.
- Anchor: AASA file — iOS domain verification source-of-truth.
- Anchor: assetlinks.json — Android verification binds package to cert.

**Threats & Failure Modes**
- Custom URL scheme hijack: attacker app registers the same scheme and receives the authorization response; user may not notice the wrong app opened, and support sees “login loops” or “wrong account” symptoms without clear telemetry.
- PKCE mitigates *code theft* but not *app impersonation*: a malicious app can still manipulate UX (open/close browser, present spoofed screens) even if it can’t redeem the code—risk model must separate credential phishing vs code interception.
- Wildcard or overly-broad redirect URI registration creates a confused deputy: it expands the set of authorized recipients beyond what you can reason about, making both abuse detection and compliance attestations weak.
- Missing/incorrect `state` validation shows up as rare, high-impact account swap incidents; at scale, “rare” becomes daily noise that burns on-call time under privacy constraints.
- Association file failures (302, wrong MIME type, stale CDN, wrong cert fingerprint after signing key rotation) cause the OS to stop opening the app, trapping users in the browser; due to caching, the blast radius persists beyond the deployment window.
- Embedded WebView flows degrade SSO and can be blocked by IdPs/platforms; operationally, you’ll chase OS/browser behavior changes with app releases (slow) instead of server mitigations (fast).
- Red flag: IdP accepts wildcard `redirect_uri` or scheme redirects for privileged scopes.
- Anchor: Confused deputy — Delegation to the wrong app is the root bug.

**Operations / SLOs / Rollout**
- Define separate SLIs for: (1) browser launch, (2) verified-link open-to-app success, (3) `state` validation, (4) token exchange success, (5) overall login completion; page on burn-rate for (2) because it often indicates CDN/association breakage.
- Latency budgeting: instrument client-side timestamps (monotonic clock) for each stage; p95 <1.5s usually means you must reduce server latency and retries, not “optimize crypto,” and you need an explicit “timeout → user message” policy.
- Synthetic monitoring: continuously fetch and validate AASA/assetlinks through the *same CDN path* clients use; assert `200`, no redirects, JSON contains expected appIDs/fingerprints; alert within minutes—before users report.
- Incident mitigation playbook for “AASA 302”/verification regressions: rollback CDN rule, serve static association from a known-good origin, and communicate a clear user workaround (continue in browser) that preserves security (no insecure scheme fallback for privileged scopes).
- Migration/back-compat: keep `myapp://callback` only for legacy versions behind an explicit allowlist with owner+expiry; require PKCE for legacy too, and measure legacy share to drive deprecation with product/support alignment.
- Compliance: log only stage + error class + coarse app/device attributes (OS/app version, brand), never raw auth codes/tokens or full redirect URLs; define retention for fraud audit vs privacy, and make it enforceable (central logging filters + tests).

**Interviewer Probes (Staff-level)**
- Probe: How do you persist and securely garbage-collect `code_verifier`/`state` across system-browser hops and process death?
- Probe: What is your fastest detection signal that Universal/App Links verification is failing globally (before support tickets), given OS caching?
- Probe: How do you design IdP redirect registrations for three branded apps so audits are trivial and migration is safe?
- Probe: Where do you enforce “verified link + PKCE required for privileged scopes”: client SDK, IdP config, or both—and how do you prevent drift?

**Implementation / Code Review / Tests**
- Coding hook: Enforce `code_verifier` length/charset and `S256` only; reject `plain` in config for high-risk clients.
- Coding hook: Store `code_verifier`/`nonce` keyed by `login_attempt_id` in Keychain/Keystore with TTL; delete on success/cancel; handle multiple concurrent login attempts deterministically.
- Coding hook: Strict redirect handler: accept only expected `https://login.example.com/...` host+path; reject unexpected params; require `state` presence and single-use.
- Coding hook: Add negative tests for duplicate/out-of-order redirects (replay) and for “redirect arrives with unknown state” (should fail closed with user-safe error).
- Coding hook: Validate ID Token JWT: enforce expected `alg`, match `kid` in JWKS, check `iss/aud/exp/nonce`; unit-test clock-skew handling and missing-claim failures.
- Coding hook: CI/CD check that fetches AASA/assetlinks via CDN URL and validates: 200, no 3xx, `Content-Type` json, schema contains current appIDs/fingerprints.
- Coding hook: Log-scrubbing test: ensure logs never contain raw `code`, `access_token`, `refresh_token`, `id_token` (regex + structured logging assertions).

## Staff Pivot
- Competing approaches to evaluate explicitly (and align on *why*, not “preference”):
  - **A)** Custom scheme redirect + embedded WebView: minimal cross-team dependencies, fastest initial ship, but weak app identity, poor SSO, and high long-term incident risk.
  - **B)** System browser + PKCE + Universal/App Links: stronger identity binding, best-practice alignment, but requires domain association files, IdP hygiene, and real ops ownership.
  - **C)** Add optional device/app attestation for the highest-risk actions: stronger signal against compromised devices, but increases latency, failure modes, and cross-platform complexity.
- Default baseline: choose **B** for all apps/scopes because it removes an entire class of redirect-hijack bugs and makes audits tractable; treat C as a scoped add-on where risk justifies friction (e.g., money movement).
- Decisive trade-off argument: “domain association + verified links” is *ops work up front* that prevents *unbounded* downstream toil (support + incident response + rotating fake ‘secrets’), and it scales across multiple teams via shared infra/SDK.
- Risk acceptance (explicit): accept initial setup friction (domain ownership, association file correctness, CI checks) to eliminate confused-deputy ATOs; do **not** accept “secrets in apps” as compensating control because extraction is inevitable and incident blast radius is huge.
- What I’d measure to steer decisions under ambiguity:
  - p50/p95/p99 login completion latency, and stage breakdown (browser, redirect, token exchange).
  - Verified-link open success rate by OS/app version (and sudden deltas).
  - Token exchange error rate by IdP region and client version.
  - Support tickets by error class (verification failure vs state failure vs network).
  - Security signals: suspected hijack attempts (unexpected redirect hosts, state mismatches) and frequency of legacy-scheme usage.
  - Operational toil: pages/week attributable to association/CDN/IdP issues, and MTTR.
- Rollout safety: ship B behind server-controlled gating (scoped to app versions) and add synthetic monitoring first; treat association files like production config with staged rollout and rollback.
- Stakeholder alignment plan: define a “golden path” mobile auth SDK (system browser + PKCE + telemetry), plus an automated validator in CI that checks AASA/assetlinks and IdP redirect registration diffs; require approvals for exceptions with expiry.
- Ownership model: web/domain owners own uptime/correctness of association files and CDN rules; identity team owns IdP redirect allowlist and scope policy; mobile teams own client implementation and telemetry—document this as an SLO contract.
- Policy/compliance trade-off: enforce “PKCE + verified link required” for privileged scopes even if it reduces completion rate initially; use error budget + measured funnel impact to justify iterations instead of weakening the control.
- What I would NOT do (tempting but wrong): allow wildcard redirects or re-introduce custom schemes as a “temporary fix” during incidents; it creates permanent debt and makes the next incident worse.
- Tie-back: Be ready to describe a time you standardized an auth “golden path” across teams (what levers worked).
- Tie-back: Be ready to explain an incident where a config/CDN change broke auth and how you reduced MTTR.

## Scenario Challenge
- You’re launching a fintech mobile app; p95 login must be **<1.5s** end-to-end on typical networks, and availability target is **99.99%** (error budget is small, so dependency failures matter).
- Security requirement: prevent redirect hijack/app impersonation assuming attackers can install malicious apps on the same device; “it’s HTTPS” is not sufficient if the OS can route to the wrong app.
- Baseline architecture must follow modern guidance: Authorization Code in **system browser** + **PKCE**; embedded WebViews are disallowed (product wants SSO and platform compliance).
- Redirect URI must be **claimed HTTPS** using Universal/App Links bound to `login.example.com`; custom schemes are considered legacy-only.
- Privacy/compliance constraints: logs must support fraud audits (who attempted what, when, outcome) but must not store raw auth codes/tokens or stable device identifiers beyond what’s necessary.
- Developer friction constraint: multiple mobile teams ship **three branded apps** sharing one IdP tenant; you need a standardized, audit-friendly redirect and registration strategy (no per-app hacks).
- Reliability constraint: login must degrade gracefully during partial outages (IdP latency spikes, CDN misconfig, link verification regressions) with clear, non-leaky user messaging and without silently weakening security controls.
- Migration constraint: legacy app versions already use `myapp://callback`; you cannot break them immediately, but you must deprecate safely with measured rollout and explicit exception ownership.
- Hard technical constraint: iOS/Android **cache association verification**, so even after fixing a broken AASA/assetlinks response, affected devices may continue failing for hours—your mitigation cannot assume instant cache purge.
- On-call twist: a CDN change starts **302-redirecting** `https://login.example.com/apple-app-site-association`; iOS stops opening your app and users get stuck in the browser—detection must be fast and mitigation must be actionable under cache persistence.
- Multi-team twist: web team owns `login.example.com` and CDN config, mobile teams own app releases, identity team owns IdP redirect registration; you must drive a rollout plan, an ownership model, and SLOs for link verification health.
- Policy twist: privileged scopes (e.g., money movement) must require the strongest protections (PKCE + verified links, and optionally attestation), but product pressures to “just get logins working” during incidents will be intense.
- Operational constraint: you need an “error-class taxonomy” and dashboards that let on-call decide quickly: IdP outage vs link verification failure vs client regression, without logging sensitive artifacts.

**Evaluator Rubric**
- Establishes clear assumptions and explicitly prioritizes risks (redirect hijack vs latency vs availability) when data is incomplete; uses error budget thinking rather than absolutes.
- Proposes an architecture that proves app identity (Universal/App Links + domain association) and uses PKCE correctly; separates “legacy compatibility” from “new secure baseline.”
- Defines measurable SLIs/SLOs for the login funnel and for link verification health; includes paging triggers and a plan to minimize on-call toil (synthetics, runbooks, rollback).
- Handles privacy/compliance by designing structured, minimal logs that still enable fraud/audit and debugging; explicitly avoids raw codes/tokens and unnecessary identifiers.
- Presents a safe migration/rollout plan: version gating, deprecation timeline, exception process with owners/expiry, and canary/rollback strategies that respect OS caching realities.
- Demonstrates cross-team influence: clarifies ownership boundaries, drives alignment with web/CDN and identity teams, and creates enforcement mechanisms (CI validators, IdP policy checks) to prevent drift.
- Anticipates incident scenarios (CDN 302, IdP latency spikes) and proposes mitigations that preserve security guarantees rather than weakening them under pressure.