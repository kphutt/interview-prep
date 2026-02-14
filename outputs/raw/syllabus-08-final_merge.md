## How to use this syllabus
- For each episode, write a 1–2 page “deep doc”: **Hook → Mental Model → Nitty Gritty → Staff Pivot → Scenario**, plus your chosen success metrics.
- Record a 6–8 minute “podcast segment” version: practice delivering **crisp trade-offs** and rollout decisions out loud (latency/SLO, reliability, friction).
- Convert each episode’s **Staff Pivot** into 2 interview answers: (1) architecture decision under constraints, (2) stakeholder alignment + risk acceptance narrative.
- Turn every **Nitty Gritty** bullet into flashcards (protocol steps, headers/claims, cache keys, failure modes); drill until you can recall under pressure.
- Use each **Scenario Challenge** as a whiteboard loop: ask clarifying questions → propose 2+ designs → pick one → rollout plan + incident plan + rollback triggers.
- After Episodes **1–4 / 5–8 / 9–12**, listen to the paired **Frontier Digest** and update your “as-of Feb 2026” assumptions (interop, standards maturity, attacker shifts).
- Build a personal “trade-off library”: one sentence per episode answering **what you’d measure**, **what you’d accept**, and **what you won’t accept**.

---

## CISSP Coverage Map
| Episode # | Title | CISSP domains (tags) | Justification (≤18 words) |
|---:|---|---|---|
| 1 | The Binding Problem: mTLS vs DPoP for Sender‑Constrained OAuth Tokens | D5 IAM, D4 Comms, D3 Arch | Sender-constrained tokens (mTLS/DPoP) reduce replay after token theft across networks. |
| 2 | The Session Kill Switch: Event‑Driven Revocation with CAEP/RISC | D5 IAM, D7 Ops, D1 Risk | CAEP/RISC push events enable fast session kill without per-request introspection dependencies. |
| 3 | Mobile Identity: Defeating the Confused Deputy with Universal/App Links + PKCE | D5 IAM, D8 AppSec, D3 Arch | PKCE plus app-link verification prevents redirect hijack and app impersonation in mobile OAuth. |
| 4 | Auth at the Edge: Passkeys (WebAuthn) Rollout Without a Support Meltdown | D5 IAM, D3 Arch, D1 Risk | WebAuthn passkeys provide phishing resistance; rollout balances recovery, reliability, and support risk. |
| 5 | BeyondCorp: Building a Zero‑Trust Proxy (Identity‑Aware Access Without the VPN) | D4 Comms, D5 IAM, D3 Arch | Identity-aware proxy enforces context policy at L7, replacing VPN/IP perimeter assumptions. |
| 6 | ALTS in Practice: Workload Identity mTLS for Service‑to‑Service Zero Trust | D4 Comms, D5 IAM, D3 Arch | Workload identity mTLS secures east‑west traffic with mutual auth independent of topology. |
| 7 | The Cloud Metadata Attack: SSRF → Instance Credentials (Defense-in-Depth Guardrails) | D8 AppSec, D4 Comms, D3 Arch | IMDS hardening plus egress controls mitigate SSRF theft of cloud instance credentials. |
| 8 | Supply Chain Security: SLSA Provenance + Deploy‑Time Verification (Trust the Binary, Not the Builder) | D8 AppSec, D2 Assets, D3 Arch | SLSA provenance and deploy-time signature checks protect artifacts against compromised build pipelines. |
| 9 | Detection Engineering: Detections‑as‑Code That Don’t Page You to Death | D7 Ops, D6 Test | Tested detections-as-code improve signal-to-noise and operational resilience of security monitoring. |
| 10 | Crypto Agility (Post‑Quantum): Hybrid TLS + “Rotate the Math Without a Code Push” | D3 Arch, D4 Comms, D1 Risk | Hybrid TLS and agility reduce store-now-decrypt-later risk while managing interoperability constraints. |
| 11 | Envelope Encryption: Rotate Access to Petabytes by Re‑wrapping Keys, Not Data | D2 Assets, D3 Arch | Envelope encryption separates DEK/KEK so rotations rewrap keys, not reencrypt petabytes. |
| 12 | Insider Risk: JIT + Multi‑Party Authorization (MPA) Without Breaking On‑Call | D1 Risk, D5 IAM, D7 Ops | JIT plus multi-party approval reduces insider abuse while keeping break-glass auditable. |
| 13 | Frontier Digest A (Feb 2026): “PoP + Signals + Passkeys” — Where Sender‑Constraint, Revocation, Mobile OAuth, and WebAuthn Are Converging | D5 IAM, D3 Arch, D8 AppSec | Feb 2026 updates on PoP, Shared Signals revocation, mobile OAuth hardening, and passkey adoption. |
| 14 | Frontier Digest B (Feb 2026): “Platform Guardrails” — ZTNA Proxies, Workload Identity, SSRF Egress Controls, and SLSA Verification | D3 Arch, D4 Comms, D8 AppSec | Feb 2026 updates on platform guardrails: ZTNA, mesh identity, SSRF isolation, SLSA enforcement. |
| 15 | Frontier Digest C (Feb 2026): “Signals, PQC, Keys, and Two‑Person Control” — Evolving Detection, Crypto, Data Protection, and Privileged Access Without Blowing SLOs | D7 Ops, D3 Arch, D1 Risk | Feb 2026 trends on detections, PQC rollout, KMS-tolerant encryption, and privileged access controls. |

