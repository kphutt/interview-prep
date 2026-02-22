<!-- DOMAIN_LENS -->
backend systems (APIs, data stores, caching, distributed coordination)

<!-- NITTY_GRITTY_LAYOUT -->
    1) **System Architecture / Data Flow**
    2) **Data Storage / Caching**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
  - Include concrete system design details (APIs, schemas, data flow, protocols).
  - Include concrete data handling (storage engines, cache strategies, consistency models).
  - Include explicit threats and concrete failure modes (what breaks, how it breaks).
  - Include operational reality (logs/metrics/SLOs, paging triggers, canary/rollback, blast radius).
  - Include at least one policy/control detail (rate limiting, access control, auditability).

<!-- DISTILL_REQUIREMENTS -->
  - 2 concrete system design details (APIs, schemas, protocols, data flow)
  - 2 data storage or caching details (engines, strategies, consistency, TTLs)
  - 2 operational details (logs, metrics, SLOs, alerting, rollout/canary, failure modes)
  - 1 policy/control detail (rate limiting, access control, audit, compliance)
  - 1 explicit threat or failure mode

<!-- STAKEHOLDERS -->
Backend, Product, SRE, Data
