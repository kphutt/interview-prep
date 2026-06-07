<!-- DOMAIN_SEEDS -->
### Episode 1: The “Golden Path” vs “Anything Goes”: Do you mandate the platform?
**Focus:** Drive adoption of an internal platform without creating a productivity tax or shadow infrastructure.
**Mental Model:** "Airports: one secure, well-signed terminal beats 200 private runways—until you need a helicopter pad."
**The L4 Trap:** "Ship a platform as a menu of optional tools and hope teams adopt." (Fails because low adoption fragments standards, multiplies on-call surfaces, and blows up integration costs.)
**The Nitty Gritty:**
- Kubernetes policy-as-product: Gatekeeper/OPA `ConstraintTemplate`, Kyverno, and admission control to enforce `requests/limits`, `runAsNonRoot`, and image provenance.
- “Golden path” scaffolding: Backstage templates + CI starters (GitHub Actions) with pinned `actions/*@<sha>` and reusable workflows.
- Standard service interface: OpenAPI 3.1 + `x-slo` metadata, or protobuf service definitions compiled in CI to generate client SDKs.
**The Staff Pivot:** "Mandate the golden path for common cases, but create an explicit exception process with SLO and security reviews."

---

### Episode 2: Chargeback vs Free Buffet: Do you price internal platform usage?
**Focus:** Align platform consumption with business value using governance that doesn’t stall delivery.
**Mental Model:** "Office snacks: free is fun until the bill triples and nobody knows who’s eating what."
**The L4 Trap:** "Keep platform ‘free’ to maximize happiness." (Fails because unmanaged consumption causes capacity surprises, budget overruns, and funding fights that stall roadmap.)
**The Nitty Gritty:**
- Showback plumbing: AWS Cost and Usage Report (CUR) / GCP Billing Export + labels/tags like `team`, `service`, `env`, `cost_center`.
- K8s allocation: enforce `ResourceQuota` and `LimitRange`; measure actual usage via Prometheus + kube-state-metrics; allocate shared costs proportionally.
- Guardrails: budgets + alerts (AWS Budgets) tied to anomaly detection; deny-list expensive instance types via policy.
**The Staff Pivot:** "Start with showback + quotas, then introduce chargeback only for scarce resources (GPU, egress, premium tiers)."

---

### Episode 3: REST + OpenAPI vs gRPC + Protobuf: Which contract wins for internal APIs?
**Focus:** Choose an API style that optimizes developer velocity, compatibility, and performance at scale.
**Mental Model:** "Blueprints vs prefabs: blueprints (OpenAPI) are flexible; prefabs (protobuf) snap together reliably."
**The L4 Trap:** "Pick whatever the first team prefers." (Fails because inconsistent contracts increase client bugs, slow migrations, and create long-lived compatibility debt.)
**The Nitty Gritty:**
- REST contract discipline: OpenAPI 3.1, JSON Schema, `nullable` semantics, and explicit pagination fields (`next_page_token` vs `offset/limit`).
- gRPC details: HTTP/2, protobuf field numbering rules, `oneof` evolution, and deadlines (`grpc-timeout`) to prevent resource pinning.
- Versioning mechanics: semantic versioning + deprecation headers (`Sunset`, `Deprecation`) vs proto package versioning (`package foo.v1;`).
**The Staff Pivot:** "Use REST/OpenAPI for broad DX and externalization; use gRPC for high-QPS internal paths with strict SLOs."

---

### Episode 4: Synchronous Calls vs Event Streams: Do you integrate with webhooks or a queue?
**Focus:** Decide between request/response coupling and asynchronous event-driven reliability.
**Mental Model:** "Phone call vs voicemail drop: calls resolve now; voicemail scales and survives outages."
**The L4 Trap:** "Add a webhook and call it ‘event-driven’." (Fails because retries, ordering, and dedupe aren’t specified—leading to double-charges, data drift, and painful incident cleanup.)
**The Nitty Gritty:**
- Queue semantics: Kafka topics with partitions (ordering per key), consumer groups, and `min.insync.replicas` for durability trade-offs.
- Idempotency: `Idempotency-Key` headers, dedupe tables keyed by `(key, operation)` with TTL, and exactly-once illusions avoided.
- Delivery patterns: transactional outbox + CDC (Debezium) vs “dual write”; schema evolution via Confluent Schema Registry (Avro/Protobuf).
**The Staff Pivot:** "Prefer async for cross-domain integration; keep sync for user-facing reads and tightly bounded workflows."

