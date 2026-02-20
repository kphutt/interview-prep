**Episode 12 — Insider Risk: JIT + Multi‑Party Authorization (MPA) Without Breaking On‑Call**

2) **The Hook (The core problem/tension).**
- Insider risk isn’t hypothetical: mistakes, coercion, compromised laptops, and disgruntled admins all exist.  
- Standing privileges reduce friction—but they turn “one bad day” into total compromise.  
- Staff-level challenge: enforce **two-person control + just‑in‑time access** while keeping incident response fast and auditable.

3) **The "Mental Model" (A simple analogy).**  
This is the two-person rule on a submarine: one person can start the process, but they can’t launch alone. JIT access is the key that only works for an hour; MPA is requiring a second key-turn from an independent operator.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “We trust admins; background checks are enough.” Security-only thinking ignores account takeover, coercion, and human error at scale.  
- “Require approvals for everything, always.” You’ll create an outage factory and a shadow-access culture (people bypass controls to get work done).

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Privilege taxonomy:** classify actions (prod config change, data export, key disable, break-glass) and map each to required approvals, duration, and logging requirements.  
- **Crypto detail (short-lived machine creds):** issue **OpenSSH certificates** (`ssh-ed25519-cert-v01@openssh.com`) with `valid_after/valid_before` and critical options (`source-address`, `force-command`) instead of distributing long-lived SSH keys.  
- **Protocol/crypto detail (short-lived web/API creds):** mint short-lived OIDC/OAuth tokens (`exp` 10–60m) with enforced assurance via `acr`/`amr` (step-up like WebAuthn UV required); gateways reject tokens missing required assurance.  
- **Request record:** every access request carries structured fields (`resource`, `role`, `reason`, `duration`, `ticket_id`); store the approval decision as an immutable record (often a signed blob/JWT) tied to a `request_id`.  
- **Data-plane/caching #1 (approver eligibility):** cache group membership/on-call rotation lookups with short TTL; push-invalidate on HR termination or role changes to avoid stale entitlements.  
- **Data-plane/caching #2 (active grants):** cache “active JIT grants” at enforcement points (bastions/gateways) keyed by `grant_id` until expiry; support emergency revocation via an epoch or push signal.  
- **Enforcement points:** unify across SSH bastions, Kubernetes (admission control for `kubectl exec`/`port-forward`), cloud role assumption, and internal admin APIs so “approved” means the same everywhere.  
- **Operational detail #1 (break-glass):** provide an emergency path that issues *even shorter-lived* access (e.g., 15m), triggers immediate paging to Security + duty manager, and auto-creates a postmortem/audit ticket.  
- **Operational detail #2 (auditability):** produce tamper-evident logs of “who requested, who approved, what was done, when” and alert on gaps; dashboards for approval latency and break-glass rate.  
- **Policy/control (separation of duties):** requester cannot approve; for critical actions require approver independence (different team/role) and sometimes **2 approvals**; all exceptions must have an owner + expiry.  
- **Developer friction reality:** ship a CLI/SDK integrated into existing workflows (PagerDuty/Jira/ChatOps) so engineers don’t invent backchannels.  
- **Explicit threat/failure mode:** collusion or a compromised approver account can rubber-stamp malicious access—mitigate via step-up auth for approvals, device posture checks, and out-of-band notifications.  
- **Explicit failure mode:** if the approval system is down during an incident, teams will seek permanent bypass—design a bounded, audited degraded mode.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing models:  
  - **A)** Standing admin roles + quarterly reviews (fast; high insider/ATO blast radius).  
  - **B)** JIT access but single-party approval/self-approval (better; still vulnerable to one compromised account).  
  - **C)** **JIT + multi-party authorization + audited break-glass** (strongest; needs careful ops + UX).  
- I pick **C for high-risk actions**, and allow a lighter-weight **B** tier for low-risk debugging to keep velocity.  
- Decisive trade-off: reduce blast radius and increase attribution at the cost of some approval latency—then engineer the system so latency is predictable and low.  
- What I’d measure: time-to-access p50/p95 (especially for on-call), approval success rate, break-glass frequency, % privileged actions covered by MPA, and post-incident audit completeness.  
- Risk acceptance: I’ll accept break-glass for true P0 incidents with strict auditing and after-the-fact review; I won’t accept permanent standing access as the “easy button.”  
- Stakeholder/influence: align SRE/on-call (speed), Compliance (dual control), Security (risk reduction), and Product (availability) on an explicit tiered policy matrix and an exception process.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You have **2,000 engineers** and 150 on-call rotations; responders must reach prod within **5 minutes p95** during incidents; overall platform SLO is **99.99%**.  
- Security: eliminate standing admin roles; require **multi-party approval** for prod mutations and data exports; reduce impact of compromised engineer laptops.  
- Reliability: the access system must work during major outages; it must be multi-region and not depend on a single IdP call-path at request time.  
- Privacy/compliance: keep 1-year auditable logs of privileged access without logging customer payloads; meet SOX/PCI-style controls for sensitive systems.  
- Developer friction: engineers use SSH, kubectl, and web consoles; you need one coherent JIT workflow and minimal retraining.  
- Migration/back-compat: legacy root SSH keys and long-lived cloud access keys exist; phase out over 6 months without breaking automation and scheduled jobs.  
- Incident/on-call twist: a P0 outage hits and the approval service is unreachable; on-call needs immediate access—how do you break-glass safely without creating a permanent bypass culture?  
- Multi-team/leadership twist: SRE leadership fears slowed MTTR, compliance demands strict dual control, security demands “no standing access,” product wants faster deployments—propose tiered controls, degraded modes, and success metrics.