1) **The Title (Catchy and technical).**  
**Episode 5 — BeyondCorp: Building a Zero‑Trust Proxy (Identity‑Aware Access Without the VPN)**

2) **The Hook (The core problem/tension).**
- VPNs assume “inside = trusted,” but your users, devices, and workloads are everywhere.  
- You want **policy at Layer 7** (“who + what device + what risk”) before traffic hits apps.  
- Centralizing control in a proxy simplifies enforcement—but concentrates **latency, blast radius, and ops burden**.

3) **The "Mental Model" (A simple analogy).**  
A VPN is checking passports only at the border. Zero Trust is **passport control at every door**: every request shows identity plus a “health certificate” (device posture), and the door decides whether you enter.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “Just put a login page in front of each app.” Security-only thinking ignores **device posture**, **session binding**, and consistency across 200+ apps.  
- “Fail closed globally if a dependency is down.” You’ll trade “more secure” for a **company-wide outage**.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Proxy TLS termination + re-encryption:** proxy terminates external TLS and establishes **new TLS** to upstream; prefer **proxy→backend mTLS** to prevent header spoofing.  
- **OIDC at the proxy (protocol detail):** proxy runs **Authorization Code (+ PKCE where applicable)**, validates `id_token` (`iss`, `aud`, `exp`, `nonce`) and maintains a session cookie.  
- **Signed identity assertion to the app (crypto detail):** forward identity as a **JWT** (or a signed header blob) with `sub`, `email`, `groups`, `acr/amr`, `exp`, and a `kid`; apps/gateways verify via JWKS.  
- **Context-aware access:** proxy evaluates policy on `(user, device_trust_tier, location, app, path, risk)` before forwarding.  
- **Device posture source-of-truth:** posture comes from an inventory/MDM-like service (patch level, disk encryption, screen lock, cert presence); treat it as *security-critical data*.  
- **Data-plane caching #1 (policy):** cache **compiled policies** + JWKS in-memory keyed by `(policy_version, kid)`; use stale-while-revalidate to avoid thundering herds.  
- **Data-plane caching #2 (posture):** cache posture results per device for short TTL (e.g., 1–5 min) plus **push invalidation** for posture changes; negative-cache denies to protect the inventory backend.  
- **Non-HTTP reality:** for SSH/RDP or raw TCP, you often need a **TCP proxy** pattern (or protocol-aware gateway) that still attaches identity/context.  
- **Operational detail #1 (dependency tiers):** when posture/inventory is degraded, use **tiered failure behavior** (fail-closed for prod/admin apps, fail-open or “step-up required” for low-risk).  
- **Operational detail #2 (telemetry):** track `policy_denied_total{reason}`, `inventory_lookup_latency`, `auth_redirect_rate`, `proxy_upstream_connect_errors`, `added_latency_ms{p95,p99}`; audit log with **policy_version** and decision inputs (not full query strings).  
- **Policy/control:** define minimum “device tier” per app/scope (e.g., “prod requires managed device + phishing-resistant auth”), with an **exception process + expiry**.  
- **Explicit threat/failure mode:** trusting **spoofable identity headers** (or over-caching posture) enables attackers to reuse stolen sessions from unmanaged devices.  
- **Industry Equivalent:** ZTNA / Identity‑Aware Proxy (IAP) gateway + device posture service + policy engine (OPA/Rego/CEL).

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** VPN + subnet ACLs (simple mental model; weak against device compromise and lateral movement).  
  - **B)** Per-app authn/z (flexible; inconsistent and slow to migrate across many teams).  
  - **C)** **Central identity-aware proxy** (consistent controls; proxy becomes tier-0 infra).  
