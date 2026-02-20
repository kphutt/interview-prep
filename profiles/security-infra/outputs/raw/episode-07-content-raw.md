## Title
**Episode 7 — The Cloud Metadata Attack: SSRF → Instance Credentials (Defense-in-Depth Guardrails)**

## Hook
- SSRF turns a “feature” (server-side URL fetch) into attacker-controlled egress; at scale, any missed edge case becomes a reliable cloud credential exfil path.
- Metadata endpoints are intentionally high-trust and low-latency; that convenience becomes a privilege escalation when your app can be tricked into reaching link-local services.
- Fixing every SSRF sink in every codebase is slow and inconsistent; platform guardrails must reduce risk **before** perfect app hygiene exists.
- Guardrails can break production: blocking metadata egress can instantly 500 workloads that implicitly depended on instance credentials—on-call gets paged, not the attacker.
- Cloud-hardening knobs (e.g., IMDSv2) are necessary but not sufficient; SSRF can still reach metadata if requests/headers are attacker-influenced.
- Low added latency budgets (<10ms p99) constrain where you can enforce controls (library vs sidecar vs centralized egress proxy) and how you do DNS/redirect checks.
- Cross-cloud reality (AWS + GCP) means no single provider mechanism solves it; you need portable controls and consistent policy enforcement.
- Compliance/privacy constraints (no full URL logging) collide with detection and audit requirements; you must log **enough** to investigate without leaking secrets.
- Rollout safety is a first-class requirement: you need monitor-only phases, allowlist exceptions with ownership, and fast rollback to avoid “security-induced outage” narratives.

## Mental Model
SSRF is convincing a receptionist to fetch documents on your behalf; the metadata endpoint is the locked server room containing master keys. Even if the receptionist is tricked, the building should prevent them from entering the server room. The core engineering question is where you put the physical barriers (network), the receptionist’s training (safe fetcher), and the alarms (detection), without slowing down normal business or causing outages.

- Receptionist → your shared HTTP client / URL fetch service used by many teams; “helpful by default” behavior is the hazard.
- Locked server room → link-local metadata (e.g., `169.254.169.254`) and internal admin services; must be unreachable from general-purpose egress paths.
- Building access controls → egress policies (iptables/eBPF/Envoy/network policy) and cloud settings (IMDSv2, hop-limit) that constrain reachability independent of app correctness.
- Alarms and security desk → metrics/alerts on blocked metadata attempts + unusual credential API usage; these drive incident response and exception governance.
- Failure mode mapping (adversary behavior) → attacker uses redirects/DNS rebinding/header injection to “walk” the receptionist past naive checks and into the server room.

## Common Trap
- Red flag: “Blacklist `169.254.169.254` with a regex.” Fails at scale because redirects, alternate encodings, IPv6, and proxy paths bypass string checks; creates dev friction when teams cargo-cult different regexes and SREs end up debugging inconsistent blocks.
- Red flag: “Validate the URL string once, then fetch.” Fails because DNS can change after validation (rebinding) and redirects can change destination; on-call toil spikes due to intermittent repros and “works in staging” discrepancies.
- Red flag: “Just require IMDSv2 and call it solved.” Reduces some attack paths but still allows SSRF-driven metadata access if attackers can set required headers or if internal components legitimately fetch tokens; creates a false sense of closure and pushes risk into detection/IR without prevention.
- “Allow all outbound, rely on app review.” Fails organizationally: code review misses sink variations across languages, and backlogs grow; meanwhile a single SSRF becomes fleet-wide credential theft, and incident response is forced into broad credential revocation.
- “Block metadata egress everywhere immediately.” Fails reliability: workloads that unknowingly depended on metadata for credentials will 500; developers create emergency exceptions or hardcode long-lived keys, increasing long-term risk and compliance burden.
- “Log full requested URLs to investigate.” Fails privacy/compliance: URLs may contain secrets/tokens; forces log access restrictions and slows investigations, while still not being sufficient to detect rebinding/redirect chains without careful structure.
- “Rely on a proxy and assume it’s safe.” Fails when proxy honors user-controlled headers (e.g., `Host`, `X-Forwarded-*`) or allows CONNECT/redirects; debugging proxy behavior becomes a specialized on-call skill, increasing toil and rollback pressure.

