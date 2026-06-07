<!-- DOMAIN_SEEDS -->
### Episode 1: **Do you promise “five nines,” or do you budget failure on purpose?**
**Focus:** Turn vague reliability goals into enforceable SLOs that drive engineering and on-call behavior.  
**Mental Model:** "A household budget: error budget is the money; outages are expenses; surprise debt equals pager hell."  
**The L4 Trap:** "Set a single uptime target (e.g., 99.99%) and page on every blip" (Fails because it maximizes toil, incentivizes hiding risk, and burns teams on non-user-impacting noise).  
**The Nitty Gritty:**
- Define SLIs as **good/total** with precise event schemas (e.g., `is_success`, `latency_ms`, `http.status_code`, `grpc.status_code`) and measure at the edge (Envoy/Nginx).
- Use **multi-window burn rates** (e.g., 14x/2h + 6x/6h) computed via PromQL `rate()` over request counters, not averages.
- Latency SLOs from **histograms**: `histogram_quantile(0.99, sum by (le)(rate(http_request_duration_seconds_bucket[5m])))`.
**The Staff Pivot:** "SLOs as a contract vs as a steering wheel: tighter SLOs improve UX but convert uncertainty into sustained on-call and slowed delivery."

---

### Episode 2: **Do you page on symptoms, or on budget burn?**
**Focus:** Build alerting that scales operationally: fewer pages, faster detection of real user harm.  
**Mental Model:** "A smoke alarm that triggers on flames, not on toast—paging is a scarce attention interrupt."  
**The L4 Trap:** "Alert on CPU>80% / error rate>1% with static thresholds" (Fails because it creates chronic false pages during benign load/cron spikes and misses slow-burn reliability debt until customers churn).  
**The Nitty Gritty:**
- Implement **burn-rate alerts** with Alertmanager routing: fast page (2h window) + slow page (24h window) tied to SLO error budget consumption.
- Use Alertmanager **inhibition rules** (e.g., inhibit `service_down` when `region_down` fires) to prevent page storms during shared failures.
- Encode **actionability** in labels/annotations: runbook URL, dashboard link, `severity=page|ticket`, `paging_team`, `slo=checkout-availability`.
**The Staff Pivot:** "Centralized alert policy improves consistency, but service-specific tuning prevents ‘one-size’ blind spots in heterogeneous systems."

---

### Episode 3: **Do you instrument everything, or sample aggressively and stay solvent?**
**Focus:** Observability design under cardinality, cost, and latency constraints (metrics + logs + traces).  
**Mental Model:** "City traffic cameras: full coverage is ideal, but bandwidth/storage forces selective high-value intersections."  
**The L4 Trap:** "Add high-cardinality labels like `user_id`, `request_id` to Prometheus metrics" (Fails because TSDB cardinality explodes, query latency spikes, and the monitoring system becomes the outage).  
**The Nitty Gritty:**
- Tracing context propagation via **W3C Trace Context** (`traceparent`, `tracestate`) and OpenTelemetry semantic conventions.
- Choose sampling: **head-based** (probabilistic) vs **tail-based** (keep slow/error traces) with OTLP collectors and queue/backpressure tuning.
- Use **exemplars** to link metrics→traces (Prometheus exemplars, OTel) instead of stuffing identifiers into metric labels.
**The Staff Pivot:** "Gold-plated telemetry improves debuggability, but the reliability of the observability pipeline itself becomes a critical dependency."

---

### Episode 4: **When prod is on fire: rollback now, or fix forward under load?**
**Focus:** Incident execution strategy that minimizes user harm while preserving learning and safety.  
**Mental Model:** "Emergency room triage: stabilize first, then diagnose; don’t run experiments on the bleeding patient."  
**The L4 Trap:** "SSH into prod and patch live until graphs look better" (Fails because it destroys provenance, makes recovery non-repeatable, and increases MTTR when the same class of failure recurs).  
**The Nitty Gritty:**
- Prefer controlled reversibility: Kubernetes `rollout undo`, GitOps revert, or feature-flag kill switches (with audited flag changes).
- Use incident roles (IC/Comms/Scribe) and a **shared timeline** tied to deploy SHAs, config versions, and dashboards.
- Capture decision points in the postmortem with **counterfactuals** (what signals were missing?) and concrete action items (SLO/alerts/runbooks).
**The Staff Pivot:** "Rollback reduces immediate risk but can reintroduce known vulnerabilities; fix-forward can be safer if blast radius is bounded by progressive delivery."

