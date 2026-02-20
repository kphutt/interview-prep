**Episode 13 — Frontier Digest A (Feb 2026): “PoP + Signals + Passkeys” — Where Sender‑Constraint, Revocation, Mobile OAuth, and WebAuthn Are Converging**

2) **The Hook (The core problem/tension).**
- 2024–2026 attackers increasingly win by **stealing tokens/sessions** (logs, infostealers, AiTM proxies), not by “breaking crypto.”  
- The ecosystem response is a stack: **Proof-of-Possession (DPoP/mTLS)** + **push revocation (CAEP/RISC)** + **phishing-resistant auth (passkeys)** + **mobile app identity (App/Universal Links + PKCE)**.  
- The Staff problem: these controls are individually sound, but **interop gaps + rollout failure modes** can create outages or conversion drops.  
- The interview angle: pick what to standardize **now** vs keep on the **watchlist**, with measurable success criteria.

3) **The "Mental Model" (A simple analogy).**  
Think of modern identity as a building with (a) **keyed entry** (passkeys), (b) a **badge that must match the person holding it** (PoP tokens), and (c) a **security desk that can radio “invalidate that badge now”** (Shared Signals revocation). Mobile app-link verification is the doorman ensuring the badge is handed to the **right app**, not a lookalike.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “If we ship passkeys, we’re done.” Security-only thinking ignores **session/token theft**, recovery, and revocation pipeline reliability.  
- “Adopt every new draft everywhere.” You’ll create **interop breakage** and on-call load without a staged migration plan.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Touchpoints:** E1 (mTLS vs DPoP sender constraint), E2 (CAEP/RISC revocation), E3 (App/Universal Links + PKCE), E4 (passkeys rollout). Re-check your “default picks” below.  
- **Frontier item (Recent): DPoP operational hardening** — *As-of Feb 2026* | *Maturity:* Deployed (select ecosystems) | *Confidence:* Medium | *Anchor:* **RFC 9449** — Expect stricter resource-server checks for `DPoP` proof fields (`htu`, `htm`, `iat`, `jti`, and `ath = BASE64URL(SHA-256(access_token))`); plan for a **hot-path replay cache** keyed by `(jwk_thumbprint, jti)` with TTL ~ proof lifetime.  
- **Frontier item (Recent): OAuth request integrity becomes “baseline” for high-risk** — *As-of Feb 2026* | *Maturity:* Adopted (regulated/high-risk APIs) | *Confidence:* Medium | *Anchor:* **RFC 9126 (PAR)** + **RFC 9101 (JAR)** — PAR reduces URL-param tampering/leakage; JAR signs request params in a JWT (JWS). Net effect: fewer “confused deputy” edges when many intermediaries/CDNs exist.  
- **Frontier item (Recent): Mix-up defenses are no longer optional in multi-IdP apps** — *As-of Feb 2026* | *Maturity:* Adopted | *Confidence:* High | *Anchor:* **RFC 9207 (`iss` parameter)** — Validate `iss` in the authorization response before code exchange; this is a cheap fix that prevents “got a code from the wrong issuer” class bugs.  
- **Frontier item (Recent): Shared Signals (CAEP/RISC) is moving from “cool idea” to “needed control”** — *As-of Feb 2026* | *Maturity:* Emerging → Adopted (IdP-dependent) | *Confidence:* Medium | *Anchor:* **OpenID Shared Signals Framework / CAEP** + **RFC 8417 (SET; `application/secevent+jwt`)** — Treat the event receiver as production infra: verify JWS, cache event `jti` for replay defense, and implement **idempotent** “latest-wins” updates to your revocation epoch (`revoked_at` per `sub`/`sid`).  
- **Frontier item (Near-Future, 6–12mo): OAuth 2.1 convergence into enforceable linting** — *As-of Feb 2026* | *Maturity:* Emerging (IETF draft) | *Confidence:* Medium | *Anchor:* **draft-ietf-oauth-v2-1** + **RFC 7636 (PKCE)** — The practical shift is less “new flow” and more **automation**: CI checks that reject implicit/hybrid remnants, missing PKCE, loose redirect matching, and unsafe token storage patterns.  
- **Frontier item (Watchlist, 12–24mo; speculative): Attestation + PoP for “real app / real device” signals** — *As-of Feb 2026* | *Maturity:* Draft | *Confidence:* Low | *Anchor:* **IETF OAuth WG drafts on attestation-based client authentication** — Likely direction: “DPoP-like key + attestation evidence” to raise the cost of cloned/malicious apps; expect verifier complexity and ecosystem fragmentation.  
- **Data-plane/caching reality (cross-cutting):** you’re now running **three caches** that must behave under duress: (1) DPoP `jti` replay cache, (2) revocation epoch/cache from CAEP events, (3) WebAuthn challenge store (5-minute TTL) — design for **regional partition**, fast local LRU, and bounded memory.  
- **Operational reality:** passkey and PoP rollouts are **browser/OS release-sensitive**; ship with feature flags, error-budget guardrails, and dashboards segmented by **platform + app version** (e.g., `NotAllowedError` spikes for WebAuthn; `dpop_proof_invalid` spikes for PoP).  
- **Policy/control detail:** define an explicit **assurance & token-binding matrix** per scope: e.g., `admin/*` requires passkey (UV required) + sender-constrained token; `read/*` can remain bearer temporarily with tighter monitoring and faster revocation.  
- **Explicit threat/failure mode:** passkeys reduce phishing, but **infostealers/AiTM can still steal live sessions** (cookies/refresh tokens). Without PoP + fast revocation, attackers keep “authenticated” access even after you “fixed login.”

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures you’ll be asked to choose between:  
  - **A)** Passkeys-only (strong login, but session theft still works; weak kill switch).  
  - **B)** PoP-only (reduces token replay, but phishing/ATO still high; UX friction on clients).  
  - **C)** **Layered**: passkeys for phishing resistance + DPoP/mTLS for replay resistance + CAEP/RISC for time-to-kill (most robust; highest integration/ops complexity).  
