<!-- DOMAIN_LENS -->
Domain depth in Staff-level SRE means reasoning from first principles about reliability mechanisms (SLOs/error budgets, load-shedding, dependency isolation, capacity/queueing, safe rollout/rollback) and connecting design decisions to measurable production outcomes under real failure modes.

<!-- NITTY_GRITTY_LAYOUT -->
1) **SLO/SLI Design & Error Budget Policy (User Journeys, Multi-window Alerts, Burn-rate)**
    2) **Resilience Architecture (Dependency Isolation, Backpressure, Rate Limits, Failover/DR)**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
- Include concrete reliability mechanisms (e.g., multi-window multi-burn-rate alerting, circuit breakers/bulkheads, load shedding/brownout, retries with jitter and bounded backoff, idempotency keys).
  - Include concrete data/state handling details (e.g., config rollout via progressive delivery, leader election/quorum implications, caching consistency + TTL/negative caching, queue semantics/at-least-once vs exactly-once, schema/versioning and backwards compatibility).
  - Include explicit threats and concrete failure modes (e.g., thundering herd after cache flush, retry storms causing cascading failure, partial zonal outage + split-brain, noisy-neighbor saturation, clock skew breaking leases).
  - Include operational reality (e.g., SLIs with instrumentation points, dashboards and golden signals, paging triggers with burn-rate thresholds, canary + automated rollback, capacity models, blast-radius containment via cell-based architecture).
  - Include at least one policy/control detail (e.g., least-privilege IAM for automation, change approvals for high-risk config, audit logging for oncall actions, retention for logs/metrics and incident artifacts).

<!-- DISTILL_REQUIREMENTS -->
- 2 concrete domain-specific technical details
  - 2 domain-specific data/state details
  - 2 operational details (logs, metrics, SLOs, alerting, rollout/canary, failure modes)
  - 1 policy/control detail (least privilege, approvals, audit, compliance)
  - 1 explicit threat or failure mode

<!-- STAKEHOLDERS -->
Product Engineering, Infrastructure/Platform, Security, Compliance/Privacy, Customer Support
