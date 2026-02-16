**Episode 6 — ALTS in Practice: Workload Identity mTLS for Service‑to‑Service Zero Trust**

2) **The Hook (The core problem/tension).**
- East-west traffic is where attackers pivot: once inside, IP-based trust collapses.  
- You need **mutual auth + encryption** between services, decoupled from topology.  
- Strong identity is easy to specify and hard to operate: cert issuance, rotation, latency, and debugging can crush teams.

3) **The "Mental Model" (A simple analogy).**  
Instead of “you’re allowed because you’re in this building (subnet),” it’s “you’re allowed because you’re *Alice from Payments* (workload identity).” Every RPC is like a phone call with verified caller ID on both ends.

4) **The "L4 Trap" (Common junior mistake + why it fails at scale).**
- “Just trust the VPC / cluster network.” Security-only thinking ignores how quickly attackers move laterally once any pod is compromised.  
- “Make certs super short-lived everywhere.” You’ll DoS your own CA/identity plane and turn cert rotation into a constant incident.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Workload identity (naming):** represent service identity as a stable principal (e.g., `spiffe://prod/ns/payments/sa/charge`) mapped to IAM/authz rules.  
- **Certificate minting (protocol detail):** workload requests an X.509 cert via **CSR (PKCS#10)** to an internal CA (often via node attestation); returns cert chain + trust bundle.  
- **mTLS handshake (crypto detail):** use **TLS 1.3 mTLS**; validate chain, `NotBefore/NotAfter`, and identity in **SAN URI/DNS**; reject missing/incorrect SAN.  
- **Identity propagation:** authorization decisions should key off **peer identity from TLS**, not headers; for RPC, surface the peer principal into request context for logging/policy.  
- **AuthZ policy:** enforce “who can call which method” (e.g., allow principal X to call `payments.Charge/Create`); keep policies versioned and reviewable.  
- **Data-plane caching #1 (credentials):** cache cert/key material locally; rotate at ~50% lifetime with jitter; hot-reload without restarting the app/sidecar.  
- **Data-plane caching #2 (handshake amortization):** rely on **HTTP/2 connection pooling** and **TLS session resumption** (session tickets) to keep handshake CPU off the p99 path.  
- **Operational detail #1 (CA dependency):** design so services keep running during CA outages (existing certs remain valid); pick lifetimes that balance revocation vs availability.  
- **Operational detail #2 (debuggability):** dashboards for `mtls_handshake_failures{reason}`, `cert_renewal_errors`, `rbac_denies`, and `cert_expiry_seconds`; include peer principal in traces (don’t log full certs).  
- **Clock skew gotcha:** cert validity failures often come from bad time sync; treat NTP as part of your identity SLO.  
- **Policy/control:** enforce “mTLS required” by namespace/environment (prod first); allow exceptions only with explicit owner + sunset date.  
- **Explicit threat/failure mode:** without workload identity, a compromised pod can spoof source IP and pivot; with mTLS, stolen node keys still enable impersonation until expiry—require node quarantine + rapid containment.  
- **Industry Equivalent:** Service mesh mTLS with workload identity (SPIFFE/SPIRE, Istio/Linkerd, Envoy SDS).

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** IP allowlists + shared secrets (fast; brittle; lateral movement friendly).  
  - **B)** Per-request JWT auth at app layer (fine-grained; adds per-service complexity and parsing overhead).  
  - **C)** **Workload identity mTLS via mesh/library** (uniform, strong; introduces identity-plane ops).  
- I pick **C** as the default: enforce mTLS at the platform layer, then layer method-level authz where needed.  
- Decisive trade-off: accept mesh/identity-plane complexity to eliminate topology-based trust; mitigate with connection reuse and strong tooling.  
- What I’d measure: handshake rate per instance, CPU cost of TLS, p99 latency deltas, cert renewal success rate, unauthorized call attempts blocked, and MTTR for “mTLS broke prod” incidents.  
- Risk acceptance: I’ll accept **24h-ish cert lifetimes** to survive CA incidents, but require strong node hardening + fast quarantine on compromise.  
- Stakeholder/influence: partner with platform + SRE to ship a “who am I / who called me” debugging tool and a staged enforcement plan (audit → permissive → strict).

7) **A "Scenario Challenge" (Constraint-based problem).**
- You run **3,000 microservices** across 5 regions; east-west traffic is **2M RPS**; budget is **+3ms p99** for auth overhead.  
- Current control is “namespace IP allowlists” and some shared API keys; you’ve had a lateral movement incident.  
- Reliability: auth must keep working through CA/identity-plane outages—no per-RPC calls to IAM/CA.  
- Security: require mutual auth + encryption; prevent service spoofing; support per-method authorization for sensitive RPCs.  
- Privacy/compliance: need auditable “service X called service Y” logs for 180 days, without logging payloads/secrets.  
- Developer friction: most teams will not change code this half; solution must be sidecar/mesh or a drop-in library.  
- Migration/back-compat: 10% of services are legacy raw TCP and can’t speak TLS for 6 months—design bridging and phased enforcement.  
- Incident/on-call twist: cert renewal fails for a subset due to clock skew; error rates spike. What’s your rollback and blast-radius containment?  
- Multi-team/leadership twist: product refuses latency regressions, security wants strict mTLS everywhere, platform dislikes sidecars—drive a decision with explicit metrics and exception policy.

---

1) **The Title (Catchy and technical).**