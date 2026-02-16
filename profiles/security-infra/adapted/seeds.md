<!-- DOMAIN_SEEDS -->
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
