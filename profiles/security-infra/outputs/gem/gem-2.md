============================================================
EPISODE 3
============================================================

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

============================================================
EPISODE 4
============================================================

## Title
Episode 4 — Auth at the Edge: Passkeys (WebAuthn) Rollout Without a Support Meltdown  
As of Feb 2026

## Hook
- Passkeys can eliminate phishing-driven credential theft, but they shift your top risk to **recovery** (device loss, sync issues, shared devices) and that’s where support volume explodes if you’re not deliberate.
- WebAuthn is “secure by construction” only if your **RP ID / origin architecture** matches how your products are actually deployed; mis-scoping breaks login or silently expands trust boundaries.
- Synced (multi-device) passkeys improve availability and conversion, but they expand the **blast radius** to the cloud account that syncs them—policy must explicitly accept or reject that, by user segment.
- Edge auth is SLO-bound: **p95 <300ms** means every extra DB/Redis lookup, risk callout, or retry loop is user-visible; passkeys reduce fraud, but a slow rollout can still violate latency budgets.
- **99.99% availability** + global traffic means “store challenge in memory” and “single-region Redis” are non-starters; you need predictable behavior during partial outages (and a rehearsed fail-open/closed policy).
- “Passwordless now” is a stakeholder conflict: finance wants to cut SMS spend, security wants phishing resistance, product wants no conversion drop—Staff-level work is sequencing and making trade-offs measurable.
- Browser/OS changes create operational toil: WebAuthn prompt failures (`NotAllowedError`) can spike overnight; without error taxonomy + per-platform telemetry, on-call is forced into blunt rollbacks.
- Shared auth frontends across 20+ teams amplify inconsistency risk: without a centralized **golden path** implementation and invariants, teams will diverge on assurance, caching, and fallback behavior.
- Compliance wants proof of MFA/assurance without biometrics or over-collecting device identifiers; logging choices affect both **auditability** and incident forensics.

## Mental Model
A passkey is a physical key that only fits one specific lock: the browser/OS enforces the lock fit (origin + RP ID), not the user’s judgment. That’s why it’s phishing-resistant—there’s no secret to type into an impostor site. The operational trade is that when a key is missing (new phone, broken device), your system must reliably route users through recovery without turning recovery into the new weakest link.

- The **lock** is your `rpId` + `origin` constraints; choosing `rpId=example.com` is like keying multiple doors alike—great UX, larger blast radius.
- Key cutting is the **registration ceremony** (`PublicKeyCredentialCreationOptions` → authenticator generates a keypair) and you must treat it as a stateful, replay-sensitive transaction.
- The doorman is **server-side verification**: validate `clientDataJSON.origin`, `challenge`, and cryptographic signatures; assurance is enforced by checking UV/UP flags and policy tier.
- Failure/adversary mapping: if you broaden the “lock” too far (shared RP ID across many apps), a compromised subdomain can legitimately request assertions—this isn’t “phishing,” it’s **trust boundary abuse**, and it shows up as hard-to-explain ATOs.
- Spare keys/locksmith is **fallback + recovery**: attackers will pivot there immediately; if it’s not rate-limited, observable, and tiered, you’ll trade phishing for recovery-fraud and on-call pain.

## Common Trap
- Red flag: “Disable passwords immediately.” Fails at scale because device churn, legacy browsers, shared devices, and platform bugs create mass lockouts; recovery paths get hammered, support throughput collapses, and SLOs degrade due to retries and escalations.
- Red flag: “Treat passkeys like just another 2FA checkbox.” Fails because you don’t actually raise assurance where it matters (sensitive actions), leaving the riskiest flows protected by the weakest factor; later retrofitting step-up enforcement creates breaking changes and cross-team friction.
- Red flag: “Implement WebAuthn verification by copy/pasting sample code.” Fails because subtle origin/RP ID validation errors cause either silent auth bypasses or widespread false rejects; debugging becomes on-call toil across multiple products and environments.
- “Store challenges in process memory / rely on sticky sessions.” Fails under multi-region routing and 99.99% availability: retries land on different edges, challenges vanish, and users see intermittent failures; engineers waste cycles on nondeterministic “works on my region” bugs.
- “Require attestation for everyone to be ‘more secure.’” Fails operationally because real-world authenticator metadata is inconsistent and evolves; you end up running allowlists/denylists as an ongoing ops burden and creating conversion cliffs on new devices/OS releases.
- “Instrument only success vs failure.” Fails because `NotAllowedError` collapses user-cancel, no-credential, and platform-bug into one bucket; without structured telemetry, on-call mitigation is guesswork and rollbacks become overly broad.