---

### Episode 5: SLOs First vs Features First: What do you actually promise developers?
**Focus:** Define service reliability targets that guide prioritization and prevent reliability theater.
**Mental Model:** "A speed limit: it’s enforceable only if everyone agrees what road and what conditions."
**The L4 Trap:** "Publish a 99.9% uptime goal without SLIs or error budgets." (Fails because teams argue during incidents, reliability work gets deprioritized, and enterprise customers churn.)
**The Nitty Gritty:**
- SLI design: RED metrics (Rate, Errors, Duration) for APIs; define “good” as `2xx` + `latency < 300ms` at the edge.
- Error budgets: `budget = 1 - SLO`; burn rate alerts using multi-window (e.g., 5m/1h, 30m/6h) burn calculations.
- Tooling: Prometheus recording rules, Alertmanager routing, and service dashboards that match the SLI query exactly.
**The Staff Pivot:** "Ship fewer features when the budget is burning; treat reliability as a product constraint, not a side quest."

---

### Episode 6: Retries Everywhere vs Retries Nowhere: How do you prevent retry storms?
**Focus:** Build resilient client/server behaviors that avoid cascading failures under partial outages.
**Mental Model:** "Crowd control at a stadium: letting everyone push back in makes the crush worse."
**The L4 Trap:** "Add naive retries with fixed intervals on every 500/timeout." (Fails because synchronized retries amplify load, extend outages, and inflate cloud spend dramatically.)
**The Nitty Gritty:**
- Backoff: exponential backoff with decorrelated jitter (AWS “Full Jitter”), plus max retry window and per-request deadlines.
- Circuit breaking: Envoy outlier detection, `max_connections`, `max_pending_requests`, and per-route timeouts; client-side breakers (resilience4j).
- Admission control: token bucket / leaky bucket rate limiting; prioritize by `x-priority` headers; shed load with 429 + `Retry-After`.
**The Staff Pivot:** "Optimize for fast failure and graceful degradation, not ‘eventual success’ at all costs."

---

### Episode 7: Logs Everywhere vs Metrics That Matter: What’s your observability contract?
**Focus:** Create an observability baseline that enables debugging without bankrupting storage and ingest.
**Mental Model:** "Security cameras: more cameras help until nobody can review the footage."
**The L4 Trap:** "Turn on debug logs in prod and rely on grep." (Fails because costs explode, signal-to-noise drops, and incident MTTR rises due to missing structure.)
**The Nitty Gritty:**
- Tracing standardization: OpenTelemetry SDKs, W3C `traceparent` propagation, and consistent span attributes (`http.method`, `rpc.system`, `db.system`).
- Sampling strategy: head-based sampling for cost caps vs tail-based sampling in the OpenTelemetry Collector for “keep errors” policies.
- Structured logging: JSON logs with stable keys (`request_id`, `tenant_id`, `user_id_hash`), plus PII redaction rules at ingestion.
**The Staff Pivot:** "Define an observability contract (required metrics/traces/log fields) and enforce it in platform templates."

---

### Episode 8: Feature Flags vs Configuration Releases: How do you ship safely without freezing delivery?
**Focus:** Choose rollout mechanisms that reduce blast radius while avoiding flag debt and inconsistent behavior.
**Mental Model:** "Circuit breakers in a house: you want controlled isolation, not a maze of hidden switches."
**The L4 Trap:** "Wrap every change in a flag and never remove them." (Fails because flag debt creates combinatorial test matrices, unpredictable behavior, and slows incident triage.)
**The Nitty Gritty:**
- Progressive delivery: Argo Rollouts / Flagger canaries with metric checks (Prometheus queries) and automated rollback thresholds.
- Flag standards: OpenFeature API, rule targeting by `tenant_id`, and mandatory expiry metadata (`owner`, `expires_at`) enforced in CI.
- Config safety: separate “dynamic config” store (e.g., etcd/Consul) from deploys; require schema validation and staged rollout by region.
**The Staff Pivot:** "Use flags for risk containment, not product design; prefer canary + fast rollback for most changes."

