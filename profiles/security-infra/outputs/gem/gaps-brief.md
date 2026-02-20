## Title
**Gaps Brief: Identity Proofing (IAL3), Global DDoS/Anycast, and Behavioral Biometrics — The Controls the Syllabus Didn't Cover**
(As-of: Feb 2026)

## Hook
- The main syllabus covers authentication, authorization, and session management in depth — but never asks: **how do you know the person is real in the first place?** Identity proofing (IAL) is the trust anchor that everything else builds on, and getting it wrong means your phishing-resistant passkeys are protecting an account that was fraudulently opened.
- DDoS at the infrastructure layer (volumetric, protocol, application) is the **availability threat that bypasses all your identity controls** — if traffic never reaches your proxy, your ZTNA policies don't matter. Anycast, scrubbing, and edge absorption are the actual mechanisms, not "just use a CDN."
- Behavioral biometrics and continuous trust scoring represent the **post-authentication signal layer** — the idea that identity confidence should decay and regenerate based on ongoing behavior, not just the login ceremony. This is where the industry is heading for session security, but operational false-positive rates and privacy constraints make it treacherous to deploy.
- All three gaps share a pattern: they sit at the **edges of the identity stack** (before login, below the network, after authentication) where most engineers don't look, and interviewers love to probe exactly those blind spots.

## Mental Model
Think of identity security as a building. The syllabus covered the locks (authn), the badge readers (authz), the doors (proxy), and the alarm system (detection). This gaps brief covers three things the building also needs: **the front desk that checks your government ID before issuing a badge** (identity proofing), **the foundation and walls that keep the building standing during a storm** (DDoS/Anycast), and **the security cameras that watch how people behave after they badge in** (behavioral biometrics). Without the front desk, you issue badges to imposters. Without the foundation, no lock matters. Without the cameras, a stolen badge works until someone notices.

- Front desk → IAL/identity proofing: the quality of the initial identity verification determines the ceiling of everything downstream. A passkey bound to a fraudulently opened account is a perfectly secure credential protecting an attacker.
- Foundation → DDoS/Anycast: availability infrastructure that must absorb attacks before they reach your application layer. If your edge goes down, your identity stack is irrelevant.
- Cameras → behavioral biometrics: continuous signals that re-evaluate trust during a session. The gap between "authenticated at login" and "still the same person 4 hours later" is where session hijacking lives.

## Common Trap
- **IAL3 trap:** "We verify email addresses." Email verification is IAL1 at best — it proves you control an inbox, not that you're a real person. For regulated flows (financial onboarding, gov identity, high-value account creation), you need document verification, liveness detection, and binding to a credential. Junior engineers skip this because they think authentication *is* identity, when it's actually downstream of proofing.
- Red flag: "Identity proofing is a product problem, not a security problem." It's both. A weak proofing flow is an ATO vector at account creation, before any of your session or token security matters. If fraud creates accounts at scale, your detection engineering (Ep 9) is fighting synthetic identities, not just compromised ones.
- **DDoS trap:** "Our cloud provider handles DDoS." Managed DDoS protection absorbs volumetric floods, but application-layer attacks (slowloris, credential stuffing at login, API abuse) pass right through. The junior mistake is treating DDoS as a checkbox rather than an architecture decision about where traffic is absorbed, how capacity is provisioned, and what degrades gracefully vs. fails hard.
- Red flag: "We rate-limit at the application." If the flood reaches your application servers, you've already lost — rate limiting at L7 doesn't help when the pipe is saturated at L3/L4. Absorption must happen at the edge.
- **Behavioral biometrics trap:** "Add a risk score to every request." Continuous scoring sounds great until false positives force step-up auth 50 times a day for legitimate users. The junior approach ships a model without defining acceptable FPR/FNR by user segment, without a graceful degradation path when the scoring service is down, and without privacy review for the signals being collected.
- Red flag: "Collect everything, score later." Behavioral signals (keystroke timing, mouse dynamics, accelerometer data) are often PII or sensitive data under GDPR/CCPA. Collection without purpose limitation and retention controls creates compliance exposure that can exceed the security benefit.