## Nitty Gritty
**Protocol / Wire Details**
- Registration options endpoint returns `PublicKeyCredentialCreationOptions` JSON: `challenge` (base64url), `rp:{id,name}`, `user:{id,name,displayName}`, `pubKeyCredParams:[{type:"public-key", alg:-7}]` (ES256), plus `timeout`, `excludeCredentials`, and `authenticatorSelection`.
- Set response headers `Cache-Control: no-store` and `Content-Type: application/json`; challenges must not be cached by CDNs/edge layers.
- Anchor: `challenge` — single-use nonce; binds ceremony; blocks replay.
- Client call: `navigator.credentials.create({ publicKey })`; treat `rawId` and response fields as bytes, serialize with base64url consistently across languages/runtimes.
- Verify `clientDataJSON` strictly: `type=="webauthn.create"`, `challenge` exact match, and `origin` exact match (scheme/host/port); mismatched origin is a hard fail, not a warning.
- Decode CBOR `attestationObject` → parse `authenticatorData` + COSE public key; for consumer rollout prefer `attestation:"none"` to minimize privacy + breakage; for admin tier consider `direct` only with explicit ownership of allowlisting and regression handling.
- Anchor: `rpIdHash` — SHA-256(RP ID); prevents cross-site assertion.
- Authentication options endpoint returns `PublicKeyCredentialRequestOptions`: `challenge`, `rpId`, `allowCredentials` (if you’re targeting non-discoverable creds), and `userVerification:"required"` for privileged tiers.
- Client call: `navigator.credentials.get({ publicKey })` returns `authenticatorData`, `clientDataJSON`, `signature`, optional `userHandle`; treat `NotAllowedError` as a structured outcome to classify (cancel vs timeout vs platform failure).
- Verify assertion signature over `authenticatorData || SHA256(clientDataJSON)` using stored COSE key; validate `rpIdHash`, and enforce UP/UV flags per action/tier.

**Data Plane / State / Caching**
- Persist credential records: `credential_id` (bytes), `public_key_cose` (bytes), `user_id` (opaque internal), `aaguid` (optional), `transports`, `created_at`, `last_used_at`, plus backup bits (`backupEligible`, `backupState`) when available.
- Anchor: `backupState` — signals synced credential; affects admin policy.
- Support multiple credentials per user; treat re-enrollment as additive (device churn is normal) and expose self-serve credential management to reduce support tickets.
- Challenge storage: write `{challenge, ceremony_type, user_id?}` to a shared low-latency store keyed by `challenge_id`, TTL ≈ 5 minutes; consume atomically to enforce one-time use.
- Multi-region reality: either replicate the challenge store per-region with predictable routing, or use a signed short-lived token that encodes `challenge_id` to reduce dependency on a single cache—trade replay resistance vs availability explicitly.
- Edge caching: cache `has_passkey` and `assurance_tier` in a signed session/JWT to avoid DB hits every login; include a `credential_version` and bump it on add/remove to force immediate invalidation.
- `signCount` handling: store it, but don’t hard-fail regressions by default because multi-device passkeys may be non-monotonic/0; use it as a fraud signal to avoid self-inflicted lockouts.

**Threats & Failure Modes**
- Replay / ceremony confusion: if you don’t bind challenges to `create` vs `get` and enforce single-use, attackers can replay assertions or cross-wire flows; store `ceremony_type` with the challenge and check it.
- Red flag: “Fallback is always allowed” — attackers pivot to password/SMS/recovery immediately; at scale, your ATOs and costs move, not disappear, and on-call sees fraud spikes despite “passkeys shipped.”
- Origin/RP ID misconfiguration: mismatched allowed origins (http vs https, alternate domains, embedded webviews) causes widespread intermittent auth failures; treat origin allowlists as versioned config with canary + rollback.
- Anchor: `userVerification` — strongest knob for step-up on sensitive actions.
- Synced passkeys: compromise of the sync account enables takeover without phishing; mitigate via segmentation (consumer accepts synced; admins require device-bound/hardware-backed) and risk checks for “new device/new credential” events.
- Recovery abuse: “lost device” flows must be rate-limited, step-up protected where possible, and fully audited (who/what/when); otherwise recovery becomes the attacker’s preferred path.
- Privacy/compliance failure mode: logging raw `clientDataJSON`, stable device identifiers, or detailed AAGUIDs can violate minimization/retention expectations; log structured outcomes + policy tier + coarse platform, with defined retention and access review.

