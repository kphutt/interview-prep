**Episode 4 — Auth at the Edge: Passkeys (WebAuthn) Rollout Without a Support Meltdown**

2) **The Hook (The core problem/tension).**
- Passkeys can kill phishing at the root, but “passwordless now” can explode account recovery, support load, and edge-case breakage.  
- WebAuthn is secure by construction (origin binding), but your architecture choices determine reliability and user experience.  
- Staff-level angle: segment users, pick enforce points, and make the rollout measurable and reversible.

3) **The "Mental Model" (A simple analogy).**  
A passkey is a physical key that only fits one specific lock: the browser/OS enforces the lock (origin/RP ID), not the user. That’s why it’s phishing-resistant—there’s no “type your secret into the wrong website.”

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “Disable passwords immediately.” Security-only thinking ignores recovery, device loss, shared devices, and support throughput; you’ll trade phishing for mass lockouts.  
- “Treat passkeys like just another 2FA checkbox.” If you don’t enforce the right assurance level for sensitive actions, you keep your riskiest paths weak.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Registration options (protocol detail):** server sends `PublicKeyCredentialCreationOptions` with `challenge`, `rp:{id,name}`, `user:{id,name,displayName}`, and `pubKeyCredParams` (e.g., ES256 `alg:-7`).  
- **Client API:** `navigator.credentials.create({ publicKey })` returns `id/rawId` and `response.attestationObject` + `response.clientDataJSON` (base64url).  
- **Verify registration (crypto detail):** decode CBOR `attestationObject`, extract credential public key (COSE) and `authenticatorData`; verify `clientDataJSON.type=="webauthn.create"`, expected `origin`, and exact `challenge`.  
- **Authentication options:** server sends `PublicKeyCredentialRequestOptions` with `challenge`, `rpId`, `allowCredentials`, and `userVerification:"required"` for privileged users.  
- **Client API:** `navigator.credentials.get({ publicKey })` returns `response.authenticatorData`, `clientDataJSON`, `signature`, and maybe `userHandle`.  
- **Signature verification:** verify signature over `authenticatorData || SHA256(clientDataJSON)` with stored public key; validate `rpIdHash == SHA-256(rpId)`; check UV/UP flags.  
- **Origin binding property:** browser will not produce assertions for `g00gle.com` if the credential is for `google.com`; this is enforced client-side, not by user training.  
- **Data-plane storage:** store `credential_id`, `public_key_cose`, `aaguid`, transports, `created_at/last_used_at`, and backup metadata (`backupEligible/backupState` when available).  
- **Challenge storage (data-plane):** store challenges in a shared store (e.g., Redis) keyed by a one-time ID with TTL ~5 minutes to prevent replay and avoid sticky sessions.  
- **Edge/caching reality:** cache “passkey enrolled” and policy tier in the session to avoid DB hits on every login, but invalidate immediately on credential add/remove.  
- **Operational:** dashboards for enrollment %, auth success rate, error codes (`NotAllowedError`, UV required failures), and support contact rates; runbooks for browser/OS regressions.  
- **Policy/control:** segment policies—synced passkeys for consumers (recovery/availability), device-bound keys/security keys for admins; keep fallback auth behind risk checks and rate limits.  
- **Explicit threat/failure mode:** synced passkeys expand blast radius—compromise of the cloud sync account can enable takeover without phishing.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** Password + SMS OTP (familiar; phishing-prone; high ongoing cost and fraud).  
  - **B)** Passkeys optional (low risk rollout; slower security benefit).  
  - **C)** Passkeys mandatory (fast phishing reduction; high recovery/support risk).  
  - **D)** Passkeys for login + step-up for sensitive actions (balanced; requires good risk engine).  
- My choice: **B → D progression**: start optional with strong UX, then require passkeys (or equivalent phishing-resistant factor) for admin/high-risk actions first.  
- What I’d measure: **phishing-driven ATO rate**, **login success/conversion**, **support tickets per 10k logins**, **time-to-auth p95**, and **fallback usage rate** (fallback is your residual risk).  
- Risk acceptance: for consumer accounts, I’ll accept synced passkeys + recovery paths to preserve availability; for admins, I won’t accept synced-only—require device-bound/hardware-backed.  
- Stakeholder/influence: partner with Support and Product early—publish a deprecation/recovery policy, and make sure “reduce fraud” translates to a business metric they’ll back.  
- Operational maturity: ship with feature flags, staged rollouts, and clear rollback criteria (e.g., spike in `NotAllowedError` after OS update).

7) **A "Scenario Challenge" (Constraint-based problem).**
- You operate a global SaaS login system with **p95 login <300ms** at the edge and **99.99% availability**; phishing ATOs are rising.  
- Security goal: adopt passkeys to materially reduce phishing risk, but you must retain secure recovery and minimize lockouts.  
- Reliability constraint: authentication must work across regions and during partial outages (Redis/DB degradation); no single-region dependency.  
- Privacy/compliance: must meet audit requirements for MFA/assurance without logging biometrics or storing sensitive device identifiers unnecessarily.  
- Developer friction: 20+ product teams rely on a shared auth frontend; you need a centralized “golden path” WebAuthn implementation.  
- Migration/back-compat: you must support legacy browsers and existing password + TOTP users; no flag day; rollout must be reversible.  
- On-call twist: a major mobile OS release increases WebAuthn prompt failures (spike in `NotAllowedError`); support volume surges—what telemetry and mitigations do you activate?  
- Multi-team/leadership twist: finance wants to cut SMS spend immediately, security wants phishing resistance, product wants zero conversion drop—propose segmentation, enforcement tiers, and a measurable rollout plan with explicit risk acceptance.