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