---

### Episode 5: **Do you keep accepting traffic, or shed load intentionally to save the system?**
**Focus:** Design overload behavior so the system fails predictably and recovers quickly.  
**Mental Model:** "A nightclub bouncer: letting everyone in causes a crush; controlled entry keeps the venue open."  
**The L4 Trap:** "Queue everything and ‘let it drain’" (Fails because queues become unbounded, tail latency explodes, retries amplify load, and recovery time stretches from minutes to hours).  
**The Nitty Gritty:**
- Apply admission control at the edge: return **HTTP 429/503** with `Retry-After` and enforce per-route limits in Envoy/Nginx.
- Implement load shedding signals: queue depth, concurrency, and latency; use algorithms like **CoDel**-style early drops for queuing delay.
- For gRPC, use status **`RESOURCE_EXHAUSTED`** / **`UNAVAILABLE`** intentionally and ensure clients respect backoff + deadlines.
**The Staff Pivot:** "Shedding protects the platform but creates partial outages; prioritize critical paths (tiered degradation) to preserve revenue and trust."

---

### Episode 6: **Rate-limit at the edge, or deep in the service graph?**
**Focus:** Prevent abuse and cascading overload with rate limiting that matches system topology and fairness needs.  
**Mental Model:** "Toll booths: place them at highway entrances (edge) or at city intersections (service)—each changes traffic patterns."  
**The L4 Trap:** "Add a single global QPS limit in one service" (Fails because it becomes a hotspot/SPoF and pushes fairness and overload problems downstream into unpredictable places).  
**The Nitty Gritty:**
- Choose an algorithm: **token bucket** (bursty) vs **leaky bucket** (smooth) and define keys (API key, user, IP, tenant).
- Envoy options: **local rate limiting filter** vs global RLS (gRPC **Rate Limit Service**) with failure-mode configs (`fail_open` vs `fail_close`).
- Distributed counters with Redis: atomic updates via **Lua scripts**; consider clock skew and per-region isolation.
**The Staff Pivot:** "Edge rate limiting is simpler and cheaper, but service-level limits enable fairness and blast-radius control for multi-tenant internals."

---

### Episode 7: **Do you retry to be resilient, or do you stop retrying to survive?**
**Focus:** Timeouts, retries, hedging, and circuit breakers without turning incidents into retry storms.  
**Mental Model:** "Calling a busy restaurant: calling back helps—unless everyone redials at once and blocks the phone lines."  
**The L4 Trap:** "Add automatic retries everywhere with exponential backoff" (Fails because it multiplies load during partial failures, turns 1 failing dependency into many failing services, and destroys tail latency).  
**The Nitty Gritty:**
- Enforce deadlines: gRPC **`deadline`** propagation; HTTP client timeouts; align server-side timeouts slightly above client timeouts.
- Control retries with a **retry budget** (e.g., retries ≤ 10% of successful traffic) and jittered backoff; require idempotency keys (`Idempotency-Key`).
- Circuit breaking via Envoy: **outlier detection** (ejection on consecutive 5xx), per-host max connections, and request hedging only for safe/idempotent calls.
**The Staff Pivot:** "More resilience features improve steady-state availability but add complex failure modes; simplicity may win if you can reduce dependency fanout."

---

### Episode 8: **Do you buy headroom, or autoscale aggressively and trust the control loop?**
**Focus:** Capacity planning and autoscaling that preserves SLOs under volatile traffic and noisy neighbors.  
**Mental Model:** "An elevator system: extra elevators (headroom) reduce wait time; smart scheduling (autoscaling) saves cost but can lag."  
**The L4 Trap:** "Autoscale only on CPU utilization" (Fails because CPU is a lagging proxy for user pain; scaling reacts too late and causes SLO misses during sudden fanout spikes).  
**The Nitty Gritty:**
- Kubernetes: HPA with custom metrics (Prometheus adapter), configure `behavior.scaleUp.stabilizationWindowSeconds` and `policies` to avoid oscillation.
- Right-size with VPA/requests-limits, use **cgroup v2** awareness; avoid CPU throttling (`cpu.cfs_quota_us`) surprises.
- Cluster-level: **cluster-autoscaler** + bin packing constraints (affinity/taints/PDBs) and explicit headroom targets per tier.
**The Staff Pivot:** "Provisioning headroom is predictable but expensive; autoscaling is cost-efficient but a distributed control system that must be engineered like one."

