## Title
Insider Risk: JIT + Multi‑Party Authorization (MPA) Without Breaking On‑Call (Feb 2026)

## Hook
- Standing privileges keep MTTR low, but they turn “one compromised laptop” or “one coerced admin” into full prod compromise + data export, with attribution gaps that make containment and compliance evidence painful.
- MPA sounds simple (“two people approve”), but at 2,000 engineers and 150 rotations it becomes a distributed-systems problem: correctness (separation of duties) under churn, paging, and follow‑the‑sun handoffs.
- JIT moves risk from long-lived keys to an issuance + enforcement pipeline; now your access system is production-critical and must be engineered like a tier‑0 service (multi-region, low tail latency, tested degraded modes).
- Approval latency is not just “slower”; *variance* breaks incident runbooks—on-call can tolerate 60–120s predictable overhead more than a 1–10 minute roulette wheel.
- If “approved” is enforced only in one plane (web console) but not in others (SSH, `kubectl exec`, cloud role assumption), attackers and stressed responders will route through the weakest path; inconsistency creates toil and outages.
- Strong assurance requirements (`acr`/`amr` step-up, device posture) reduce approver ATO/collusion risk, but add friction; the Staff-level job is deciding where friction buys real risk reduction vs just angering on-call.
- Auditing must be both compliance-grade (1-year retention, dual control evidence) and privacy-preserving (no customer payloads); logs that are incomplete or uncorrelatable are operational debt that explodes during incidents.
- Degraded mode determines culture: if the approval service is unreachable, either you block access (outage amplifier) or you allow bypass (permanent backdoor). The only workable answer is a bounded, noisy break-glass path with forced review.
- Rollout safety is a constraint: legacy root SSH keys and long-lived cloud keys exist; if you break automation or incident playbooks, you’ll get “temporary” standing-access exceptions that never expire.

## Mental Model
Two-person control on a submarine: one person can start the launch sequence, but cannot complete it alone; an independent operator must also turn a key, and the system records exactly who did what. JIT is a key that only works for a short window; MPA is requiring an independent second key-turn. The engineering challenge is making those key-turns fast and reliable during incidents while preventing duplication (self-approval), forgery (unbound approvals), and bypass (alternate access paths).

- The first key-turn maps to creating a structured *request record* (`resource`, `role`, `reason`, `duration`, `ticket_id`) that becomes the audit and enforcement root.
- The second key-turn maps to an independent approver producing a *signed approval artifact* that enforcement points can verify without trusting the requester.
- The “key expires” maps to short-lived SSH certs / OIDC tokens with tight `valid_before`/`exp`, plus constraints like `source-address` and required step-up (`acr`/`amr`).
- The submarine launch log maps to tamper-evident audit trails that correlate `request_id → approvals → issued creds → enforcement events` for incident response and compliance.
- Adversarial mapping: if both keys live in the same pocket (requester can approve, or approvals don’t require strong step-up), a single compromised account collapses MPA into single-party control.

## L4 Trap
- **Junior approach:** “We trust admins; background checks are enough.” **Why it fails at scale:** ATO, coercion, and human error are probabilistic certainties across large orgs. **Friction/toil risk:** you pay later via longer IR, ambiguous root cause, and repeated “who touched prod?” investigations that pull in multiple teams.
- **Junior approach:** “Require approvals for everything, always.” **Why it fails at scale:** approval queues become the new global lock; responders optimize for speed by bypassing controls. **Friction/toil risk:** you create a shadow-access culture (shared secrets, backchannel group adds) and inject tail latency into incident response.
- **Red flag:** “Approvals happen in chat (‘LGTM’, emoji) not cryptographically bound to a specific `request_id`/`resource`.” **Why it fails at scale:** you can’t prove what was approved vs executed; approvals become replayable and non-auditable. **Friction/toil risk:** post-incident compliance becomes manual log archaeology and blocks operational learning.
- **Red flag:** “MPA is implemented only in the web console; SSH/kubectl paths still accept standing keys.” **Why it fails at scale:** security is only as strong as the weakest enforcement point. **Friction/toil risk:** inconsistent runbooks and wasted on-call time figuring out which path works under pressure.
- **Red flag:** “Break-glass is a shared root key / wiki secret.” **Why it fails at scale:** it becomes the default access path and is impossible to contain if leaked. **Friction/toil risk:** constant key rotations, unclear accountability, and recurring incidents driven by uncontrolled access.
- **Junior approach:** “Make tokens ultra-short (e.g., 5 minutes) to be secure.” **Why it fails at scale:** clock skew, issuance flakiness, and step-up prompts explode; automation becomes brittle. **Friction/toil risk:** responders re-mint creds mid-mitigation and start lobbying for permanent exemptions to meet MTTR.

