<!-- DOMAIN_LENS -->
Domain depth in platform/infrastructure TPM means grounding product decisions in control-plane/data-plane mechanics, API/ABI compatibility, multi-tenant isolation, capacity/cost models, and operability (SLOs/rollouts) so tradeoffs are explicit, measurable, and safe at scale.

<!-- NITTY_GRITTY_LAYOUT -->
1) **Platform Architecture (Control Plane vs Data Plane / Multi-Tenancy)**
    2) **Interfaces & Contracts (APIs/SDKs, Backward Compatibility, Versioning)**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
- Include concrete platform/infrastructure technical details (e.g., control-plane reconciliation loops, rate limiting/backpressure, idempotency keys, schema/API versioning, quotas, caching layers, leader election).
  - Include concrete data/state handling (e.g., source-of-truth selection, eventual consistency windows, state machine transitions, retries with dedupe, migrations/dual-write, tenancy-scoped metadata, partitioning/sharding keys).
  - Include explicit threats and concrete failure modes (e.g., noisy-neighbor/resource starvation, thundering herd, misconfigured IAM leading to cross-tenant access, cascading retries, partial rollout incompatibilities, split-brain control plane).
  - Include operational reality (e.g., SLIs/SLOs and error budgets, RED/USE metrics, structured logs with correlation IDs, paging thresholds, canary/gradual rollout, rollback strategy, blast radius containment, game days).
  - Include at least one policy/control detail (e.g., least-privilege IAM, break-glass with approvals, audit logs/immutable trails, data retention/TTL, change-management gates for prod).

<!-- DISTILL_REQUIREMENTS -->
- 2 concrete platform technical details (e.g., idempotent create/update semantics; API versioning/backward compatibility strategy)
  - 2 data/state details (e.g., source-of-truth datastore and consistency model; migration approach such as dual-write + backfill + cutover)
  - 2 operational details (e.g., SLO with a specific SLI and paging threshold; rollout plan with canary and explicit rollback trigger)
  - 1 operational failure-mode detail (e.g., how retries/backoff prevent cascading failures, or how quotas limit blast radius)
  - 1 policy/control detail (e.g., least-privilege IAM with audit logging and approval workflow)
  - 1 explicit threat or failure mode (e.g., cross-tenant data leakage via mis-scoped permissions or shared cache keying bug)

<!-- STAKEHOLDERS -->
Platform Engineering, SRE/Production Engineering, Security/IAM, Compliance/Privacy, Finance/Capacity Planning -->
