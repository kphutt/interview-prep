**Episode 7 — The Cloud Metadata Attack: SSRF → Instance Credentials (Defense-in-Depth Guardrails)**

2) **The Hook (The core problem/tension).**
- SSRF bugs turn your server into an attacker-controlled HTTP client.  
- Cloud metadata endpoints hand out powerful credentials—so SSRF becomes **cloud account compromise**.  
- Fixing every app is slow; you need **platform and network guardrails** that don’t break production.

3) **The "Mental Model" (A simple analogy).**  
SSRF is convincing a receptionist to fetch documents on your behalf. The metadata endpoint is the locked server room—your receptionist should never be able to enter it, even if tricked.

4) **The "L4 Trap" (Common junior mistake + why it fails at scale).**
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