- I pick **C** for most internal apps, with a **TCP proxy** adjunct for legacy protocols—because policy consistency beats bespoke implementations.  
- Decisive trade-off: accept **central choke point** risk in exchange for **uniform enforcement**; mitigate via multi-region, aggressive caching, and explicit degraded-mode policies.  
- What I’d measure: **p99 added latency**, proxy error budget burn, posture cache hit rate, deny-rate by reason (misconfig vs true risk), and time-to-onboard per app.  
- Risk acceptance: I’ll accept **fail-open for low-risk read apps** during posture outages (audited), but **not** for prod/admin paths.  
- Stakeholder/influence: align IT/MDM (device signals), SRE (proxy SLOs), app owners (JWT/header verification), and Privacy (minimal device data) around a published “golden path” onboarding kit.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You must retire VPN access for **80k employees** within **9 months**; target **99.99%** availability and **<20ms p99** proxy overhead.  
- App mix: 150 web apps, 30 internal APIs, plus legacy SSH/RDP to jump hosts—many apps cannot change code quickly.  
- Security: enforce `Allow IF (user group + device tier + geo/risk)`; prevent stolen session cookies from being replayed on unmanaged devices.  
- Privacy/compliance: keep auditable access logs for 1 year but avoid logging sensitive URLs/query params or stable device identifiers unnecessarily.  
- Developer friction: 200 app owners; need self-serve onboarding and minimal per-app changes (proxy should do most work).  
- Migration/back-compat: must run VPN and ZT proxy in parallel; some scripts depend on IP allowlists—provide a deprecation path.  
- Incident/on-call twist: posture inventory backend has a regional outage; deny rate spikes and executives can’t reach critical tools—where do you fail open/closed and what do you cache?  
- Multi-team/leadership twist: Security wants “managed devices only,” HR needs contractors supported, SRE refuses new hard dependencies—propose tiered policy + exception governance with rollback triggers.

---

1) **The Title (Catchy and technical).**  
**Episode 6 — ALTS in Practice: Workload Identity mTLS for Service‑to‑Service Zero Trust**

2) **The Hook (The core problem/tension).**
- East-west traffic is where attackers pivot: once inside, IP-based trust collapses.  
- You need **mutual auth + encryption** between services, decoupled from topology.  
- Strong identity is easy to specify and hard to operate: cert issuance, rotation, latency, and debugging can crush teams.

3) **The "Mental Model" (A simple analogy).**  
Instead of “you’re allowed because you’re in this building (subnet),” it’s “you’re allowed because you’re *Alice from Payments* (workload identity).” Every RPC is like a phone call with verified caller ID on both ends.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
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
**Episode 7 — The Cloud Metadata Attack: SSRF → Instance Credentials (Defense-in-Depth Guardrails)**

2) **The Hook (The core problem/tension).**
- SSRF bugs turn your server into an attacker-controlled HTTP client.  
- Cloud metadata endpoints hand out powerful credentials—so SSRF becomes **cloud account compromise**.  
- Fixing every app is slow; you need **platform and network guardrails** that don’t break production.

3) **The "Mental Model" (A simple analogy).**  
SSRF is convincing a receptionist to fetch documents on your behalf. The metadata endpoint is the locked server room—your receptionist should never be able to enter it, even if tricked.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “Blacklist `169.254.169.254` with a regex.” Security-only thinking ignores redirects, DNS rebinding, IPv6, and proxy paths—attackers bypass it.  
- “Just require IMDSv2 and call it solved.” It reduces risk but doesn’t eliminate SSRF-driven credential theft by itself.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **SSRF blast radius:** attacker forces requests to link-local metadata (`169.254.169.254`) and exfiltrates returned tokens/credentials.  
- **AWS IMDSv2 (protocol detail):** `PUT /latest/api/token` with `X-aws-ec2-metadata-token-ttl-seconds`; then `GET` metadata with `X-aws-ec2-metadata-token: <token>`.  
- **GCP metadata (protocol detail):** requires `Metadata-Flavor: Google` request header and returns the same header; still reachable via SSRF if headers are attacker-controlled.  
- **Azure IMDS (protocol detail):** `GET /metadata/identity/oauth2/token?...&api-version=...` with header `Metadata: true`.  
- **Data-plane/caching #1 (IMDSv2 token):** clients cache the IMDSv2 session token in-memory until TTL; ensure it’s never logged and not shared across tenants/containers.  
- **Data-plane/caching #2 (cloud creds):** SDKs cache and refresh temporary credentials; stolen creds remain valid until expiry—factor this into your kill-time expectations.  
- **Network guardrail:** enforce egress controls (iptables/eBPF/Envoy/network policy) blocking access to metadata IPs by default; allow only trusted agents that truly need it.  
- **Platform hardening:** disable IMDSv1 where possible; set metadata hop-limit / routing constraints so metadata is not reachable through unintended proxying paths.  
- **App-layer pattern:** build a “safe fetcher” that allowlists schemes/ports, blocks private/link-local ranges post-DNS-resolve, forbids redirects to private ranges, strips sensitive headers, and uses tight timeouts.  
- **Operational detail #1 (detection):** alert on unexpected metadata egress attempts and unusual STS/credential APIs; dashboard counts of blocked `169.254.169.254` traffic by workload.  
- **Operational detail #2 (incident runbook):** quarantine instance/pod, rotate/disable the instance profile or service account, search for exfil signals, and patch the SSRF entry point.  
- **Policy/control:** default-deny metadata egress org-wide; explicit allow with owner + justification; CI/IaC checks prevent “oops we re-enabled IMDSv1.”  
- **Explicit threat/failure mode:** blocking metadata without a supported workload-identity path can push teams to hardcode long-lived keys—worsening risk long-term.  
- **Industry Equivalent:** IMDS hardening (IMDSv2) + egress filtering (network policies/sidecar proxy) + SSRF-safe URL fetcher.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** App-only URL validation (slow, inconsistent, bypass-prone).  
  - **B)** Cloud-only hardening (IMDSv2) without egress controls (better, but still reachable from SSRF).  
  - **C)** **Defense in depth:** IMDSv2 + network egress blocks + safe fetcher + detection (most robust).  