- My decisive trade: pick **C**, but **tier it**—deploy PoP + CAEP first for *high-risk scopes and partner classes*, then expand as tooling matures.  
- Enforce at the **gateway/edge** when feasible (consistent policy, fewer per-service bugs), but keep a shared library fallback for services that can’t be fronted uniformly.  
- What I’d measure (to decide “adopt now vs pause”): **ATO rate by vector (phishing vs token theft)**, **replay blocks**, **time-to-kill p95**, **p99 auth overhead**, **login conversion**, and **support tickets per 10k logins** (recovery + passkey prompt failures).  
- Risk acceptance: I’ll accept **partial ecosystem coverage** (bearer tokens for low-risk reads for a time-bounded window), but I won’t accept “no kill switch” for privileged scopes once CAEP is in place.  
- Stakeholder/influence: align Product (conversion), Support (recovery load), Identity (token format + event streams), and Gateway/SRE (latency + capacity) around an explicit **assurance tier policy** and a **deprecation calendar** with rollback triggers.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You operate a global auth + API platform at **150k RPS**, with **+10ms p99** auth budget at the gateway and **99.99%** availability.  
- New fraud pattern: attackers steal access tokens and session cookies via infostealers; compliance demands **phishing-resistant auth** for money movement and **<60s revocation** for confirmed compromise.  
- Reliability constraint: APIs must stay up during **IdP partial outage**; you cannot introspect every request.  
- Security constraint: must prevent replay of stolen access tokens for `payments:write`; attacker can read logs/headers but cannot compromise OS secure key stores.  
- Privacy/compliance constraint: no raw token logging; device identifiers must be minimized and purpose-bound.  
- Developer friction constraint: 30 microservices + 3 mobile apps + partner integrations; you need a **golden path SDK** and gateway enforcement (no bespoke per-service auth).  
- Migration/back-compat: legacy mobile versions still use `myapp://` redirects and bearer tokens; partners include TLS-terminating appliances (mTLS inconsistent). Mixed-mode must work per `client_id`/scope for **12–18 months**.  
- Incident/on-call twist: after enabling DPoP for a large mobile cohort, CPU on the gateway spikes and you see elevated `dpop_jti_replay_cache_miss` due to cache evictions—latency SLO is violated. What do you shed (nonce? scopes? cohorts?), and where do you fail closed?  
- Multi-team/leadership twist: Product wants “no UX change,” Compliance wants “phishing-resistant now,” Partners want “no client changes,” and SRE wants “no new hard dependency.” Drive a decision: which cohorts get passkeys first, which scopes require PoP, what your CAEP kill-time SLO is, and the explicit exception process.