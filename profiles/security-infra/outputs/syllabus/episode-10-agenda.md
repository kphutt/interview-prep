**Episode 10 — Crypto Agility (Post‑Quantum): Hybrid TLS + “Rotate the Math Without a Code Push”**

2) **The Hook (The core problem/tension).**
- Post-quantum isn’t a single migration; it’s a **multi-year compatibility problem** under live traffic.  
- “Store now, decrypt later” turns long-lived confidentiality into today’s risk.  
- Staff-level challenge: introduce PQ defenses **without** ossifying the protocol stack or blowing up latency/cost.

3) **The "Mental Model" (A simple analogy).**  
Crypto agility is changing a car engine while the car is doing 70 mph: you can’t stop the fleet, and not every driver upgrades at once. Hybrid crypto is like running **two engines in parallel** for a while so either one failing doesn’t crash the car.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “We’ll wait until PQ is fully standardized everywhere.” Security-only thinking ignores that long-lived secrets can be recorded today.  
- “Hardcode algorithms and key sizes in code.” You guarantee painful emergency migrations when primitives break or policies change.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Protocol detail (TLS negotiation):** in TLS 1.3, algorithm agility lives in ClientHello extensions (`supported_groups`, `signature_algorithms`, `key_share`); you need visibility into what clients actually offer/accept.  
- **Crypto detail (hybrid key exchange):** do **ECDHE (e.g., X25519)** + a PQ KEM (e.g., **ML‑KEM/Kyber class**) and combine secrets via HKDF to derive the handshake traffic keys; expect bigger ClientHello and more CPU.  
- **Interoperability reality:** keep certificates on widely supported classical signatures (ECDSA/RSA) while piloting PQ in key exchange; PQ signatures in X.509 are ecosystem-sensitive.  
- **JWT/JWS agility footgun:** enforce an allowlist for JOSE `alg` (e.g., `ES256`, `EdDSA`) and reject `alg=none`; don’t let “agility” become algorithm confusion.  
- **Abstraction layer:** use a primitive-agnostic API (e.g., `KeyHandle.sign()`, `Aead.encrypt()`) so call sites don’t know/care whether it’s RSA vs ECDSA vs PQ later.  
- **Key identification:** version keys with explicit `kid` (JWKS, JWS headers, or internal metadata) and support dual-verify windows during rotation.  
- **Data-plane/caching #1 (JWKS / key material):** cache JWKS/public keys with `Cache-Control`/ETag and stale-while-revalidate; avoid turning every signature verify into a network call.  
- **Data-plane/caching #2 (TLS session resumption):** maximize resumption (PSK/session tickets) to keep hybrid handshake cost off p99; monitor resumption rate as an SLI.  
- **Operational detail #1 (crypto inventory):** continuously inventory where algorithms are used (TLS endpoints, token signing, storage encryption) so you can target migrations and prove compliance.  
- **Operational detail #2 (safe rollout):** canary hybrid TLS by client segment; measure handshake failure reasons (hello size, middlebox intolerance) and provide fast rollback toggles.  
- **Policy/control:** a centralized crypto policy (minimum TLS version, disallowed curves, approved key sizes) enforced in CI and at runtime prevents drift across 100 services.  
- **Explicit threat/failure mode:** **downgrade/ossification**—middleboxes or legacy clients force weaker negotiation; if you don’t detect and block, “hybrid” becomes “mostly classical.”  
- **Emergency rotation plan:** practice “algorithm incident response” (e.g., sudden primitive break): staged disable, dual-sign/dual-decrypt window, and client impact comms.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing strategies:  
  - **A)** Do nothing until mandated (low effort now; high future risk + emergency migration likelihood).  
  - **B)** Big-bang PQ cutover (theoretically clean; practically breaks clients and creates outages).  
  - **C)** **Crypto-agile abstraction + hybrid in selected high-value paths** (best balance; requires discipline and observability).  
- I pick **C**: first make the platform **agile** (policy + APIs + telemetry), then selectively turn on hybrid where confidentiality horizon justifies cost.  
- Decisive trade-off: accept some handshake overhead and complexity to prevent “one-day emergency” migrations.  
- What I’d measure: handshake CPU/time, ClientHello size distribution, resumption rate, error rate by client library, and “time-to-rotate” for keys/algorithms.  
- Risk acceptance: I’ll accept partial PQ coverage (only certain endpoints/classes) early, but I won’t accept unknown algorithm usage (no inventory) or untested rollback.  
- Stakeholder/influence: align Compliance (roadmap), SRE (latency/cost), Product/Partners (client compatibility), and Security (threat horizon) on a phased plan and deprecation dates.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You operate an edge TLS termination layer at **300k RPS**; handshake p99 must stay **<30ms**, and overall availability is **99.99%**.  
- Security: a subset of data has a **10–15 year confidentiality** requirement (record-now-decrypt-later concern).  
- Reliability: you must support legacy clients (older Android, Java 8) and enterprise middleboxes; no flag day.  
- Privacy/compliance: gov region must remain **FIPS-aligned**; algorithm changes require audit evidence and rollback planning.  
- Developer friction: 100 internal services share a common crypto library; teams can’t rewrite call sites—agility must be mostly config/policy-driven.  
- Migration/back-compat: partners pin TLS settings; some can’t upgrade for 18 months; you must run dual policy and track who’s blocking progress.  
- Incident/on-call twist: after enabling hybrid TLS for 10% of traffic, CPU jumps 40% and some clients fail due to oversized ClientHello—what do you roll back, and what telemetry tells you why?  
- Multi-team/leadership twist: Compliance wants “PQ now,” SRE wants “no latency regression,” Partner Eng wants “no breakage”—propose phased enablement, exception governance, and weekly metrics.

---

1) **The Title (Catchy and technical).**