## Nitty Gritty

**Identity Proofing / IAL (NIST 800-63A)**

- **IAL levels:** IAL1 = self-asserted (email/phone); IAL2 = remote document verification + liveness; IAL3 = in-person or supervised remote with physical document + biometric binding. Most consumer flows are IAL1; regulated/financial/gov often require IAL2+.
- **Document verification pipeline:** capture government ID (passport, driver's license) → OCR + template matching → check against fraud databases (if available) → liveness detection (selfie + challenge like "turn head left") → bind verified identity to credential (passkey, certificate).
- **Liveness detection attacks:** presentation attacks (printed photo, screen replay, 3D mask) require certified liveness (ISO 30107-3 PAD Level 2+); remote attacks include deepfake injection into the camera stream — detection must operate on the raw sensor feed, not user-submitted images.
- **Binding to credential:** after proofing, you must create a strong binding between the verified identity and the authentication credential. If proofing is IAL2 but the credential is a password, the proofing is wasted on first credential compromise.
- Anchor: NIST 800-63A — Defines IAL1/2/3 requirements and evidence strength.
- Anchor: ISO 30107-3 — Presentation attack detection (PAD) levels for liveness.
- **Operational reality:** identity proofing is typically outsourced to vendors (Jumio, Onfido, Socure, etc.) via API; this creates a **critical vendor dependency** with its own SLOs, failure modes (vendor downtime = can't onboard users), and data residency constraints.
- **Fraud signal integration:** proofing results feed into account risk tier at creation time; a "high-confidence" proofing result can unlock higher-trust actions (larger transactions, admin enrollment) while a "low-confidence" result triggers additional verification or limits.
- Probe: How would you design an identity proofing flow that meets IAL2 for a global consumer product while keeping onboarding conversion above 85% and handling vendor outages?

**Global DDoS / Anycast Architecture**

- **Volumetric attacks (L3/L4):** UDP floods, SYN floods, amplification (DNS, NTP, memcached). Mitigation: anycast-distributed edge absorbs traffic across many PoPs; scrubbing centers (dedicated or cloud-based) filter malicious traffic before it reaches origin.
- **Anycast mechanics:** the same IP prefix is advertised via BGP from multiple PoPs worldwide. Traffic naturally routes to the nearest PoP. During an attack, traffic is distributed across all PoPs proportionally, so no single PoP is overwhelmed. Failover happens via BGP withdrawal.
- Anchor: BGP anycast — Traffic distribution mechanism for edge absorption.
- **Protocol attacks (L4):** SYN floods exhaust connection tables. Mitigation: SYN cookies at the edge (stateless SYN handling), connection rate limiting per source IP, and TCP stack tuning (backlog, timeout).
- **Application-layer attacks (L7):** HTTP floods, slowloris, credential stuffing, API abuse. These are valid TCP connections with valid HTTP — volumetric scrubbing doesn't help. Mitigation: WAF rules, bot detection (JS challenge, CAPTCHA, fingerprinting), rate limiting per identity/session/API key at the edge proxy, and adaptive throttling.
- **Scrubbing pipeline:** traffic flow is typically: client → anycast PoP → (if clean) origin, or client → anycast PoP → scrubbing center → (cleaned) origin. The scrubbing center inspects packet headers, payload patterns, and rate heuristics. Latency cost of scrubbing is typically 1–5ms added per hop.
- **Capacity planning:** DDoS protection requires pre-provisioned headroom — you can't autoscale fast enough for a 500Gbps flood. Edge providers (Cloudflare, Akamai, AWS Shield Advanced, GCP Cloud Armor) provide this capacity as a service, but you must understand what's included (volumetric vs. L7) and what requires custom rules.
- **Operational reality:** DDoS response is an **on-call event** — even with automated mitigation, novel attack patterns require human judgment (is this a real attack or a traffic spike from a viral event?). Runbooks must distinguish between the two.
- Coding hook: Implement rate limiting at the edge with composite keys (source IP + authenticated identity + API path) rather than IP-only; add negative tests for rate-limit bypass via header spoofing (`X-Forwarded-For`).
- Coding hook: Health check and failover: anycast PoPs must withdraw BGP routes when unhealthy; test failover time and ensure no traffic black-holing during withdrawal propagation (~30–90 seconds).
- Probe: You're under a mixed L3/L7 attack — volumetric is being absorbed by your edge, but application-layer credential stuffing is overwhelming your login endpoint. Your rate limiter uses IP-only keys and attackers rotate IPs. What do you change?
- **Policy/control:** define DDoS response tiers (automated absorption, human-in-the-loop WAF tuning, emergency origin isolation) with escalation paths and communication templates for leadership/customers.
- **Explicit threat/failure mode:** anycast withdrawal during BGP issues can cause asymmetric routing and dropped connections; if your PoP health checks are too aggressive, you create self-inflicted failover cascades.

**Behavioral Biometrics / Continuous Trust**

- **Signal types:** keystroke dynamics (timing between keystrokes, dwell time), mouse/trackpad movement patterns (speed, curvature, click patterns), touch/swipe patterns on mobile, accelerometer/gyroscope data (device handling), and navigation patterns (page flow, timing between actions).
- **Continuous authentication vs. step-up triggers:** two deployment models. (1) Continuous scoring adjusts a session risk score in real time — high score triggers step-up or session termination. (2) Point-in-time check at sensitive actions uses behavioral signals as an additional factor.
- **Scoring architecture:** signals collected client-side → shipped to scoring service → ML model produces risk score → score compared to threshold → action (allow / step-up / block). The scoring service is a **hot-path dependency** if used for real-time decisions.
- **False positive management:** behavioral biometrics have inherently noisy signals. A user with a broken wrist, a new keyboard, or a different posture will trigger anomalies. FPR must be tuned per user segment; hard thresholds create support nightmares. The industry-standard approach is to use behavioral signals as **risk modifiers**, not hard gates.
- Anchor: FIDO Alliance UX guidelines — Recommends behavioral signals as supplementary, not primary.
- **Privacy constraints:** behavioral data (keystroke timing, device motion) may constitute biometric data under GDPR Art. 9, BIPA (Illinois), and similar regulations. Requirements: explicit consent, purpose limitation, data minimization, retention limits, and right to deletion. Processing must be local where possible; server-side storage of raw behavioral data is high-risk.
- **Data plane:** prefer on-device scoring (edge ML) to minimize data transmission and privacy exposure. Ship a compressed feature vector (not raw signals) to the server for aggregate analysis and model updates. Cache user behavioral profiles locally with strict TTL.
- Coding hook: Feature extraction must be deterministic and testable — write unit tests for keystroke timing extraction that verify consistent results across browser engines and input methods (IME, voice input, password managers produce no behavioral signal — handle gracefully).
- Coding hook: Scoring service circuit breaker — if scoring is unavailable, fall back to session-age-based step-up rather than blocking all actions. Test the degraded path explicitly.
- Probe: Your behavioral scoring service has a 2% false positive rate. At 100k daily active users, that's 2,000 unnecessary step-up prompts per day. How do you reduce friction without reducing security for the highest-risk sessions?
- **Operational detail:** dashboards for FPR/FNR by user segment, scoring latency p99, step-up trigger rate, and "behavioral signal coverage" (% of sessions with enough signal to score — password managers and assistive tech create blind spots).
- **Explicit threat/failure mode:** adversaries who have stolen a session can mimic behavioral patterns if they have access to the victim's device (RAT/remote access). Behavioral biometrics are strongest against remote token replay from a different device, weakest against on-device compromise.

**Interviewer Probes (Staff-level)**

- Probe: How do you decide which actions require IAL2 proofing vs. IAL1 self-assertion, and how does that decision interact with your authn assurance tiers (passkeys vs. passwords)?
- Probe: Walk me through what happens during a 300Gbps DDoS attack against your login endpoint — from BGP anycast absorption through to the auth stack. Where does each layer of defense activate?
- Probe: If you deploy behavioral biometrics for continuous trust, how do you handle the privacy review, and what's your fallback when the scoring service is degraded during an incident?

**Implementation / Code Review / Tests**

- Coding hook: Identity proofing vendor integration — implement idempotent verification requests with timeouts and retry; test vendor timeout (>5s) gracefully degrades to "try again later" rather than silent account creation without proofing.
- Coding hook: Anycast health check — verify that BGP route withdrawal triggers within 10s of health check failure and that traffic reroutes to the next-nearest PoP without connection drops for established sessions.
- Coding hook: Behavioral signal collection — ensure raw signal data is never persisted server-side beyond the scoring window; add integration tests that verify no keystroke timing data appears in application logs, analytics pipelines, or crash reports.
- Coding hook: Rate limiter key composition — test that composite keys (IP + session + path) correctly bucket authenticated vs. unauthenticated traffic separately; negative test for key collision under NAT (many users behind one IP).

## Staff Pivot
- **IAL as a security architecture decision, not a product checkbox:** the proofing level you require at account creation determines the trust ceiling for every downstream control. If you're deploying passkeys (Ep 4) and CAEP revocation (Ep 2) but your accounts are IAL1 (email only), you're securing fraudulently created accounts with the same rigor as legitimate ones. Staff-level move: tier proofing requirements by account risk class (consumer vs. business vs. admin), and use proofing confidence as an input to your authn assurance tier matrix.
- **DDoS as an availability architecture, not an add-on:** DDoS mitigation is not a feature you buy — it's a property of your edge architecture. Anycast, scrubbing, and edge rate limiting must be designed into the request path from day one, not bolted on after an attack. The Staff insight is that DDoS protection and your ZTNA proxy (Ep 5) share infrastructure — the edge PoP that terminates TLS, enforces identity policy, and absorbs floods is often the same tier-0 component.
- **Behavioral biometrics as risk enrichment, not a gate:** the strongest deployment model uses behavioral signals to adjust session risk scores (feeding into your CAEP/RISC event stream from Ep 2 and detection pipeline from Ep 9), not as a hard authentication factor. This avoids the FPR problem while still raising the cost of session hijacking from a different device.
- Competing approaches for continuous trust:
  - **A)** Hard behavioral gate on every sensitive action — strongest security signal, but FPR creates support load and user frustration that leadership will force you to disable.
  - **B)** Behavioral score as a risk modifier feeding into step-up decisions — balanced; requires careful threshold tuning and segment-specific baselines.
  - **C)** Behavioral signals for detection/forensics only (not real-time) — lowest friction, but doesn't prevent in-session abuse.