---

### Episode 9: **Do you ship faster, or make every change prove it won’t break the SLO?**
**Focus:** Progressive delivery and change safety mechanisms that prevent regressions from becoming incidents.  
**Mental Model:** "A vaccine trial: phased rollout with monitoring beats injecting the whole population at once."  
**The L4 Trap:** "Big-bang deploy + ‘we’ll watch dashboards’" (Fails because blast radius is maximal; rollback may be slow or unsafe due to schema/config drift).  
**The Nitty Gritty:**
- Progressive delivery: canary/blue-green with Argo Rollouts/Spinnaker; bake time and step weights; automated analysis using Prometheus queries.
- SLO-aware gates: block promotion on burn-rate spikes, error-rate deltas, and p95/p99 latency regressions (per-route, not global).
- Safe migrations: **expand/contract** patterns; avoid non-backward-compatible protobuf/JSON changes; dual-write with explicit cutover flags.
**The Staff Pivot:** "Automation reduces human error but can ‘auto-fail’ on noisy signals; invest in robust metrics and guardrails before strict gating."

---

### Episode 10: **Active-active across regions, or active-passive with a clean failover story?**
**Focus:** Multi-region reliability architecture with clear consistency, failover, and operational semantics.  
**Mental Model:** "Two pilots: both can fly (active-active) but must coordinate; otherwise you fight the controls (split-brain)."  
**The L4 Trap:** "Stretch a single primary database across regions and hope latency is fine" (Fails because cross-region RTT wrecks tail latency, increases contention, and makes incident recovery ambiguous and risky).  
**The Nitty Gritty:**
- Consensus basics: **Raft** leader election, quorum writes, lease-based reads; understand failure modes (network partitions, leader flaps).
- Traffic steering: global load balancing (Anycast/BGP or DNS with low TTL) and health-based routing; ensure clients respect TTL and retry safely.
- Split-brain prevention: fencing tokens / lease epochs; write barriers; explicit failover runbooks and automation with safety checks.
**The Staff Pivot:** "Active-active improves availability but increases complexity and data anomalies; active-passive simplifies correctness but accepts regional brownouts during failover."

---

### Episode 11: **Backups you ‘have,’ or restores you’ve proven under pressure?**
**Focus:** Disaster recovery engineering as a tested capability, not a compliance checkbox.  
**Mental Model:** "A parachute: ownership isn’t safety—packing and test jumps are."  
**The L4 Trap:** "Schedule nightly backups and call it DR" (Fails because restores are slow/broken, RPO/RTO are fantasy, and a real incident becomes an existential business event).  
**The Nitty Gritty:**
- Backup types: snapshot + **WAL** shipping; **PITR** (point-in-time recovery); verify checksums and immutability (Object Lock / WORM).
- Restore drills: measure RTO/RPO; rehearse region evacuation; keep runbooks versioned and executable (scripts, Terraform, Kubernetes manifests).
- Fault injection game days: Chaos Mesh/Litmus; validate degraded-mode operation and dependency timeouts during simulated regional failures.
**The Staff Pivot:** "Frequent DR drills consume engineering time but prevent catastrophic surprises; choose a cadence tied to business risk and change velocity."

---

### Episode 12: **Frontier Digest — eBPF everywhere, or stick to app instrumentation you can reason about?**
**Focus:** Modern production debugging with eBPF-based telemetry and continuous profiling—powerful, but with sharp edges.  
**Mental Model:** "X-ray imaging: reveals hidden fractures without surgery, but misreads and overuse can harm the patient."  
**The L4 Trap:** "Deploy eBPF collectors cluster-wide with default settings" (Fails because kernel-level overhead and data volume can cause node instability, plus security/compliance risk from overly broad capture).  
**The Nitty Gritty:**
- eBPF mechanics: CO-RE (Compile Once–Run Everywhere), BTF, kprobes/uprobes, ring buffer output; understand verifier limits and kernel compatibility.
- Continuous profiling pipelines: pprof format, Parca/Pyroscope agents, on-CPU/off-CPU profiles; correlate with traces via OTel exemplars or shared trace IDs.
- Guardrails: per-node CPU/memory budgets, sampling rates, namespace/UID filtering, and explicit allowlists for probe attachment targets.
**The Staff Pivot:** "eBPF accelerates incident resolution and performance wins, but increases platform surface area; limit scope and prove ROI before broad rollout."

---
