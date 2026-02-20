## Title
Episode 8 — Supply Chain Security: SLSA Provenance + Deploy‑Time Verification (Trust the Binary, Not the Builder)  
Staff focus: integrity guarantees with measurable rollout, <50ms gates, and governed break-glass

## Hook
- A compromised CI runner can ship a perfect-looking, test-passing artifact that’s malicious; the hard part is **proving origin/integrity (commit→builder→artifact)** rather than detecting known-bad code after the fact.
- Vulnerability scanners answer “does it contain a known CVE?” but not “**who built this exact digest from what source and deps**”; during an incident, the latter determines blast radius and rebuild priority under ambiguity.
- “Signed” is meaningless unless the signature is tied to a **trusted builder identity** and controlled key lifecycle; otherwise an attacker who steals a key can mint “legit” malware indefinitely.
- Container tags optimize for velocity and ergonomics, not security; enforcing digest-based identity changes rollback, promotion, and “what’s running where?” workflows (and causes real developer friction if done bluntly).
- Deploy-time verification is now a production dependency on the deploy path; you’re budgeting **<50ms p99** for crypto + policy evaluation + (sometimes) network fetch, under bursty rollout QPS.
- Reliability trade-off is unavoidable: fail-closed increases security but can violate **99.99% deploy SLO** during provenance store / key distribution / transparency log degradation; fail-open can become an attacker’s outage-shaped bypass.
- Rollout safety is part of the control: audit-only → scoped enforcement → tiered expansion; otherwise the first enforcement flip becomes an on-call event that trains orgs to bypass security.
- Break-glass is mandatory for hotfixes, but it must be **time-bounded, audited, and measurable** or it turns into permanent policy rot (and compliance risk).
- Compliance wants an audit trail (commit→build→artifact→deploy) with retention guarantees, while security wants minimal data exposure; provenance must be **useful without leaking secrets** from build inputs or repo metadata.

## Mental Model
Provenance is a tamper-evident receipt stapled to an artifact: “this digest came from commit X, built by builder Y, using materials Z.” Deploy-time verification is the bouncer at the production door: it doesn’t care how convincing the artifact looks—it checks the receipt against house rules. At Staff level, the bouncer must be fast, highly available, and resistant to being socially engineered (break-glass) or dependency-failed (key/provenance outages).

- The receipt → DSSE-wrapped, signed in-toto/SLSA provenance attached to the artifact (or retrievable by digest) and retained for auditability.
- The bouncer → Kubernetes admission controller / deploy gate that verifies signatures and enforces policy (trusted builder, trusted repo, reviewed commit) before the artifact can run.
- House rules → environment/tier-specific policy (prod vs staging, high-risk vs low-risk) plus explicit exception governance and telemetry.
- Adversarial failure mode mapping → if an attacker controls a long-lived builder, they can produce *both* malicious artifacts *and* “valid” receipts; without ephemeral/hermetic builders and bounded credentials, the bouncer is checking forged receipts.
- Operational mapping → bouncer decisions must be cacheable and replay-safe so partial outages (key fetch, provenance store) don’t become global deploy outages.

## Common Trap
- **Red flag:** “Have developers PGP-sign artifacts.” Fails at scale because human key hygiene is inconsistent and keys get phished/stolen; it also creates persistent toil (key rotation, revocation, lost keys) and brittle release blocks that push teams to bypass controls under pager pressure.
- **Red flag:** “Just add an image scanner and block critical CVEs.” Scanners don’t prevent a compromised builder from shipping malware *today* and tend to add slow, noisy gates; the result is false confidence plus repeated emergency exceptions that degrade both security posture and deploy reliability.
- **Red flag:** “Enforce ‘must be signed’ without specifying *who* is allowed to sign.” At scale, teams generate ad-hoc keys or reuse shared keys; verification becomes inconsistent across clusters/environments, causing deny storms, hotfix blocks, and on-call escalations to “temporarily disable enforcement.”
- “Treat `:prod`/`:latest` as the identity boundary.” Tags are mutable pointers; this breaks audit trails, rollback correctness, and incident response (“what digest actually ran?”), creating manual forensics toil and cross-team blame loops during outages.
- “Put all verification behind a single centralized service.” It’s tempting for governance, but it becomes a latency bottleneck and a single point of failure; when it degrades, you force a choice between violating deploy SLOs or turning off security globally.

