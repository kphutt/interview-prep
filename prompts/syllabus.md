# CHUNKED SYLLABUS GENERATOR PROMPT (Core + Frontier), with run controls
# Purpose: Generate the syllabus in multiple high-quality runs (scaffold -> core batches -> frontier digests -> optional gaps).

=====================
RUN CONFIG
=====================
MODE: {MODE}
CORE_EPISODES: {CORE_EPISODES}
FRONTIER_DIGEST: {FRONTIER_DIGEST}
AS_OF_OVERRIDE: {AS_OF_OVERRIDE}

=====================
ROLE + GOAL
=====================
You are a {ROLE} at {COMPANY} acting as an expert interview coach.

GOAL
Create a "Deep Dive Podcast Syllabus" for a {ROLE} {DOMAIN} Interview.
The audience is {AUDIENCE}. Content must focus on Architecture, Trade-offs, Latency, and Developer Friction.

CRITICAL FRAMING
- This is NOT a textbook. It is Staff-level interview prep: crisp mental models + concrete mechanisms + trade-off arguments.
- Every core episode (Episodes 1-{TOTAL_CORE}) must be both:
  - Domain: identity/infrastructure mechanics (protocols, architecture, threats).
  - RRK: role-related knowledge beyond identity (incident response judgment, risk prioritization under ambiguity, operational excellence/SRE thinking, stakeholder influence, and policy/compliance trade-offs).
- Do NOT add new top-level per-episode sections beyond the required 7 components. Instead, weave RRK into the existing components (especially Nitty Gritty, Staff Pivot, Scenario Challenge, and L4 Trap).
- Freshness / "latest & greatest" content must NOT be crammed into each core episode. It will be handled via dedicated Frontier Digest episodes (Episodes {FRONTIER_RANGE}).

=====================
OUTPUT RULES BY MODE
=====================
You MUST follow the MODE exactly. Output ONLY what the mode asks for.

MODE = SCAFFOLD
- Output ONLY:
  1) "How to use this syllabus" (5-8 bullets)
  2) "CISSP Coverage Map" table (includes Episodes 1-{TOTAL_CORE} + Frontier Digests {FRONTIER_RANGE}; and optional gap episodes only if later generated)
  3) "Syllabus Index" table in LISTENING ORDER (includes Episodes 1-{TOTAL_CORE} + Frontier Digests {FRONTIER_RANGE}; gap episodes only if later generated)
- Do NOT output any episode agendas in this mode.

MODE = CORE_BATCH
- Output ONLY the episode agendas for the specified CORE_EPISODES range.
- Do NOT output How-to, CISSP map, Index, Frontier Digests, or any other episodes.

MODE = FRONTIER_DIGEST
- Output ONLY the single Frontier Digest agenda specified by FRONTIER_DIGEST (A or B or C).
- Do NOT output How-to, CISSP map, Index, or any core episode agendas.
- Use Episode numbering:
{FRONTIER_MAP}

MODE = FINAL_MERGE
- Output ONLY:
  1) "How to use this syllabus" (5-8 bullets)
  2) "CISSP Coverage Map" table
  3) "Syllabus Index" table in LISTENING ORDER
- Do NOT output episode agendas in this mode.
- If prior runs exist in the conversation, use the actual generated episode titles; otherwise, use canonical titles from the training data and defined Frontier Digest titles.

=====================
OUTPUT PACKAGE (used in SCAFFOLD and FINAL_MERGE)
=====================
1) How to use this syllabus (5-8 bullets)
   - Explain how each episode agenda becomes: (a) a deep doc, (b) a podcast segment, (c) interview practice prompts, (d) quizzes/flashcards.
   - Keep it practical and action-oriented.

2) CISSP Coverage Map (table)
   - Create a table mapping each episode (including Frontier Digests and any gap episodes) to 1-3 CISSP domains (tags) + one-line justification (<= 18 words).
   - Ensure coverage across ALL 8 CISSP domains at least once across the full syllabus.

3) Syllabus Index (table)
   Columns: Episode #, Title, Primary Focus, Primary CISSP domains (tags), Primary Interview Axis (Domain / RRK / Mixed), Key trade-off (<= 10 words)
   Listening order: {LISTENING_ORDER}

=====================
EPISODE AGENDAS (used in CORE_BATCH, FRONTIER_DIGEST)
=====================
For EACH episode, generate a detailed Agenda with EXACTLY these 7 required components (in this order):
1) The Title (Catchy and technical).
2) The Hook (The core problem/tension). 2-4 bullets.
3) The "Mental Model" (A simple analogy). 2-3 sentences.
4) The "L4 Trap" (Common junior mistake + why it fails at scale). 1-2 bullets.
5) The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality). 8-14 bullets MAX.
   Must include: 2 protocol/crypto details, 2 data-plane/caching details, 2 operational details, 1 policy/control detail, 1 explicit threat/failure mode.
   If {COMPANY}-internal terms used, add: "Industry Equivalent: <generic term(s)>" (<= 2 lines).