## Nitty Gritty
- **Protocol / Wire Details**
  - AWS IMDSv2 token flow: client does `PUT http://169.254.169.254/latest/api/token` with header `X-aws-ec2-metadata-token-ttl-seconds: <seconds>`; receives token in body; subsequent metadata `GET` must include `X-aws-ec2-metadata-token: <token>`.
  - AWS failure mode: if attacker-controlled SSRF can issue the `PUT` then the `GET`, IMDSv2 doesn’t prevent exfil; it mainly blocks unauthenticated/simple requests and some proxy misuse.
  - GCP metadata requires request header `Metadata-Flavor: Google`; response includes `Metadata-Flavor: Google`—this is a header-based CSRF-ish guard, not a network reachability control.
  - Azure IMDS managed identity token request: `GET http://169.254.169.254/metadata/identity/oauth2/token?resource=...&api-version=...` with header `Metadata: true`; returns JSON with `access_token`, `expires_in`, etc.
  - SSRF header control is the pivot: if the attacker can influence arbitrary headers in the server-side fetch, they can satisfy GCP/Azure header requirements; if your fetcher strips/overrides headers, you reduce that risk.
  - Redirect handling is a wire-level concern: `3xx Location:` can move from a public URL to link-local; safe fetch must validate every hop, not just the initial URL.
  - Anchor: IMDSv2 session token — turns metadata into a two-step capability.
  - Anchor: Metadata-Flavor header — weak guard if attacker controls headers.
  - Anchor: Link-local `169.254.169.254` — non-routable but reachable from instances.

- **Data Plane / State / Caching**
  - IMDSv2 token caching: clients typically cache the token in-memory until TTL; treat it as a bearer token—never log it, never expose via debug endpoints, and never share across tenants/containers.
  - Cache key scoping: IMDSv2 token must be scoped to the instance/VM network namespace; in containerized multi-tenant nodes, avoid a host-level singleton token accessible to untrusted workloads.
  - Cloud credential caching: SDKs cache temporary creds and refresh pre-expiry; stolen creds remain valid until expiration—incident “kill time” is bounded by expiry + propagation delays of revocation/disable.
  - Replay window: IMDSv2 token TTL defines how long an attacker can reuse it if exfiltrated; shorter TTL reduces window but increases metadata traffic and potential throttling/latency.
  - Egress proxy state: if using Envoy/sidecar, ensure it does not cache DNS results longer than intended; stale DNS can defeat post-resolve IP range checks or cause unexpected blocks during failover.
  - Failure isolation: per-request timeouts and circuit breakers must be tuned so blocked metadata attempts fail fast without consuming connection pools (otherwise SSRF becomes a self-DoS vector).
  - Anchor: Hop-limit / TTL — constrains metadata reachability via forwarding.

- **Threats & Failure Modes**
  - SSRF → metadata: attacker supplies URL that resolves (directly or via redirect) to `169.254.169.254` and exfiltrates credentials/tokens returned by IMDS.
  - Redirect chain bypass: allowlist checks only first URL; attacker uses `https://example.com/redirect?to=http://169.254.169.254/...` and wins unless every hop is validated and redirects to private/link-local are blocked.
  - DNS rebinding: validate hostname resolves to public IP, then fetch later resolves to private/link-local; mitigation requires pinning resolved IPs per request and enforcing IP-range policy at connect time.
  - IPv6 and alternative address forms: metadata may be reachable via IPv6 or via integer/hex representations; string matching fails; enforce at socket connect using canonical IP classification.
  - Proxy path: outbound proxy that can reach link-local (or that runs on host network) becomes the SSRF target; even if apps can’t reach metadata directly, they can reach a proxy that can.
  - Header smuggling/control: if fetcher forwards user headers, attacker sets `Metadata-Flavor: Google` or `Metadata: true`; mitigation includes stripping user-supplied hop-by-hop and sensitive headers, and setting an explicit allowed header set.
  - Red flag: “Block `169.254.169.254` only.” Fails because internal admin services (RFC1918, cluster DNS names) are also SSRF targets; partial fixes create complacency and repeated incident classes.
  - Red flag: “One-time DNS check.” Fails under rebinding; causes non-deterministic security bugs and hard-to-debug production incidents.
  - Break-glass risk: blocking metadata without a supported workload identity path pushes teams to hardcode long-lived keys; worsens compromise blast radius and violates least-privilege posture.
  - Policy/control: default-deny metadata egress org-wide; exceptions require owner + justification + expiry; IaC/CI checks prevent re-enabling IMDSv1 or disabling hop-limit.
  - Auditability constraint: store structured “blocked SSRF attempt” records (hashed URL components, resolved IP class, redirect count, workload identity) for 90 days without storing full URLs.