- I'd choose **B** for high-value sessions and **C** as a baseline everywhere else. The decisive trade-off: accept that behavioral signals are noisy and use them to *inform* decisions rather than *make* decisions.
- What I'd measure: proofing conversion rate by IAL level, proofing vendor latency/availability, DDoS mitigation time-to-absorb, L7 attack detection rate, behavioral FPR/FNR by segment, step-up trigger rate attributable to behavioral signals, and user complaint rate from false step-ups.
- Tie-back: Describe a time you had to balance a security control's false positive rate against user experience — how did you decide the threshold and who signed off?
- Tie-back: Explain how you would prioritize which of these three gaps to address first given limited engineering capacity and two interview-relevant constraints: a compliance deadline for identity proofing and an active DDoS campaign.
- Risk acceptance: I'll accept IAL1 for low-risk consumer accounts temporarily, but not for accounts with admin privileges or financial access. I'll accept that behavioral biometrics are enrichment-only (not blocking) for the first year while baselines stabilize. I'll accept cloud-provider DDoS absorption for L3/L4 but demand custom L7 rules for login and API endpoints.
- Stakeholder alignment: IAL3 crosses Identity, Product, Legal/Compliance, and vendor management. DDoS crosses SRE, Network, and the edge/CDN team. Behavioral biometrics crosses Privacy, Product, Security, and ML. Each gap requires a different coalition and a different success metric.