## Nitty Gritty
**Protocol / Wire Details**
- Artifact identity: treat the OCI artifact digest (`sha256:<hex>`) as the principal; tags are UX-only and never a security boundary.
- Anchor: Image digest — canonical identity; tags are mutable pointers.
- SLSA provenance as in-toto Statement (JSON): `_type: "https://in-toto.io/Statement/v1"`, `subject: [{name, digest: {sha256}}]`, `predicateType: "https://slsa.dev/provenance/v1"`.
- Policy-relevant `predicate` keys to enforce: `builder.id` (stable builder identity), `buildType` (URI of build system/workflow), `invocation` (config source/parameters—careful), `materials[]` (source/dependency digests/URIs).
- DSSE envelope shape: `{payloadType, payload: base64(statement), signatures: [{sig: base64, kid|keyid}]}`; verification is over exact payload bytes.
- Anchor: DSSE payload bytes — avoid JSON canonicalization signature bypasses.
- Signature verification: standardize algorithm(s) and reject drift (e.g., allow ECDSA P-256 + SHA-256 and/or Ed25519); never “auto-accept” unknown algorithms because it simplifies rollouts.
- Trust mapping: verify signature against a managed trust bundle (KMS/HSM-backed keys or short-lived certs bound to a workload identity); policy should reference identities (“trusted builder workload”) rather than raw public keys.
- Sigstore-style option (agenda-implied): verify signer identity from short-lived certificate claims (e.g., OIDC identity/SAN) and optionally check transparency log inclusion; define offline behavior (cached roots + bounded freshness) to avoid deploy outages.
- Receipt laundering prevention: provenance `subject[].digest.sha256` must exactly equal the deployed digest; additionally constrain allowed repo URIs and commit SHA formats so provenance can’t be replayed across repos/artifacts.

**Data Plane / State / Caching**
- Admission/deploy verification should be a deterministic function of `(digest, policy_version, attestation_bundle, time)` so incidents are replayable and debuggable without hidden mutable state.
- Decision cache: `(image_digest, policy_version) -> allow|deny|reason` with short TTL (1–5 min) to hit <50ms p99 under deploy bursts; include negative caching for “missing provenance” to prevent thundering herd.
- Anchor: (digest, policy_version) cache — bounds p99 latency during rollouts.
- Trust bundle cache: cache keysets/certs by `kid` and issuer identity; implement stale-while-revalidate + hard expiry so transient fetch failures don’t cause global deploy outages.
- Replay/age checks: enforce max attestation age and clock-skew window; maintain a replay cache of recently seen `(attestation_hash, signature_fingerprint)` to reduce repeated expensive verification and to detect suspicious reuse patterns.
- Digest normalization: verify the digest that will actually run (manifest vs platform-specific image); otherwise you can “verify” one digest and schedule another, breaking integrity guarantees and confusing incident blast-radius queries.

**Threats & Failure Modes**
- Long-lived builders: persistent CI workers + cached credentials enable durable backdoors; provenance can become “attacker-signed truth” unless builders are ephemeral and credentials are scoped/short-lived.
- Red flag: Provenance without ephemeral/hermetic builders — false confidence, delayed detection, higher MTTR.
- Red flag: Global fail-open on verifier dependency errors — creates an outage-shaped bypass attackers can trigger.
- Key compromise: leaked signing key / stolen workload identity token; response requires immediate trust bundle update (revoke/block), forced rebuild of affected artifacts, and runtime inventory (“where is this digest running?”) for containment.
- Identity spoofing: attacker sets `builder.id` string to a trusted value; mitigation is binding—signature issuer identity must cryptographically map to the asserted `builder.id` (reject if claim and signer disagree).
- Privacy/compliance failure: provenance `invocation.parameters` or `materials.uri` can leak secrets or internal topology; enforce field allowlists + redaction, and set retention/access controls as part of the threat model (compliance + least privilege).
- Anchor: Ephemeral builders — limits attacker dwell time inside CI.