- **Operations / SLOs / Rollout**
  - Monitor-only phase first: deploy egress telemetry that counts attempted connections to metadata IPs and internal ranges per workload; do not block until you have a dependency map.
  - Rollout strategy: canary blocks by workload tier/namespace; progressive enforcement with fast rollback (feature flag) to avoid availability incidents.
  - Paging signals: alert on spikes in blocked metadata egress **and** spikes in STS/IAM token minting anomalies; correlate with 4xx/5xx in the URL fetch service to catch self-inflicted outages.
  - SLO trade-off: enforcing DNS pinning + redirect validation adds CPU and potentially extra DNS lookups; keep within <10ms p99 by caching DNS per-request (not global) and limiting redirect hops (e.g., max 3).
  - On-call playbook: when blocks cause 500s, identify which credential path broke (metadata vs workload identity), apply scoped temporary exception with expiry, and open migration bug with owner; avoid permanent allowlists that become policy debt.
  - Blast radius management: ensure blocks are enforced at the narrowest point (per-namespace egress policy or per-service egress gateway) so a misconfig doesn’t take down unrelated services.
  - Detection vs privacy: log only normalized components (scheme, port, eTLD+1 if allowed, resolved IP range category, redirect hop count) and a keyed hash of full URL for deduplication without disclosure.
  - Industry Equivalent: Envoy/sidecar proxy, Kubernetes NetworkPolicy/CNI egress, iptables/eBPF filters.

- **Interviewer Probes (Staff-level)**
  - Probe: Where do you enforce “no metadata access” so it’s bypass-resistant (socket-level vs URL parsing), and how do you prove coverage across languages and runtimes?
  - Probe: How do you design redirect + DNS rebinding defenses that meet a <10ms p99 overhead and 60k RPS, without turning DNS into a bottleneck?
  - Probe: What metrics distinguish “attack attempts” from “broken legitimate dependency,” and what are your paging thresholds to avoid alert fatigue?
  - Probe: In a cross-cloud environment (AWS+GCP), what’s your common control plane policy model for metadata access and exception governance?

- **Implementation / Code Review / Tests**
  - Coding hook: Enforce connect-time IP policy (block link-local/RFC1918) using the resolved socket address, not the URL string.
  - Coding hook: Resolve DNS once per request, pin to the specific IP(s) used, and re-check IP classification on each connection attempt; reject if resolution changes mid-flight.
  - Coding hook: Validate every redirect hop: cap max redirects, forbid scheme downgrade (https→http), and re-apply IP-range policy to each `Location` target after resolution.
  - Coding hook: Strip user-controlled headers by default; allowlist only required safe headers (e.g., `User-Agent`, `Accept`), and explicitly forbid `Metadata-Flavor`, `Metadata`, `Host` override, and proxy-control headers unless internally set.
  - Coding hook: Set aggressive timeouts (connect, TLS handshake, request, overall deadline) and low read limits to prevent SSRF-induced resource exhaustion and to keep p99 budget.
  - Coding hook: Negative tests for alternate IP encodings (IPv6, decimal/hex, dotted variants) and for redirect-to-metadata scenarios; ensure they fail closed consistently.
  - Coding hook: Add structured audit log emission on block: include workload ID, reason code, resolved IP class, redirect count, and keyed hash of URL; ensure 90-day retention pipeline exists.
  - Coding hook: Rollback safety test: feature-flag enforcement modes (observe→block) and validate that flipping modes doesn’t restart the service or drop traffic.
  - Coding hook: Ensure IMDSv2 token and cloud creds are treated as secrets: redaction in logs, no propagation into error messages, and no cross-tenant cache sharing.

## Staff Pivot
- Competing approaches (explicit):
  - A) App-only URL validation in each service/library: fastest to start, but inconsistent, bypass-prone, and impossible to audit fleet-wide coverage.
  - B) Cloud-only hardening (e.g., IMDSv2 + hop-limit) without egress control: reduces some risks but still allows SSRF to reach metadata from workloads that can make HTTP calls.
  - C) Defense-in-depth: IMDS hardening + network egress blocks + safe fetcher + detection/IR runbooks + exception governance.
