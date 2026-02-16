<!-- DOMAIN_LENS -->
identity/infrastructure mechanisms (protocols, architecture, threats)

<!-- NITTY_GRITTY_LAYOUT -->
    1) **Protocol / Wire Details**
    2) **Data Plane / State / Caching**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
  - Include concrete protocol/crypto details (headers/claims/handshakes/certs/curves).
  - Include concrete data-plane/state handling (cache keys, invalidation, TTLs, replay windows).
  - Include explicit threats and concrete failure modes (what breaks, how it breaks).
  - Include operational reality (logs/metrics/SLOs, paging triggers, canary/rollback, blast radius).
  - Include at least one policy/control detail (least privilege, approvals, auditability, retention).

<!-- DISTILL_REQUIREMENTS -->
  - 2 concrete protocol/crypto details (headers, claims, handshakes, certs, algorithms)
  - 2 data-plane or caching details (cache keys, invalidation, TTLs, state management)
  - 2 operational details (logs, metrics, SLOs, alerting, rollout/canary, failure modes)
  - 1 policy/control detail (least privilege, approvals, audit, compliance)
  - 1 explicit threat or failure mode

<!-- STAKEHOLDERS -->
Security, Product, SRE, Legal/Compliance