**Operations / SLOs / Rollout**
- Rollout sequencing: audit-only (measure missing/invalid provenance) → enforce in a narrow tier/namespace → expand to prod tiers; prioritize based on measured risk (internet-facing, data sensitivity) rather than org chart.
- Latency engineering: keep crypto verification local and minimize synchronous network calls; prefetch attestations on image pull or deploy pipeline stages when possible, and track admission p50/p95/p99 plus cache hit ratio.
- Degradation policy: if provenance store/key fetch is degraded, allow only if you have a recent cached allow decision for same `(digest, policy_version)`; for unseen digests, deny in high-risk prod but allow-with-alert in low-risk staging (explicit risk acceptance).
- Break-glass governance: exception is scoped (service/namespace), time-bounded, requires explicit approver identity, and is fully auditable; alert on repeated use and auto-expire to prevent “temporary” bypass from becoming baseline.
- Anchor: Break-glass TTL — prevents “temporary” bypass becoming the new normal.
- Key lifecycle ops: scheduled rotation with overlap window; runbook for compromise that includes revocation propagation time, policy rollback strategy, and paging criteria when deny rates spike.
- Developer friction controls: denial reasons must be actionable (“untrusted builder”, “digest mismatch”, “missing DSSE”) and attributable by repo/team; use top deny reasons to drive a golden path (templates, build wrappers) instead of bespoke per-team fixes.

**Interviewer Probes (Staff-level)**
- Probe: What’s your caching strategy to hit <50ms p99, and how do you invalidate safely on policy/key rotation without causing deny storms?
- Probe: Where do you enforce “reviewed commit” and how do you represent that claim in provenance without trusting mutable CI metadata?
- Probe: How do you bind `builder.id` to a trusted signing identity so it can’t be spoofed as a string field?
- Probe: When the key server / transparency log / provenance store is partially down, what’s your explicit failover behavior by environment and why?

**Implementation / Code Review / Tests**
- Coding hook: Verify DSSE signature over the raw decoded `payload` bytes; reject inputs requiring JSON reserialization to “make it verify.”
- Coding hook: Enforce `subject[].digest.sha256 == deployed_digest`; reject multiple subjects unless you have explicit multi-subject policy semantics.
- Coding hook: Implement decision cache keyed by `(digest, policy_version)` with bounded TTL; add negative caching for missing provenance to avoid thundering herd under deploy retries.
- Coding hook: Trust bundle fetch must implement stale-while-revalidate + hard expiry; test simulated key endpoint timeouts so you don’t accidentally become global fail-open.
- Coding hook: Add rotation tests: accept new key + old key during overlap; deny old key after revocation timestamp; ensure revocation propagates within defined SLO.
- Coding hook: Fuzz and size-cap provenance parsing (nested JSON depth, large `materials` arrays, weird unicode) to prevent admission DoS and parser confusion.
- Coding hook: End-to-end break-glass tests: exception issuance, audit log emission, auto-expiry, and post-expiry re-enforcement; verify no “forever allow” states survive restarts.

## Staff Pivot
- Competing approach A: “Trust CI logs + dev approvals.” Weak against CI compromise and painful to audit—incident response becomes log forensics under pressure with unclear integrity of the logs themselves.
- Competing approach B: “Vulnerability scanning only.” Necessary hygiene but not an integrity control; it cannot answer “is this the intended artifact from reviewed source?” and doesn’t stop today’s compromise.
- Chosen approach C: **SLSA provenance + deploy-time verification** because it creates an enforceable contract between source, builder identity, and artifact digest—and reduces incident ambiguity (“what’s running where and how was it built?”).
- Decisive trade-off: C adds platform complexity and critical-path latency, so the Staff move is to engineer it like an SRE-facing data plane (caching, degradation modes, observability) rather than a best-effort security add-on.
- Rollout argument: audit-only first to quantify missing provenance and top deny reasons; then enforce for internet-facing/prod tiers; only then expand—this prevents the “security launch” from turning into a release outage and trains teams through measured adoption.
- Risk acceptance: accept a quarter of mixed mode for low-risk services with explicit deadlines and telemetry; do not accept unsigned/provenance-less artifacts in high-risk prod without time-bounded, approved exceptions.
- Availability posture: avoid single points of failure—verifiers must be horizontally scalable, cache-heavy, and capable of safe degraded operation during key/provenance/transparency interruptions.
- Break-glass stance: build a safe hotfix path (scoped + TTL + audit) and treat break-glass rate as a leading indicator of control quality (or systemic reliability issues in provenance upload).
- What I’d measure (security + ops): % prod deploys with valid provenance; deny rate by reason; admission p99 latency; cache hit ratio; build-time delta (must stay <10%); verifier error budget burn; break-glass count + duration; time-to-containment during drills/incidents.
- Stakeholder alignment: partner with Release Eng/DevProd for a golden path (minimize per-repo work), SRE for SLO/degradation policy, and Compliance/Legal for audit trail + retention/redaction—frame as “faster containment and provable change control,” not purity.
- What I would NOT do: flip global enforcement immediately or require every team to manage keys/signing; both are tempting “simple policies” that create widespread outages, bypass culture, and long-term toil.
- Tie-back: Describe a time you introduced a hard gate—what metrics proved it didn’t harm SLOs?
- Tie-back: Describe how you handled an incident where build integrity/asset inventory was ambiguous.