6) The "Staff Pivot" (Architectural trade-off argument). 4-7 bullets.
   Must include: 2+ competing architectures + decisive trade-off, "what I'd measure", stakeholder/influence/risk acceptance angle.
7) A "Scenario Challenge" (Constraint-based problem). 6-10 bullets.
   Must include constraints across: latency/SLO, reliability, security, privacy/compliance, developer friction.
   Must include: incident/on-call twist, multi-team/leadership twist, migration/backwards-compat constraint.

RRK INTEGRATION (embed in the 7 components, do not create new sections)
- L4 Trap: call out failure of "security-only thinking"
- Nitty Gritty: operational hooks (logs, metrics, pages, rollout breakage)
- Staff Pivot: prioritize risks under incomplete facts, choose now vs later, influence stakeholders
- Scenario: force clarifying questions, assumptions, constraints, rollout + incident plan

=====================
FRONTIER DIGEST RULES (used only when MODE=FRONTIER_DIGEST)
=====================
- Cover recent + near-future standards, capabilities, threat shifts for Identity & Infrastructure.
- Every frontier item MUST include: As-of date, Maturity (Draft/Emerging/Adopted/Deployed), Confidence (High/Medium/Low), Anchor (RFC/IETF draft/CVE/vendor feature/regulatory milestone).
- Nitty Gritty: include ONE "Touchpoints" bullet referencing covered core episodes, plus 3-6 frontier items in micro-format.
- Time windows: Recent (18 months), Near-Future (6-12 months), optional Watchlist (12-24 months, label speculative).

=====================
QUALITY SELF-CHECK (run silently; revise until true)
=====================
- Output matches MODE exactly (no extra sections).
- Every episode has real protocols/claims/headers (not vague generalities).
- Every core episode includes RRK (ops + risk + influence) in existing sections.
- Frontier Digests include Maturity + Confidence + Anchor for every item.
- No section violates length limits.

=====================
TRAINING DATA (SOURCE OF TRUTH)
=====================
Use the following 12 examples as the definition for depth and content.
Do NOT summarize them. Expand on them using the specific technical details provided.

---

### Episode 1: The Binding Problem (mTLS vs DPoP)
**Focus:** Prevention of Token Theft & Replay
**Mental Model:** "Cash (Bearer) vs. Credit Card with PIN (Sender-Constrained)."
**The L4 Trap:** "Rotate tokens faster (5 mins)." (Fails to stop immediate replay; DDOS-es IdP).
**The Nitty Gritty:**
- **mTLS:** Client presents X.509 cert in TLS handshake. LB (GFE) hashes cert. Access Token `cnf` claim has thumbprint. API checks connection hash.
- **DPoP:** `DPoP` HTTP Header contains JWT signed by device key. Payload includes `htu`, `htm`, `ath`. Server sends `DPoP-Nonce` for liveness.
**The Staff Pivot:** "Infrastructure binding (mTLS) for servers (invisible to devs). App-layer binding (DPoP) for mobile (avoids client cert nightmare)."

### Episode 2: The Session Kill Switch (Revocation)
**Focus:** Immediate Access Termination
**Mental Model:** "Pulling the plug vs. Waiting for the battery to die."
**The L4 Trap:** "Short TTL on tokens." (Trade-off is too harsh).
**The Nitty Gritty:**
- **Shared Signals (CAEP/RISC):** "Push" model events.
- **Payload:** JSON event `risk-account-compromised` sent to webhook.
- **Receiver:** Service verifies ECDSA signature, updates local Redis blocklist or invalidates cache immediately.
**The Staff Pivot:** "Trade 'Time-to-Live' for 'Time-to-Kill'. Long sessions (UX) + Event-Driven Revocation (Security)."

### Episode 3: Mobile Identity (The Confused Deputy)
**Focus:** Stopping App Impersonation
**Mental Model:** "Checking the ID badge, not just the uniform."
**The L4 Trap:** "Custom URL Schemes (`myapp://`) + Client Secrets." (Hijackable).
**The Nitty Gritty:**
- **Universal Links:** OS checks `.well-known/assetlinks.json` on domain to verify app signature.
- **PKCE:** `code_verifier` (random) -> `code_challenge` (hash). Server verifies `SHA256(verifier) == challenge`.
**The Staff Pivot:** "Mobile security requires proving *App Identity* (Binary Signature) before proving *User Identity*."

### Episode 4: Auth at the Edge (Passkeys)
**Focus:** Phishing Resistance
**Mental Model:** "A physical key that only fits one specific lock (Origin Binding)."
**The L4 Trap:** "Disable passwords immediately." (Support costs explode).
**The Nitty Gritty:**
- **WebAuthn:** `navigator.credentials.create()` vs `get()`.
- **Origin Binding:** Browser enforces domain (stops `g00gle.com`).
- **Sync vs Bound:** iCloud Keychain (Synced/Recoverable) vs YubiKey (Device-Bound/Secure).
**The Staff Pivot:** "Segment users: Consumers get Synced Passkeys (Availability). Admins get Device-Bound Keys (Security)."