## Nitty Gritty

**Protocol / Wire Details**
- SSH JIT: issue OpenSSH user certificates of type `ssh-ed25519-cert-v01@openssh.com` signed by an internal CA; encode `key_id` as `request_id:grant_id` and set `valid_after/valid_before` to 10–60 minutes (shorter for break-glass).
- Constrain SSH certs with critical options: `source-address=<corp egress CIDR>` to reduce reuse from stolen laptops; `force-command=<session-wrapper>` to ensure consistent server-side enforcement and metadata capture.
- Keep SSH principals policy-shaped (not user-shaped): `principals=["prod-mutate-k8s", "prod-debug-readonly", "data-export"]` so enforcement maps to action categories and doesn’t require bespoke per-user configuration.
- Web/API JIT: mint short-lived OAuth/OIDC access tokens; enforcement checks `Authorization: Bearer <token>` plus claims `iss`, `aud`, `sub`, `exp`, `nbf`, `iat`, `jti`, and privilege/role scopes derived from the approved grant.
- Assurance gating: require `acr`/`amr` to meet the action’s policy (e.g., step-up requiring WebAuthn user verification); gateways reject validly-signed tokens that lack required assurance for high-risk actions.
- Request record schema (stored server-side, referenced everywhere): `{ "request_id", "resource", "role", "reason", "duration_seconds", "ticket_id", "requester", "created_at" }`; treat `reason`/`ticket_id` as required for privileged actions to keep audit reviews actionable.
- Approval artifact as an immutable signed blob (often JWT-shaped): `{ request_id, grant_id, approvers[], policy_version, not_before, not_after, constraints{resource, role, source_ip, max_actions} }` signed so enforcement can verify without online calls.
- Anchor: request_id — Correlates approvals, credentials, and audit events.
- Anchor: acr/amr — Enforces step-up; reduces approver/requester ATO impact.

**Data Plane / State / Caching**
- Cache approver eligibility (group membership + on-call rotation) with short TTL (e.g., 30–120s) to bound p95 latency; require push invalidation on termination/role change to prevent stale privilege.
- Termination/role-change kill switch: publish an `entitlement_epoch` bump; enforcement points deny if a presented grant was minted under an older epoch than currently active for the subject or organization.
- Cache active JIT grants at enforcement points keyed by `grant_id` until expiry; validate `not_before/not_after` locally to avoid synchronous dependency on central services.
- Emergency revocation: maintain `revocation_epoch` (global or per-resource) that enforcement points consult; bumping it invalidates cached grants without enumerating them.
- Enforce context binding: a grant for `resource="prod-k8s"` and `role="prod-mutate"` must not be accepted by data-export endpoints even if signature is valid; require exact `aud` and `resource` match.
- Multi-region considerations: replicate policy keys/epochs regionally; design conservative behavior under partitions (deny normal grants if freshness is uncertain; allow only bounded break-glass with audit noise).
- Anchor: grant_id — Stable handle for caching, revocation, and debugging.

**Threats & Failure Modes**
- Collusion / compromised approver account: require step-up for approval actions (WebAuthn UV), device posture checks for approvers, and out-of-band notifications for high-risk approvals to reduce silent rubber-stamping.
- Separation of duties: enforce `requester != approver`; for critical actions require approver independence (different role/team) and sometimes 2 approvals; encode in policy evaluation, not just UI.
- Stale entitlements: cached on-call/HR data can over-grant after org changes; mitigate with short TTL + push invalidation + “deny if cache age > bound” at enforcement points.
- “Approval system down” failure mode: if normal path blocks, engineers will seek permanent bypass; require a degraded mode that’s faster than workarounds but bounded (very short TTL), noisy (paging), and review-triggering (auto-ticket).
- Audit gaps: missing `request_id`/`grant_id` correlation breaks IR and compliance evidence; treat missing logs as a production defect with alerts and ownership.
- Red flag: “Approver identity checked only during approval UI flow, not embedded in the signed grant.” Breaks non-repudiation and enables substitution/replay.
- Red flag: “Break-glass issues the same TTL/scopes as normal access, just skipping approval.” Converts emergency access into an invisible permanent bypass.
- Anchor: revocation_epoch — Fast global kill switch for cached grants.