## Scenario Challenge
- You own rollout design for 500 repos, ~2k builds/day, and 300 Kubernetes clusters after a competitor’s CI compromise; leadership expects rapid, credible hardening without freezing releases.
- Latency constraint: build time increase must be **≤10%**; deploy-time verification must add **<50ms p99** on the admission/deploy path (crypto + policy + any fetch).
- Reliability constraint: deploy pipeline SLO is **99.99%**; verification must not be a single point of failure, and clusters must continue to deploy safely during partial outages (key distribution, provenance store, transparency log).
- Security constraint: prod artifacts must be built from reviewed commits on trusted builders; block “developer laptop build” artifacts from ever reaching prod, even if they’re tagged like prod.
- Migration constraint: most existing images are unsigned; you must support mixed mode with explicit deadlines and **per-namespace / per-tier enforcement** to avoid immediate brownouts.
- Developer friction constraint: heterogeneous build tools and workflows; the solution must provide a golden path that doesn’t require every team to become an attestation or PKI expert.
- Compliance/privacy constraint: maintain an audit trail “commit → build → artifact → deploy” with retention, but prevent provenance from leaking secrets (tokens in build args, internal URIs in materials).
- Hard technical constraint: some clusters have restricted egress or intermittent connectivity; you cannot assume every admission decision can synchronously reach external key/provenance services, yet you must still prevent new untrusted digests in prod.
- Policy twist: compliance demands immediate enforcement everywhere; product demands zero deploy blocks; infra demands minimal new components—your proposal must include tiered policy, phased rollout, and exception governance that all three can sign.
- Incident/on-call twist: enforcement goes live and blocks a critical prod hotfix because provenance upload failed (not because the artifact is bad); you must break-glass safely, keep auditability, and prevent the exception from becoming a permanent bypass.
- Operational realism: you need measurable “why denied” reasons, dashboards by org/team, and a paging model that doesn’t drown on-call in expected migration churn.
- Ownership constraint: multiple teams own CI, registry, cluster policy, and compliance tooling; you need a plan that is resilient to partial adoption and unclear ownership boundaries.

**Evaluator Rubric**
- States explicit assumptions and threat model boundaries (builder compromise, key compromise, replay/TOCTOU) and prioritizes controls that reduce worst-case blast radius.
- Proposes an architecture that meets latency/SLO constraints via caching, local verification, and safe degraded modes—without turning security dependencies into global release blockers.
- Defines concrete policy semantics: trusted builder identities, repo/commit constraints, environment/tier differences, and how “reviewed commit” is asserted and verified.
- Presents a phased rollout with audit-only measurement, scoped enforcement, deadlines, and clear rollback/disable mechanics that are themselves governed and observable.
- Treats break-glass as an engineered system (scope, TTL, approver identity, audit logs, alerting) and uses metrics to prevent permanent bypass culture.
- Includes an incident playbook for key compromise and verifier dependency outages (containment steps, trust bundle updates, forced rebuild strategy, “what’s running where” queries).
- Balances developer friction with security outcomes via a golden path, actionable denial reasons, and ownership alignment (Release Eng/SRE/Compliance/Product).
- Demonstrates stakeholder influence: frames trade-offs in risk + availability terms, negotiates tiered enforcement, and defines what “risk acceptance” requires (time-bound exceptions, explicit approvers, measurable outcomes).