## Scenario Challenge
You operate a global financial services platform. Recent events:
- A fraud ring has been opening accounts at scale using synthetic identities (generated SSNs, AI-generated ID photos). Your current onboarding is email + phone verification (IAL1). Compliance has given you **90 days** to implement IAL2 proofing for all new accounts.
- Simultaneously, you're under a sustained mixed-mode DDoS: **200Gbps volumetric** (absorbed by your edge) plus **application-layer credential stuffing** at 50k RPS against your login endpoint, rotating source IPs every 30 seconds. Your IP-based rate limiter is ineffective.
- Your security team proposes adding behavioral biometrics to detect session hijacking from infostealers. Privacy/Legal flags that your EU user base requires GDPR Art. 9 compliance for biometric data processing.

Constraints:
- **Latency/SLO:** login p95 must stay under 1.5s; proofing flow must complete in under 3 minutes; behavioral scoring must add <50ms to sensitive action paths.
- **Reliability:** proofing vendor has 99.9% SLA (8.7 hours downtime/year) — you can't block onboarding during vendor outages. Edge must absorb attacks without origin impact.
- **Security:** stop synthetic identity fraud at account creation; stop credential stuffing at login; detect session hijacking post-authentication.
- **Privacy/compliance:** IAL2 document images must be retained per KYC but purged after retention period; behavioral data must comply with GDPR biometric processing rules; DDoS logs must not contain PII beyond source IP.
- **Developer friction:** 3 mobile apps and a web app share a single auth stack; proofing, rate limiting, and behavioral scoring must be centralized, not per-app.
- **Migration/back-compat:** existing accounts are IAL1; you cannot force re-proofing of all existing users, but you must risk-tier them and require proofing for privilege escalation.
- **Incident/on-call twist:** your proofing vendor goes down during the DDoS attack. New user signups are failing. Product demands you bypass proofing temporarily. Compliance says no. What's your degraded mode?
- **Multi-team/leadership twist:** Product wants zero friction on onboarding, Privacy wants minimal data collection, Compliance wants IAL2 now, SRE wants no new hot-path dependencies, and the fraud team wants behavioral signals on every session. Drive a decision with tiered controls, explicit risk acceptance, and measurable success criteria.

