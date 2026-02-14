**Episode 9 — Detection Engineering: Detections‑as‑Code That Don’t Page You to Death**

2) **The Hook (The core problem/tension).**
- You can’t incident-respond to what you can’t *reliably* detect—but “more alerts” usually means “more ignored alerts.”  
- Detection is a **data product** with SLOs (freshness, completeness, precision), not a pile of SIEM queries.  
- Staff-level challenge: ship high-signal detections fast **without** turning your log pipeline into a fragile, expensive dependency.

3) **The "Mental Model" (A simple analogy).**  
Good detections are like airport security: you’re not trying to recognize every bad actor’s face—you’re looking for *behavioral anomalies with context* (wrong place, wrong time, wrong tool). The goal is to stop the attacker’s “kill chain moves,” not to alert on every suspicious-looking passenger.

4) **The "L4 Trap" (Common junior mistake + why it fails at scale).**
- “Alert on failed logins / 403s / exceptions.” Security-only thinking creates noise, not coverage; SOC drowns and misses real incidents.  
- “Write detections directly in the SIEM UI.” It doesn’t version, test, review, or roll back like software—so it fails under churn.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Telemetry contract:** normalize events to a stable schema (ECS/OpenTelemetry-style) with fields like `event.category`, `user.id`, `source.ip`, `http.request.method`, `dns.question.name`, `process.parent.name`; detections are only as good as schema consistency.  
- **Protocol detail (secure transport):** ship logs/metrics over **TLS/mTLS** (e.g., OTLP over gRPC with TLS 1.3) so collectors can authenticate agents and prevent trivial spoofing.  
- **Crypto detail (audit log integrity):** when available, validate cloud audit log integrity (e.g., CloudTrail log file integrity uses **SHA-256 hash chaining + digital signatures**) to detect tampering or gaps.  
- **Detections as code:** express rules in a structured format (e.g., Sigma-style YAML with `logsource`, `detection`, `condition`, `falsepositives`, `level`) and compile to your SIEM query language; require code review.  
- **Correlation at scale:** implement windowed aggregations (e.g., `count_distinct(device_id) > N in 10m`, “impossible travel,” “rare parent→child process”) using a streaming engine with a state store keyed by `(principal, host, api_key)`.  
- **Data-plane/caching #1 (enrichment cache):** cache asset/identity enrichment (host→service owner/tier, user→group, IP→ASN) with TTL (minutes) to avoid turning detections into constant inventory/LDAP lookups.  
- **Data-plane/caching #2 (dedup/suppression cache):** prevent paging storms by grouping and deduping alerts keyed by `(rule_id, entity, time_bucket)` with TTL; emit one page + a rollup list.  
- **Rule performance:** avoid hot-path joins on massive tables; precompute cheap features (e.g., DNS entropy score, eTLD+1 extraction) and store as event fields for O(1) rule evaluation.  
- **Operational detail #1 (rollouts):** ship detections with feature flags: *dry-run* (count would-have-fired), canary, then paging; bake rollback triggers (precision drop, page rate spike).  
- **Operational detail #2 (triage readiness):** every paging rule needs a runbook: “why this is bad,” “how to validate in <10 minutes,” “containment steps,” and “known false positives.”  
- **Policy/control:** define a paging bar: only rules meeting a precision/SNR target (and with an owner) can page; everything else tickets or dashboards.  
- **Explicit threat/failure mode:** attackers disable/evade telemetry (EDR killed, log shipper blocked) *or* your pipeline drops events under backpressure—without “ingestion gap” alerts, you get silent failure.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing approaches:  
  - **A)** “SIEM queries in the UI” (fast initially; untestable, unreviewable, brittle).  
  - **B)** **Detections-as-code + CI + staged rollout** (higher upfront cost; scalable quality).  
  - **C)** “ML anomaly detection for everything” (can help, but hard to explain/tune; often high false positives without strong baselines).  
- I choose **B** as the backbone, with **targeted ML/heuristics** as *enrichment* (risk scoring), not as the only detector.  
- Decisive trade-off: prioritize **precision and operational safety** over maximal coverage early; you can add breadth once the pipeline is trustworthy.  
- What I’d measure: **MTTD**, alert **precision** (true-positive rate), page volume per on-call, detection latency (event→alert), ingestion gap rate, and “alert→incident” conversion.  
- Risk acceptance: I’ll accept that some low-signal TTPs remain uncovered for a quarter if it avoids alert fatigue and broken on-call.  
- Stakeholder/influence: align SOC (triage), SRE (pipeline SLOs), app teams (instrumentation), and Privacy (PII minimization) around a shared schema and a “paging bar” governance process.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You ingest **3 TB/day** of logs across 60 services; leadership wants “detect ATO + data exfil within **5 minutes**.”  
- Latency/SLO: detections must fire within **2 minutes p95** of the event; the detection pipeline must be **99.9%** available.  
- Reliability: the SIEM/search backend has weekly maintenance windows; you need buffering and a plan for “late alerts” without missing incidents.  
- Security: attacker may attempt log tampering (kill agent, block egress); you must detect **telemetry gaps** as first-class signals.  
- Privacy/compliance: you cannot store full URLs/query strings or raw payloads; retention is 180 days with strict access auditing.  
- Developer friction: 20 teams emit inconsistent logs; you need a **golden schema + SDK** and automated conformance checks, not bespoke per-team rules.  
- Migration/back-compat: legacy services emit unstructured text logs; you must onboard them without a flag day while still getting useful detections.  
- Incident/on-call twist: Kafka/stream backlog spikes and event lag grows to 30 minutes; window-based detections stop working—what do you shed, and what do you page on?  
- Multi-team/leadership twist: CISO demands “more detections,” SOC demands “more context,” SRE demands “fewer pages,” Privacy demands “less data”—propose a prioritization rubric and weekly metrics report.

---

1) **The Title (Catchy and technical).**