- I pick **C** and sequence it: deploy **monitor-only egress telemetry first**, then block with allowlisted exceptions, while shipping a safe-fetcher golden path.  
- What I’d measure: metadata egress attempts, false positive blocks, time-to-fix SSRF classes, credential theft incidents, and latency impact of egress proxying.  
- Risk acceptance: I’ll accept temporary exceptions for a small set of legacy agents, but I won’t accept broad metadata reachability from general workloads.  
- Stakeholder/influence: align cloud/platform, app teams, and SRE on a single “credential acquisition” story so security controls don’t create outages.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You run a multi-tenant service that fetches user-provided URLs (webhooks + image fetch) at **60k RPS**, with **<10ms p99** added latency budget and **99.95%** availability.  
- Security: prevent SSRF to metadata and internal admin services; attacker controls URL inputs and may influence headers/redirects.  
- Reliability: the service runs on both AWS and GCP; you need controls that work cross-cloud and during partial cloud outages.  
- Privacy/compliance: can’t log full URLs (they may contain secrets); must keep auditable records of blocked SSRF attempts for 90 days.  
- Developer friction: dozens of teams use a shared HTTP client; you need a centralized solution (library + egress gateway), not bespoke app fixes.  
- Migration/back-compat: some workloads legitimately hit metadata today for credentials—transition them to workload identity / approved agent without a flag day.  
- Incident/on-call twist: after rolling out metadata egress blocks, a subset of workloads starts 500ing because they can’t fetch creds. How do you triage, mitigate, and prevent whack-a-mole exceptions?  
- Multi-team/leadership twist: security demands “block now,” platform fears outages, product demands no customer impact—propose rollout phases, exception governance, and success metrics.

---

1) **The Title (Catchy and technical).**  
**Episode 8 — Supply Chain Security: SLSA Provenance + Deploy‑Time Verification (Trust the Binary, Not the Builder)**

2) **The Hook (The core problem/tension).**
- If CI/build gets compromised, you can ship a perfect-looking binary that’s malicious.  
- Vulnerability scanning finds known bad code; it doesn’t prove **who built this artifact from what source**.  
- Strong supply-chain controls can slow builds and block releases—so the real challenge is **measurable rollout + safe break-glass**.