**Evaluator Rubric**
A strong Staff answer demonstrates:
- Clear separation of the three problems (proofing, DDoS, behavioral) with a unified architectural narrative about how they interact (proofing feeds trust tiers, DDoS threatens availability of all controls, behavioral signals enrich session trust).
- Explicit assumptions about vendor dependencies (proofing vendor SLA, edge provider capacity, scoring service availability) and failure modes for each.
- Tiered approach: what you enforce immediately (edge rate limiting with composite keys, proofing for new high-risk accounts) vs. what you defer (behavioral biometrics to enrichment-only while baselines stabilize).
- Concrete rollout plan with measurable milestones: proofing conversion rate, fraud account creation rate, L7 attack mitigation rate, behavioral FPR by segment.
- Privacy-aware architecture: on-device feature extraction for behavioral signals, purpose-bound retention, and explicit GDPR Art. 9 compliance plan.
- Incident plan for the compound failure (vendor down + DDoS active): what degrades, what fails closed, and who approves temporary risk acceptance.
- Stakeholder handling: resolves Product vs. Compliance vs. Privacy tension with tiered controls and data-driven thresholds rather than ideology.
- Demonstrates awareness that these three gaps connect to the main syllabus (IAL feeds into passkey trust from Ep 4, DDoS threatens the proxy from Ep 5, behavioral signals feed into CAEP/detection from Ep 2 and Ep 9).