**Operations / SLOs / Rollout**
- Access SLOs: track `time_to_access` p50/p95 (on-call separately), approval success rate, denial breakdown (policy vs system), and “system-caused denial” error budget; page when p95 blows the 5-minute constraint.
- Hot-path reliability: enforcement points must validate signed grants locally and avoid synchronous IdP/approval calls on every privileged request (especially during major outages).
- Break-glass operations: issue 15-minute grants, page Security + duty manager immediately, and auto-create an audit/postmortem ticket; force a structured reason referencing the incident.
- Tamper-evident auditing: append-only logs capturing who requested, who approved, what was accessed, when, where (enforcement point), and outcome; retain 1 year; explicitly avoid customer payload logging (log identifiers/counts, not data).
- Alerting on integrity: missing audit events, enforcement points that stop emitting logs, or actions outside the grant window should page as “control failure,” not just be dashboard noise.
- Exception control: every exception has owner + expiry; measure exception volume/age and treat “exceptions > break-glass” as a control anti-pattern that needs leadership intervention.
- Anchor: break-glass — Short-lived, loud access that forces follow-up.

**Interviewer Probes (Staff-level)**
- Probe: How do bastions/gateways enforce MPA if the approval service or IdP is unreachable (offline-verifiable artifacts, cache freshness, revocation)?
- Probe: What does your privilege taxonomy look like, and how do you prevent it from becoming unmaintainable policy sprawl that on-call can’t reason about?
- Probe: How do you mitigate “compromised approver rubber-stamps” without making approvals unusably slow (step-up, device posture, notifications)?
- Probe: Which metrics detect bypass culture early (exception creep, break-glass rate, out-of-band access paths), and what actions do you take when they regress?

**Implementation / Code Review / Tests**
- Coding hook: Enforce invariants `requester != approver` and (if 2 approvals) `approver1 != approver2`; verify independence constraints in policy evaluation, not only UI.
- Coding hook: Validate `duration_seconds` against policy maxima per action category; reject missing `reason`/`ticket_id` for privileged roles; negative tests for boundary values.
- Coding hook: Token claim validation: strict checking of `aud/iss/sub/exp/nbf/iat/jti` plus required `acr/amr`; include clock-skew tolerance tests and “weak assurance” rejection tests.
- Coding hook: SSH cert issuance tests: verify `valid_before-valid_after` bounds; ensure required critical options (`source-address`, `force-command`) are present; reject if principals are not in an allowlist.
- Coding hook: Replay protection: bounded replay cache keyed by `jti`/`grant_id`; test duplicate approval submissions, concurrent approvals, and idempotency semantics.
- Coding hook: Revocation correctness: bump `revocation_epoch` and assert cached grants are denied within defined propagation bounds; test partial region failure and stale-cache behavior.
- Coding hook: Audit completeness tests: for every privileged enforcement decision, assert an audit record exists with `request_id`, `grant_id`, enforcement point ID, and decision; test that customer payload fields are redacted by default.
- Coding hook: Degraded-mode chaos tests: simulate approval service outage; confirm only break-glass succeeds and that it triggers paging + auto-ticket + shorter TTL.

## Staff Pivot
- Evaluate competing models explicitly:
  - **A)** Standing admin roles + quarterly reviews: lowest friction, highest insider/ATO blast radius, weakest attribution.
  - **B)** JIT but single-party approval/self-approval: reduces standing exposure, still collapses under single compromised account or coercion.
  - **C)** JIT + MPA + audited break-glass: strongest for high-risk actions, but adds latency and creates a new reliability-critical service.