---

## Syllabus Index (LISTENING ORDER)
| Episode # | Title | Primary Focus | Primary CISSP domains (tags) | Primary Interview Axis (Domain / RRK / Mixed) | Key trade-off (≤10 words) |
|---:|---|---|---|---|---|
| 1 | The Binding Problem: mTLS vs DPoP for Sender‑Constrained OAuth Tokens | Prevent token theft & replay via sender‑constrained tokens | D5 IAM, D4 Comms | Domain | mTLS transparency vs DPoP device agility |
| 2 | The Session Kill Switch: Event‑Driven Revocation with CAEP/RISC | Event-driven revocation for immediate access termination | D5 IAM, D7 Ops | Mixed | Long sessions vs fast kill-time |
| 3 | Mobile Identity: Defeating the Confused Deputy with Universal/App Links + PKCE | Secure OAuth redirects by proving app identity | D5 IAM, D8 AppSec | Domain | Deep links UX vs redirect hijack risk |
| 4 | Auth at the Edge: Passkeys (WebAuthn) Rollout Without a Support Meltdown | Phishing-resistant auth and practical rollout strategy | D5 IAM, D3 Arch | Domain | Phishing resistance vs recovery/support friction |
| 13 | Frontier Digest A (Feb 2026): “PoP + Signals + Passkeys” — Where Sender‑Constraint, Revocation, Mobile OAuth, and WebAuthn Are Converging | Recent + near-future shifts for user auth and token binding | D5 IAM, D3 Arch | Mixed | Adopt now vs wait for ecosystem maturity |
| 5 | BeyondCorp: Building a Zero‑Trust Proxy (Identity‑Aware Access Without the VPN) | Replace VPN with identity-aware proxy + context policy | D4 Comms, D5 IAM | Mixed | Central policy vs app autonomy and latency |
| 6 | ALTS in Practice: Workload Identity mTLS for Service‑to‑Service Zero Trust | Service-to-service auth via workload identity | D4 Comms, D5 IAM | Domain | Strong identity vs handshake overhead/debugging |
| 7 | The Cloud Metadata Attack: SSRF → Instance Credentials (Defense-in-Depth Guardrails) | Stop SSRF from stealing cloud metadata credentials | D8 AppSec, D4 Comms | Mixed | Platform controls vs app fixes and flexibility |
| 8 | Supply Chain Security: SLSA Provenance + Deploy‑Time Verification (Trust the Binary, Not the Builder) | Trust binaries via provenance and deploy-time verification | D8 AppSec, D2 Assets | Mixed | Hermetic builds vs developer velocity |
| 14 | Frontier Digest B (Feb 2026): “Platform Guardrails” — ZTNA Proxies, Workload Identity, SSRF Egress Controls, and SLSA Verification | Updates for infra identity controls and software provenance | D3 Arch, D8 AppSec | Mixed | Standardize platform vs per-team customization |
| 9 | Detection Engineering: Detections‑as‑Code That Don’t Page You to Death | High-signal detections as code; reduce noise sustainably | D7 Ops, D6 Test | RRK | Coverage breadth vs alert quality |
| 10 | Crypto Agility (Post‑Quantum): Hybrid TLS + “Rotate the Math Without a Code Push” | Hybrid TLS + abstraction to rotate crypto without rewrites | D3 Arch, D4 Comms | Domain | Agility layers vs performance/interoperability |
| 11 | Envelope Encryption: Rotate Access to Petabytes by Re‑wrapping Keys, Not Data | Encrypt at scale; rotate access fast via DEK/KEK | D2 Assets, D3 Arch | Domain | Rotation speed vs key management complexity |
| 12 | Insider Risk: JIT + Multi‑Party Authorization (MPA) Without Breaking On‑Call | JIT + peer approval to limit admin abuse | D1 Risk, D5 IAM | RRK | Operational urgency vs governance controls |
| 15 | Frontier Digest C (Feb 2026): “Signals, PQC, Keys, and Two‑Person Control” — Evolving Detection, Crypto, Data Protection, and Privileged Access Without Blowing SLOs | Evolving threats + controls for ops, crypto, and privileged access | D7 Ops, D3 Arch | Mixed | Move fast vs evidence-driven rollout safety |