- Choose C because it de-risks under ambiguity: you assume more SSRF sinks exist than you know, and you put a bypass-resistant control (egress) closest to the blast radius.
- Sequencing matters to avoid outages: start with **monitor-only egress telemetry**, then enforce blocks with scoped allowlists and expirations, while shipping a “golden path” safe fetcher used by the shared HTTP client.
- Latency trade-off argument: doing all checks in a centralized egress gateway can add hops; mitigate with local sidecar/host policy + lightweight library checks, keeping <10ms p99 overhead.
- Reliability argument: blocks will surface hidden dependencies; treat that as migration work, not a reason to weaken policy. Provide an approved credential acquisition story (workload identity / agent) to prevent key hardcoding.
- What I’d measure (security + ops):
  - Blocked attempts to metadata/IP-private ranges by workload and by code path (observe vs enforce).
  - False positive rate: number of legitimate requests blocked (validated by owner) and mean time to resolve.
  - Availability impact: 5xx rate deltas, p99 latency deltas, connection pool saturation signals.
  - Credential abuse indicators: anomalous STS/IAM token minting, unusual role assumptions, short-lived token usage spikes.
  - On-call toil: pages per week attributable to the rollout; time-to-mitigate and number of exceptions created/expired.
- Risk acceptance: allow temporary exceptions for a narrowly scoped set of legacy agents with explicit owners and expiry; do not accept broad metadata reachability from general workloads.
- Stakeholder alignment: Security sets policy baseline and threat model; Platform/SRE owns rollout safety and guardrail implementation; Product agrees on phased enforcement to protect customers; Compliance signs off on privacy-preserving audit logs and 90-day retention.
- “What I would NOT do”: immediately hard-block metadata for all workloads without a dependency inventory and rollback plan—tempting because it’s decisive, but it converts a security risk into a guaranteed reliability incident.
- Tie-back: Describe a time you rolled out a breaking security control with a monitor→enforce progression and what you measured.
- Tie-back: Describe how you handled exception governance to prevent permanent policy debt while keeping uptime.

## Scenario Challenge
- You operate a multi-tenant URL fetch service (webhooks + image fetch) at **60k RPS**; added latency budget is **<10ms p99** and availability target is **99.95%**.
- Attacker controls URL inputs and may influence headers and redirects; goal is to prevent SSRF to **cloud metadata** and **internal admin services** across both AWS and GCP.
- Hard technical constraint: you cannot rely on per-app bespoke fixes; dozens of teams share a common HTTP client and ship independently—controls must be centralized (library + egress gateway) and measurable.
- Hard technical constraint: you cannot log full URLs (may contain secrets); yet you must keep **auditable records** of blocked SSRF attempts for **90 days**.
- Cross-cloud requirement: the same guardrail model must work in AWS and GCP, and must degrade safely during partial cloud outages (e.g., DNS issues, STS hiccups) without turning into a cascading failure.
- Some workloads legitimately hit metadata today to fetch creds; you must migrate them to workload identity / approved agent without a flag day or widespread outages.
- Reliability constraint: outbound fetches are a major dependency path; adding an egress proxy hop or heavy DNS logic risks violating the <10ms p99 budget and saturating connection pools.
- On-call twist: after rolling out metadata egress blocks, a subset of workloads starts 500ing because they can’t fetch creds; teams claim “security broke prod” and request blanket exceptions.
- Multi-team/leadership twist: Security demands “block now,” Platform fears outages and wants months of telemetry, Product demands no customer impact; you must propose rollout phases, exception governance, and success metrics that all can sign.
- Privacy/compliance twist: auditors require evidence of enforcement and blocked-attempt retention, but legal restricts URL visibility; you need a structured logging/audit approach that is useful in incident response.
- Migration twist: a legacy agent depends on IMDSv1 and cannot be updated quickly; you must decide whether to allow exceptions, replace the agent, or provide a compatibility shim without re-opening SSRF risk.

**Evaluator Rubric**
- Demonstrates a layered architecture that is portable across AWS/GCP (metadata hardening + egress control + safe fetcher + detection), with clear reasoning on where enforcement must live to be bypass-resistant.
- Prioritizes rollout safety: monitor-only telemetry, canaries, feature flags, rollback plans, and scoped exception processes with expiry/ownership to manage on-call load.
- Quantifies trade-offs: latency overhead budget accounting (DNS/redirect checks, proxy hops), capacity impacts (connection pools, timeouts), and error budget impact during enforcement.
- Handles privacy/compliance concretely: designs audit logs that avoid full URLs yet remain investigable (hashing, structured fields, retention), and defines access controls for incident responders.
- Presents incident response posture: triage steps for post-block 500s, immediate mitigations that don’t permanently weaken controls, and a path to eliminate repeated exceptions.
- Shows stakeholder influence: aligns Security/Platform/SRE/Product/Compliance on phased objectives, success metrics, and risk acceptance boundaries; anticipates and counters “just block it” vs “never block” extremes.
- Tie-back: Explain how you would decide which metrics trigger moving from observe→enforce and who signs off.
- Tie-back: Explain how you would prevent “temporary” exceptions from becoming permanent and invisible.