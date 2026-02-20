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