- Choose **C** for high-risk actions (prod mutations, data exports, key disables, break-glass) and allow a lighter **B-tier** for low-risk debugging (read-only introspection) to protect MTTR.
- Decisive trade-off: accept small, **predictable** access latency to buy reduced blast radius + strong attribution; unpredictability (tail latency, flaky approvals) is worse than modest overhead because it breaks incident response muscle memory.
- Architecture argument to meet constraints: use offline-verifiable signed grants and local enforcement caches so access decisions don’t require a live centralized call path during outages.
- Risk prioritization under ambiguity: start where expected loss is highest (data export, production mutation paths) and defer less critical hardening until workflow adoption is stable—otherwise you’ll ship a perfect policy nobody uses.
- What I’d measure: `time_to_access` p50/p95 (on-call vs non), approval latency and variance, approval failure rate by cause, break-glass frequency/duration, % privileged actions covered by MPA, exception count/age, and audit correlation completeness.
- On-call/SRE reality: treat the access system as tier‑0 with its own SLO/error budget; if it’s unreliable you are directly increasing MTTR and risking availability regressions.
- Stakeholder alignment: co-author a tiered policy matrix with SRE (speed/MTTR), Compliance (dual control evidence), Security (blast radius reduction), and Product (availability); define what qualifies for break-glass and the enforcement for after-the-fact review.
- Policy/compliance trade-off: keep 1-year tamper-evident metadata logs and explicit separation-of-duties evidence, while forbidding customer payload logging to stay within privacy boundaries and reduce sensitive log handling.
- Risk acceptance: allow break-glass for true P0s with strict TTL + immediate paging + mandatory follow-up; do not accept “temporary standing access” because it becomes the default and is rarely removed.
- What I would NOT do: disable MPA during incidents or grant permanent on-call admin “for speed”—it’s tempting, but it converts rare emergency risk into continuous high-privilege exposure.
- Tie-back: Describe how you used p95 latency + error budgets to drive a security control rollout.
- Tie-back: Describe mechanisms you used to prevent exception processes from becoming the default access path.

## Scenario Challenge
- You have **2,000 engineers** and **150 on-call rotations**; responders must reach prod within **5 minutes p95** during incidents while maintaining **99.99%** platform SLO.
- Security constraint: eliminate standing admin roles; require **multi-party approval** for prod mutations and data exports; assume some engineer laptops will be compromised.
- Reliability constraint: the access system must be **multi-region** and must function during major outages; it cannot depend on a **single IdP call-path** at request time.
- Hard technical constraint: enforcement points (SSH bastions, K8s admission for `kubectl exec`/`port-forward`, API gateways, cloud role assumption) must make allow/deny decisions even when central services are unreachable—“just call the approval service” is not an option.
- Privacy/compliance: keep **1-year auditable logs** of privileged access and approvals without logging customer payloads; meet SOX/PCI-style dual control expectations for sensitive systems.
- Developer friction: engineers use SSH, kubectl, and web consoles; you need one coherent JIT workflow (CLI/SDK + minimal retraining) or people will create backchannels.
- Migration/back-compat constraint: legacy root SSH keys and long-lived cloud access keys exist; phase out over **6 months** without breaking automation and scheduled jobs.
- Incident/on-call twist: a P0 outage hits and the approval service is unreachable; on-call needs immediate access—design break-glass that is fast, bounded, noisy, and doesn’t create a permanent bypass culture.
- Multi-team/leadership twist: SRE leadership fears slowed MTTR, compliance demands strict dual control, security demands “no standing access,” product wants faster deployments—propose tiered controls, degraded modes, and success metrics everyone can sign.
- Operational integrity twist: approvals are being rubber-stamped under pressure—define how you detect this via metrics/logs and how you correct it without exploding on-call toil.
- Rollout safety twist: an enforcement point starts denying valid access due to clock skew or stale caches—explain how you prevent a cascading outage and avoid a rollback to standing access.
- Auditability twist: you discover gaps where privileged actions lack `request_id` correlation—describe how your system surfaces, alerts, and remediates this as a control failure.

**Evaluator Rubric**
- Shows explicit assumptions and a tiered privilege taxonomy mapping actions → approvals → TTL → logging, avoiding unmaintainable policy sprawl.
- Designs offline-verifiable enforcement (signed grant artifacts, local validation, revocation epochs, cache freshness bounds) and handles partitions/multi-region failure modes concretely.
- Prioritizes risk under ambiguity (what must be MPA immediately vs what can be lighter-weight) while protecting MTTR and reducing bypass incentives.
- Defines SLOs/metrics and operational hooks (paging triggers, dashboards, audit gap alerts) and treats the access system as a production service with error budgets and incident playbooks.
- Provides a degraded-mode/break-glass plan that is bounded (short TTL), loud (paging + auto-ticket), reviewable (forced follow-up), and culturally resistant to becoming the default.
- Addresses privacy/compliance explicitly (metadata-only logs, retention, separation of duties evidence) without expanding customer data handling footprint.
- Includes a migration/rollout plan with canary/rollback safety, automation compatibility strategy, and exception governance (owner + expiry + visibility).
- Demonstrates stakeholder influence by translating trade-offs into SRE/Product/Compliance/Security terms and proposing alignment mechanisms (policy matrix, exception process, success criteria).