---

### Episode 9: Multi-Tenant Shared Cluster vs Cell-Based Architecture: Where do you draw isolation boundaries?
**Focus:** Scale a platform while balancing efficiency, blast radius, compliance, and operability.
**Mental Model:** "Apartment building vs separate houses: shared utilities are efficient until one fire alarms everyone."
**The L4 Trap:** "Put every tenant in the same cluster/DB for utilization." (Fails because noisy neighbors cause SLO violations, incidents become cross-customer, and compliance boundaries break.)
**The Nitty Gritty:**
- K8s isolation: namespaces + NetworkPolicy, Pod Security Standards, `ResourceQuota`, and node pools with taints/tolerations for premium tenants.
- Data partitioning: shard keys (`tenant_id`) with consistent hashing; per-tenant encryption keys; connection pool limits per tenant.
- Cell architecture: route by cell (`X-Cell-Id`), replicate control plane config, and isolate failure domains per region/cell.
**The Staff Pivot:** "Start shared with strong quotas; move to cells when SLO/compliance demand predictable blast radius."

---

### Episode 10: OAuth/OIDC vs mTLS Identity: How do services trust each other?
**Focus:** Pick an identity and authN/authZ model that scales across microservices and teams.
**Mental Model:** "Badges vs handshakes: badges (tokens) are portable; handshakes (mTLS) prove who’s at the door."
**The L4 Trap:** "Hardcode shared API keys in services." (Fails because rotation is painful, breaches have huge blast radius, and audits/compliance fail.)
**The Nitty Gritty:**
- OAuth 2.1 + OIDC: JWT access tokens, JWKS key rotation, `aud`/`iss` validation, and short TTL with refresh flows for humans vs services.
- Service identity: SPIFFE IDs (`spiffe://domain/ns/service/sa/default`) and SPIRE issuing SVIDs; mTLS enforcement via Envoy.
- AuthZ: centralized policy (OPA/Styra) with ABAC claims (e.g., `tenant_id`, `role`) and consistent denial logging.
**The Staff Pivot:** "Use mTLS for service identity and encryption; layer OAuth/OIDC for end-user delegation and fine-grained authorization."

---

### Episode 11: Encrypt Everything at Rest vs Field-Level Controls: What’s the right privacy posture?
**Focus:** Meet security and residency requirements without making the system unoperable or unbearably slow.
**Mental Model:** "Locking the whole warehouse vs locking individual cages: both work, but change how you operate."
**The L4 Trap:** "Rely only on disk encryption and call it done." (Fails because sensitive fields leak via logs/exports, residency rules are violated, and breach impact is catastrophic.)
**The Nitty Gritty:**
- Envelope encryption: per-record DEK encrypted by KMS KEK (AWS KMS / GCP KMS), rotated with rewrap jobs; AES-256-GCM.
- Data residency: region-scoped keyrings, routing controls to prevent cross-region writes, and explicit replication allowlists.
- Tokenization/FLE: deterministic encryption for joinable fields, format-preserving encryption (FPE) where needed, and strict key access via IAM conditions.
**The Staff Pivot:** "Combine layered controls: platform-wide encryption + field-level protection for high-risk data and regulated tenants."

---

### Episode 12 (Frontier Digest): LLM Copilot for On-Call vs “No AI in Prod”: Where do you place the trust boundary?
**Focus:** Apply frontier AI to incident response without creating new security, reliability, or accountability failures.
**Mental Model:** "A junior assistant with a fast keyboard: helpful, but you must control what they can touch."
**The L4 Trap:** "Let an LLM read everything and suggest fixes in the heat of an incident." (Fails because prompt injection/data exfiltration risks rise, wrong actions extend outages, and postmortems lose clear accountability.)
**The Nitty Gritty:**
- Retrieval design: RAG over runbooks/postmortems with doc provenance, chunking, and strict allowlisted sources (no freeform internet).
- Guardrails: PII redaction on logs before indexing, tool-based actions via function calling with scoped permissions, and immutable audit logs.
- Evaluation: offline incident replay sets, hallucination checks, and “human-in-the-loop” gating for any write action (feature flag flips, rollbacks).
**The Staff Pivot:** "Use AI for summarization and search first; graduate to controlled actions only after measurable safety and accuracy."

---