**Operations / SLOs / Rollout**
- Latency budget: keep options/verify endpoints to O(1) datastore work; avoid synchronous calls to external risk systems on the hot path—prefer cached risk posture or async enrichment.
- Page-worthy SLIs: auth success rate by platform/browser, p95/p99 endpoint latency, `NotAllowedError` rate, UV-required failure rate, fallback usage rate, support contacts per 10k logins, plus phishing-driven ATO (lagging KPI).
- Rollout control: independent flags for (1) enrollment UX, (2) passkey login allowed, (3) step-up enforcement; make rollback a config flip with explicit thresholds (e.g., +X% `NotAllowedError` after OS update).
- Partial outages: predefine fail-closed vs fail-open per action—e.g., fail closed for admin step-up, allow consumer login with compensating controls (tight rate limits, additional verification) when caches degrade; document and rehearse in runbooks.
- OS/browser regressions: maintain a targeted denylist/mitigation policy by platform version (server-side), and an immediate safe fallback; blast-radius control beats heroic debugging during an incident.
- Auditability: emit immutable events for credential add/remove, assurance tier decisions, and recovery approvals; minimize PII while preserving incident timelines and assurance evidence.

**Interviewer Probes (Staff-level)**
- Probe: How do you choose RP ID(s) across multiple subdomains/products without creating a shared-blast-radius failure?
- Probe: If Redis/challenge storage is degraded in one region, what is your explicit fail-open/closed policy per tier, and how do you prevent abuse?
- Probe: What telemetry schema lets you separate “user canceled” vs “no credential” vs “platform bug” for `NotAllowedError`, and how does that drive rollback?
- Probe: What risk acceptance do you document for synced passkeys (consumer) vs device-bound/hardware-backed (admin), and where do you enforce it?

**Implementation / Code Review / Tests**
- Coding hook: Strict base64url decoding for all binary fields; reject padding/invalid chars; fuzz invalid encodings to prevent parser edge cases.
- Coding hook: Exact-match validation of `clientDataJSON.type`, `origin`, and `challenge`; reject non-HTTPS origins and unexpected ports; unit-test origin allowlist changes.
- Coding hook: Challenge must be ceremony-bound and single-use with atomic consume; add a negative test for double-submit within TTL and for stale challenges.
- Coding hook: CBOR parsing hardening—bounded sizes for `authenticatorData` and extensions; reject truncated/oversized structures to prevent CPU/memory DoS.
- Coding hook: Enforce policy-tier checks: `rpIdHash` match, UP/UV flag requirements, and allowed `alg` (e.g., ES256) only; test each tiered action.
- Coding hook: `allowCredentials` / discoverable credentials must not introduce account enumeration via different error messages/timings; add black-box tests for enumeration.
- Coding hook: Cache invalidation invariant—credential add/remove increments `credential_version`; edge session must reject stale versions immediately; integration test “enroll then login” without delay.
- Coding hook: Rollback safety tests—toggle passkey-required → optional under load; ensure no data loss and stable UX while preserving audit logs.