### Episode 5: BeyondCorp (Zero Trust Proxy)
**Focus:** Removing the VPN
**Mental Model:** "Passport control at every door, not just at the border."
**The L4 Trap:** "Expose app with a login page." (Vulnerable to exploits).
**The Nitty Gritty:**
- **GFE (Proxy):** Terminates TLS, enforces policy *before* app logic.
- **Context-Aware Access:** `Allow IF (User + Device_Tier + Location)`.
- **Inventory Service:** Source of Truth for device state.
**The Staff Pivot:** "Identity is the new Firewall. Move control from Layer 3 (IP) to Layer 7 (Proxy)."

### Episode 6: ALTS (Service Identity)
**Focus:** Service-to-Service Zero Trust
**Mental Model:** "Not 'Where are you?' (IP), but 'Who are you?' (Job/User)."
**The L4 Trap:** "Trust the Intranet/IP Whitelists." (Lateral movement risk).
**The Nitty Gritty:**
- **Identity:** Bound to **Borg User/Job**.
- **Handshake:** Service gets Ticket from Master Guard. Handshake uses Resumption Tickets for speed.
**The Staff Pivot:** "Decouple Identity from Topology. Services move anywhere; Identity follows."

### Episode 7: The Cloud Metadata Attack (SSRF)
**Focus:** Infrastructure Defense
**Mental Model:** "Giving the visitor a badge, but locking the server room."
**The L4 Trap:** "Regex blacklist the IP." (Bypassable).
**The Nitty Gritty:**
- **IMDSv2:** Requires `PUT` for Session Token. Header `X-aws-ec2-metadata-token`.
- **Sidecar Proxy:** Envoy drops traffic to metadata IP unless authorized.
**The Staff Pivot:** "Defense in Depth: Fix Platform (IMDSv2) + Network (Sidecar) + App (Validation)."

### Episode 8: Supply Chain (SLSA)
**Focus:** Trusting the Binary
**Mental Model:** "Buying food with a 'Certified Organic' seal vs. trusting a roadside stand."
**The L4 Trap:** "Trust developer signatures." (Keys stolen).
**The Nitty Gritty:**
- **SLSA L3:** Hermetic (No network) + Ephemeral Build.
- **Provenance:** Signed JSON: "I built X from Commit Y."
- **Binary Auth:** Kubernetes checks signature at deploy time.
**The Staff Pivot:** "Shift trust from Person (Developer) to Platform (Build Service)."

### Episode 9: Detection Engineering
**Focus:** Finding the Needle
**Mental Model:** "Not looking for a specific face, but looking for nervous behavior."
**The L4 Trap:** "Alert on Failed Logins." (Noisy).
**The Nitty Gritty:**
- **DNS:** High Entropy (DGA) domains.
- **Netflow:** Long Duration / Low Bytes (C2 Heartbeat).
- **Process:** Parent-Child anomalies.
**The Staff Pivot:** "Detection as Code. Rules tested in CI/CD. Measure Signal-to-Noise."

### Episode 10: Crypto Agility (Post-Quantum)
**Focus:** Future-Proofing
**Mental Model:** "Changing the engine of the car while driving."
**The L4 Trap:** "Wait for the computers." (Store Now, Decrypt Later).
**The Nitty Gritty:**
- **Hybrid Key Exchange:** X25519 (Classical) + Kyber/ML-KEM (Quantum) in TLS.
- **Tink:** Abstract primitives (`KeyHandle.sign()`) for config-based rotation.
**The Staff Pivot:** "Abstract the primitive so we can rotate math without deploying code."

### Episode 11: Data Protection (Envelope Encryption)
**Focus:** Encrypting at Scale
**Mental Model:** "Putting the letter in an envelope, and putting the envelope in a safe."
**The L4 Trap:** "Use one key for everything." (Key rotation requires re-encrypting petabytes).
**The Nitty Gritty:**
- **DEK (Data Encryption Key):** Encrypts the data chunk. Stored *next* to the data, encrypted.
- **KEK (Key Encryption Key):** Encrypts the DEK. Stored in KMS (HSM).
- **Rotation:** To rotate, you only re-encrypt the DEKs with the new KEK. You do *not* touch the petabytes of data.
**The Staff Pivot:** "We optimize for 'Rotation Latency'. Envelope Encryption allows us to 'rotate' access to 1PB of data in milliseconds by rotating one KEK."

### Episode 12: Insider Risk (Multi-Party Auth)
**Focus:** The Rogue Admin
**Mental Model:** "The Two-Man Rule on a nuclear submarine."
**The L4 Trap:** "Trust Admins / Background Checks." (Good people break or get coerced).
**The Nitty Gritty:**
- **MPA (Multi-Party Authorization):** Admin requests access to Prod. A *different* qualified peer must approve.
- **JIT (Just-in-Time):** Access is granted for 1 hour, then revoked.
- **Break Glass:** Emergency access bypasses MPA but triggers P0 alerts to Security.
**The Staff Pivot:** "Zero Trust applies to employees too. No standing privileges. All access is ephemeral and peer-reviewed."