3) **The "Mental Model" (A simple analogy).**  
Provenance is a tamper-evident receipt: “This artifact came from commit X, built by builder Y, with dependencies Z.” Deploy-time verification is the bouncer checking the receipt before letting the artifact into production.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “Have developers sign artifacts with PGP.” Security-only thinking ignores key theft and the fact you need *platform trust*, not human trust.  
- “Just add an image scanner.” Scanners don’t stop a compromised builder from shipping malware *today*.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Artifact identity:** treat the artifact digest (e.g., `sha256:<...>`) as the canonical identity; tags like `:latest` are not security boundaries.  
- **SLSA provenance (protocol detail):** in-toto statement includes `_type`, `subject[].digest.sha256`, `predicateType` (e.g., `https://slsa.dev/provenance/v1`), and `predicate` with `builder.id`, `buildType`, `invocation`, `materials`.  
- **Signing (crypto detail):** wrap provenance in **DSSE** (`payloadType`, `payload`, `signatures[].sig`) or equivalent; verify signature against a trusted key/identity (KMS/HSM-backed).  
- **Hermetic/ephemeral builds:** isolate builds, pin toolchains, restrict network, and use ephemeral workers to reduce “persistent CI backdoor” risk (SLSA L3-style goals).  
- **Deploy-time verification:** an admission controller / deploy gate verifies (a) artifact signature, (b) provenance signature, and (c) provenance matches policy (trusted builder, trusted repo, reviewed commit).  
- **Data-plane/caching #1 (admission decisions):** cache `(image_digest, policy_version) -> allow/deny` briefly to avoid repeated signature/provenance verification at high deploy QPS.  
- **Data-plane/caching #2 (key material):** cache trusted keysets / trust bundles and handle `kid` rotation safely; stale-while-revalidate avoids deploy outages during key fetch glitches.  
- **Operational detail #1 (key lifecycle):** keep signing keys in KMS/HSM, rotate regularly, and maintain a “key compromise” playbook (block old keys, force rebuilds, audit blast radius).  
- **Operational detail #2 (rollout):** start in audit-only mode (measure missing provenance), then enforce for a narrow tier, then expand; instrument “why denied” to avoid developer dead-ends.  
- **Policy/control:** define required build provenance by environment (prod vs staging) and service tier; require exceptions to be time-bounded with explicit approver.  
- **Explicit threat/failure mode:** if build workers are long-lived with cached credentials, an attacker can persist and sign trojans indefinitely—provenance without ephemeral builders may provide false confidence.  
- **Industry Equivalent:** SLSA + in-toto attestations + Sigstore/cosign (or Notary v2) + Kubernetes admission control.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** “Trust CI logs + dev approvals” (weak against CI compromise; hard to audit).  
  - **B)** Vulnerability scanning only (necessary, not sufficient; doesn’t prove integrity/origin).  
  - **C)** **SLSA provenance + deploy-time verification** (strong integrity; requires platform investment).  
- I pick **C**, but I phase it: audit-only → enforce for internet-facing/prod → expand. This avoids a “security launch” turning into a release outage.  
- What I’d measure: % prod deploys with valid provenance, deny rate by reason, build-time delta, admission latency p99, and number of emergency break-glass uses.  
- Risk acceptance: I’ll accept a quarter of mixed mode for low-risk services, but I won’t accept unsigned/provenance-less artifacts in high-risk prod without a formal exception.  
- Stakeholder/influence: partner with DevProd/Release Eng and Compliance—frame it as “faster incident containment” (provenance answers “what’s running where?”) not just security purity.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You have **500 repos**, **2k builds/day**, and **300 Kubernetes clusters**. A competitor suffered a CI compromise—leadership demands supply-chain hardening.  
- Latency/velocity: build time must not increase by >10%; admission verification must add **<50ms p99**; deploy pipeline SLO is **99.99%**.  
- Reliability: verification cannot be a single point of failure; clusters must still deploy safely during partial outages (key server / transparency log / provenance store).  
- Security: ensure prod artifacts are built from reviewed commits on trusted builders; stop “developer laptop build” artifacts from reaching prod.  
- Privacy/compliance: keep an audit trail of “commit → build → artifact → deploy” without leaking secrets from build inputs or source.  
- Developer friction: teams use heterogeneous build tools; you need a golden path that doesn’t require every team to become supply-chain experts.  
- Migration/back-compat: most existing images are unsigned; you must support mixed mode with explicit deadlines and per-namespace enforcement.  
- Incident/on-call twist: enforcement goes live and blocks a critical hotfix because provenance upload failed—how do you break-glass safely and prevent permanent bypass?  
- Multi-team/leadership twist: compliance wants immediate enforcement, product wants zero deploy blocks, infra wants minimal new components—propose tiered policy, rollout phases, and exception governance.