## Staff Pivot
- Competing architectures: **A)** password + SMS OTP (familiar, phishing-prone, ongoing fraud + SMS spend), **B)** passkeys optional (safer rollout, slower security benefit), **C)** passkeys mandatory (fast phishing drop, high lockout/support risk), **D)** passkeys + step-up for sensitive actions (balanced, needs solid policy/risk gating).
- Decision: execute **B → D**—earn reliability and enrollment first, then enforce phishing-resistant auth on the highest-loss actions (admins/high-risk) before broad mandates.
- Enforcement is the lever: keep baseline login permissive initially, but require WebAuthn (`userVerification:"required"`) for actions that change control of the account (recovery factor changes, admin grants, API key creation).
- Latency/SLO trade: step-up limits WebAuthn prompts and datastore reads to the subset of sessions that need it, protecting p95 <300ms while still collapsing phishing ROI on the most valuable paths.
- What I’d measure (weekly): phishing-driven ATO rate, enrollment %, login conversion, support contacts per 10k logins, and p95/p99 time-to-auth by platform.
- What I’d measure (daily/on-call): `NotAllowedError` rate by OS/browser version, UV-required failure rate, challenge-store errors, and fallback usage rate (residual risk + cost proxy).
- Rollout discipline: separate flags for enrollment UI, passkey auth, and step-up requirements; define rollback thresholds tied to user impact (conversion/support/SLO), not just security outcomes.
- Stakeholder influence: finance gets a savings curve tied to measured fallback reduction (not promises), product gets conversion guardrails + experimentation framework, security gets measurable phishing resistance via tiered enforcement.
- Support/SRE alignment: publish recovery SLIs (success rate, time-to-recover) and runbooks for device loss, shared devices, and OS regressions; otherwise the “security win” becomes sustained operational toil.
- Compliance trade-off: generate auditable assurance events (tier decision, UV/UP) while explicitly avoiding biometric storage and minimizing device identifiers; set retention/access controls before broad rollout.
- What I would NOT do: “turn off SMS next month” or “make passkeys mandatory everywhere” before recovery and telemetry are proven; tempting for cost/security, but it’s how you trigger mass lockouts and emergency policy reversals.
- Tie-back: Describe a time you used feature flags + explicit rollback criteria to ship a risky auth change safely.
- Tie-back: Describe how you documented and defended risk acceptance when availability and security objectives conflicted.

## Scenario Challenge
- You operate a global SaaS auth system fronted at the edge with **p95 login <300ms** and **99.99% availability**; traffic is multi-region with no single “primary” region.
- Phishing ATOs are rising, concentrated in password + SMS OTP; security needs a measurable reduction within two quarters.
- Product constraint: no more than **0.5% absolute** drop in login conversion during rollout; reversibility within minutes is required.
- Finance constraint: reduce SMS spend quickly, but you cannot trade it for a sustained support spike or elevated takeover risk via weaker recovery paths.
- Migration constraint: legacy browsers and existing password + TOTP users must keep working; no flag day; rollout must be staged and reversible.
- Developer friction constraint: 20+ product teams depend on a shared auth frontend; you must provide a centralized “golden path” WebAuthn implementation with guardrails so teams can’t subtly violate assurance requirements.
- Reliability constraint: your Redis challenge store and primary DB can degrade regionally; authentication must continue across regions during brownouts without single-region dependency.
- Security constraint: privileged/admin actions require phishing-resistant step-up; consumer login can accept higher availability trade-offs, but risk acceptance must be explicit and documented.
- Privacy/compliance constraint: auditors require evidence of MFA/assurance; you must not log biometrics and must avoid storing unnecessary device identifiers (minimize AAGUID/transport collection and retention).
- Hard technical constraint: edge nodes cannot make more than **one cross-region roundtrip** on the critical login path; additional coordination must be cached locally or handled asynchronously.
- On-call twist: a major mobile OS release causes a spike in `NotAllowedError` for `navigator.credentials.get()` concentrated in one OS version; support volume doubles in 6 hours and p95 latency creeps above 300ms due to retries.
- Leadership twist: security pushes “mandatory passkeys,” product wants “optional forever,” finance wants “SMS off next month”; propose segmentation, enforcement tiers, telemetry, and a rollout plan with explicit risk acceptance/deferral.

**Evaluator Rubric**
- Clearly states assumptions, defines user/admin segments, and identifies enforcement points (login vs step-up) with explicit fail-open/closed choices.
- Proposes an architecture that meets latency/availability: minimal synchronous dependencies, multi-region state handling for challenges/credentials, and bounded critical-path work.
- Demonstrates protocol correctness: strict origin/RP ID validation, UV/UP policy, replay protection, and correct handling of synced vs device-bound passkeys.
- Outlines a staged rollout with independent feature flags, canary strategy, and rollback criteria tied to conversion, support load, error rates, and SLO impact.
- Defines observability with actionable taxonomy: `NotAllowedError` breakdown, UV failures, datastore health, fallback usage, and dashboards that enable fast triage.
- Provides an incident mitigation plan for OS regressions: targeted toggles, platform-based mitigations, safe fallbacks, and coordination with Support/Product during the event.
- Addresses privacy/compliance explicitly: minimal logging, retention/access controls, and auditable assurance events without biometrics or over-collection.
- Shows stakeholder handling: quantifies trade-offs (security vs conversion vs cost), aligns incentives, and documents residual risk (fallback/recovery) in a way leadership can sign off on.