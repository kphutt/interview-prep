**Episode 8 — Supply Chain Security: SLSA Provenance + Deploy‑Time Verification (Trust the Binary, Not the Builder)**

2) **The Hook (The core problem/tension).**
- If CI/build gets compromised, you can ship a perfect-looking binary that’s malicious.  
- Vulnerability scanning finds known bad code; it doesn’t prove **who built this artifact from what source**.  
- Strong supply-chain controls can slow builds and block releases—so the real challenge is **measurable rollout + safe break-glass**.

3) **The "Mental Model" (A simple analogy).**  
Provenance is a tamper-evident receipt: “This artifact came from commit X, built by builder Y, with dependencies Z.” Deploy-time verification is the bouncer checking the receipt before letting the artifact into production.

4) **The "L4 Trap" (Common junior mistake + why it fails at scale).**
- “Have developers sign artifacts with PGP.” Security-only thinking ignores key theft and the fact you need *platform trust*, not human trust.  
- “Just add an image scanner.” Scanners don’t stop a compromised builder from shipping malware *today*.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **Artifact identity:** treat the artifact digest (e.g., `sha256:<...>`) as the canonical identity; tags like `:latest` are not security boundaries.  
- **SLSA provenance (protocol detail):** in-toto statement includes `_type`, `subject[].digest.sha256`, `predicateType` (e.g., `https://slsa.dev/provenance/v1`), and `predicate` with `builder.id`, `buildType`, `invocation`, `materials`.  
- **Signing (crypto detail):** wrap provenance in **DSSE** (`payloadType`, `payload`, `signatures[].sig`) or equivalent; verify signature against a trusted key/identity (KMS/HSM-backed).  
- **Hermetic/ephemeral builds:** isolate builds, pin toolchains, restrict network, and use ephemeral workers to reduce “persistent CI backdoor” risk (SLSA L3-style goals).  
- **Deploy-time verification:** an admission controller / deploy gate verifies (a) artifact signature, (b) provenance signature, and (c) provenance matches policy (trusted builder, trusted repo, reviewed commit).  
- **Data-plane/caching #1 (admission decisions):** cache `(image_digest, policy_version) -> allow/deny` briefly to avoid repeated signature/provenance verification at high deploy QPS.  
- **Data-plane/caching #2 (key material):** cache trusted keysets / trust bundles and handle `kid` rotation safely; stale-while-revalidate avoids deploy outages during key fetch glitches.  
- **Operational detail #1 (key lifecycle):** keep signing keys in KMS/HSM, rotate regularly, and maintain a “key compromise” playbook (block old keys, force rebuilds, audit blast radius).  
- **Operational detail #2 (rollout):** start in audit-only mode (measure missing provenance), then enforce for a narrow tier, then expand; instrument “why denied” to avoid developer dead-ends.  
- **Policy/control:** define required build provenance by environment (prod vs staging) and service tier; require exceptions to be time-bounded with explicit approver.  
- **Explicit threat/failure mode:** if build workers are long-lived with cached credentials, an attacker can persist and sign trojans indefinitely—provenance without ephemeral builders may provide false confidence.  
- **Industry Equivalent:** SLSA + in-toto attestations + Sigstore/cosign (or Notary v2) + Kubernetes admission control.

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** “Trust CI logs + dev approvals” (weak against CI compromise; hard to audit).  
  - **B)** Vulnerability scanning only (necessary, not sufficient; doesn’t prove integrity/origin).  
  - **C)** **SLSA provenance + deploy-time verification** (strong integrity; requires platform investment).  
- I pick **C**, but I phase it: audit-only → enforce for internet-facing/prod → expand. This avoids a “security launch” turning into a release outage.  
- What I’d measure: % prod deploys with valid provenance, deny rate by reason, build-time delta, admission latency p99, and number of emergency break-glass uses.  
- Risk acceptance: I’ll accept a quarter of mixed mode for low-risk services, but I won’t accept unsigned/provenance-less artifacts in high-risk prod without a formal exception.  
- Stakeholder/influence: partner with DevProd/Release Eng and Compliance—frame it as “faster incident containment” (provenance answers “what’s running where?”) not just security purity.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You have **500 repos**, **2k builds/day**, and **300 Kubernetes clusters**. A competitor suffered a CI compromise—leadership demands supply-chain hardening.  
- Latency/velocity: build time must not increase by >10%; admission verification must add **<50ms p99**; deploy pipeline SLO is **99.99%**.  
- Reliability: verification cannot be a single point of failure; clusters must still deploy safely during partial outages (key server / transparency log / provenance store).  
- Security: ensure prod artifacts are built from reviewed commits on trusted builders; stop “developer laptop build” artifacts from reaching prod.  
- Privacy/compliance: keep an audit trail of “commit → build → artifact → deploy” without leaking secrets from build inputs or source.  
- Developer friction: teams use heterogeneous build tools; you need a golden path that doesn’t require every team to become supply-chain experts.  
- Migration/back-compat: most existing images are unsigned; you must support mixed mode with explicit deadlines and per-namespace enforcement.  
- Incident/on-call twist: enforcement goes live and blocks a critical hotfix because provenance upload failed—how do you break-glass safely and prevent permanent bypass?  
- Multi-team/leadership twist: compliance wants immediate enforcement, product wants zero deploy blocks, infra wants minimal new components—propose tiered policy, rollout phases, and exception governance.