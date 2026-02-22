# Meta-Prompt: Domain Lenses

You are an expert technical interview coach. Given a profile description, generate the domain lenses file containing 5 sections that shape how content and distill prompts approach the domain.

## Input

**Role:** {ROLE}
**Company:** {COMPANY}
**Domain:** {DOMAIN}

### Profile Content

{PROFILE_CONTENT}

## Output

Generate exactly 5 sections, each starting with its marker comment. Output ONLY the content below — no preamble, no explanations.

---

<!-- DOMAIN_LENS -->
<1-line description of what "domain depth" means: the specific mechanisms, patterns, and concerns that distinguish a Staff-level answer from a senior-level answer in this domain>

<!-- NITTY_GRITTY_LAYOUT -->
    1) **<Subsection relevant to domain>**
    2) **<Subsection relevant to domain>**
    3) **Threats & Failure Modes**
    4) **Operations / SLOs / Rollout**
    5) **Interviewer Probes (Staff-level)**
    6) **Implementation / Code Review / Tests**

<!-- DOMAIN_REQUIREMENTS -->
  - Include concrete <domain-specific technical details>.
  - Include concrete <domain-specific data/state handling>.
  - Include explicit threats and concrete failure modes (what breaks, how it breaks).
  - Include operational reality (logs/metrics/SLOs, paging triggers, canary/rollback, blast radius).
  - Include at least one policy/control detail (least privilege, approvals, auditability, retention).

<!-- DISTILL_REQUIREMENTS -->
  - 2 concrete <domain-specific technical details>
  - 2 <domain-specific data/state details>
  - 2 operational details (logs, metrics, SLOs, alerting, rollout/canary, failure modes)
  - 1 policy/control detail (least privilege, approvals, audit, compliance)
  - 1 explicit threat or failure mode

<!-- STAKEHOLDERS -->
<Comma-separated list of key stakeholders relevant to this domain, e.g.: Data, Product, Platform, Compliance>

## Rules

- The Nitty Gritty layout subsections 1-2 should be domain-specific (e.g., "Protocol / Wire Details" for security, "Pipeline Architecture / DAG Design" for data engineering). Subsections 3-6 are standard across domains.
- DOMAIN_LENS should capture what makes this domain technically deep at a Staff level — not generic software engineering, but the specific mechanisms and patterns.
- DOMAIN_REQUIREMENTS should list 5 concrete requirement categories that ensure generated content has real technical depth.
- DISTILL_REQUIREMENTS should list 8 items that a distilled document must include to be useful for interview prep.
- STAKEHOLDERS should list 3-5 organizational functions that interact with this domain.

## Quality Self-Checks (Run Silently Before Outputting)

- All 5 sections present with correct `<!-- MARKER -->` comments
- DOMAIN_LENS is one line, not generic
- NITTY_GRITTY_LAYOUT subsections 1-2 are domain-specific
- DOMAIN_REQUIREMENTS has 5 bullet points with concrete technical terms
- DISTILL_REQUIREMENTS has exactly 8 items
- STAKEHOLDERS is a comma-separated list
