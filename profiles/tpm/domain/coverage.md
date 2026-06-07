<!-- COVERAGE_FRAMEWORK -->
Infra TPM Competency Framework (June 2026) Coverage Map (table)

| Episode | Framework Domains (Tags) | Justification (<= 18 words) |
|---|---|---|
| 1. Golden Path vs Anything Goes | Product Strategy & Adoption; Delivery & Change Management | Adoption strategy plus enforcement mechanisms prevent platform sprawl and on-call fragmentation. |
| 2. Chargeback vs Free Buffet | Platform Economics & Governance; Product Strategy & Adoption | Aligns consumption with cost drivers; reduces funding conflicts and improves roadmap credibility. |
| 3. REST/OpenAPI vs gRPC/Protobuf | API/DX & Contract Design | Contract choice determines compatibility, latency, tooling, and long-term migration cost. |
| 4. Sync vs Event Streams | API/DX & Contract Design; Reliability & Performance | Integration style controls coupling, failure modes, ordering, and dedupe guarantees. |
| 5. SLOs First vs Features First | Reliability & Performance; Platform Economics & Governance | Error budgets create objective trade-offs and make reliability investment economically legible. |
| 6. Retries Everywhere vs Nowhere | Reliability & Performance | Prevents cascading failures and spend spikes through backoff, breakers, and load shedding. |
| 7. Logs Everywhere vs Metrics That Matter | Observability & Experimentation | Defines telemetry contracts, sampling, and correlation needed for low-MTTR operations. |
| 8. Feature Flags vs Config Releases | Delivery & Change Management; Reliability & Performance | Rollout controls reduce blast radius while avoiding flag debt and inconsistent behavior. |
| 9. Shared Multi-Tenant vs Cells | Platform Economics & Governance; Reliability & Performance | Isolation boundaries balance utilization against blast radius, SLO predictability, and compliance. |
| 10. OAuth/OIDC vs mTLS Identity | Security/Privacy/Compliance; API/DX & Contract Design | Establishes scalable identity, authZ policy, and secure service-to-service communication. |
| 11. Encrypt-at-Rest vs Field-Level | Security/Privacy/Compliance; Platform Economics & Governance | Meets residency/privacy with manageable key rotation, access controls, and auditability. |
| 12. Frontier Digest: LLM Copilot vs No AI | Observability & Experimentation; Security/Privacy/Compliance | Applies AI safely via RAG guardrails, audits, and controlled action boundaries. |
