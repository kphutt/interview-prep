## How to use this syllabus
- For each episode, write a 1–2 page “deep doc”: **Hook → Mental Model → Nitty Gritty → Staff Pivot → Scenario**, plus your chosen metrics.
- Record a 6–8 minute “podcast segment” version: practice delivering crisp trade-offs out loud, not just knowing facts.
- Convert each episode’s **Staff Pivot** into 2 interview answers: (1) architecture decision under constraints, (2) stakeholder/risk acceptance narrative.
- Turn every **Nitty Gritty** bullet into flashcards (headers/claims/protocol steps/keys); drill until you can recall details under pressure.
- Use each **Scenario Challenge** as a whiteboard loop: ask clarifying questions, propose 2+ designs, pick one, then outline rollout + incident plan.
- After Episodes **1–4 / 5–8 / 9–12**, listen to the paired **Frontier Digest** and update your “as-of Feb 2026” assumptions.
- Build a personal “trade-off library”: one sentence per episode answering **what you’d measure** and **what risk you’d accept**.

---

## CISSP Coverage Map
| Episode # | Title | CISSP domains (tags) | Justification (≤18 words) |
|---:|---|---|---|
| 1 | The Binding Problem (mTLS vs DPoP) | D5 IAM, D4 Comms, D3 Arch | Sender-constrained tokens (mTLS/DPoP) reduce replay and credential theft across networks. |
| 2 | The Session Kill Switch (Revocation) | D5 IAM, D7 Ops, D1 Risk | CAEP/RISC push revocation events; services invalidate sessions quickly during compromise. |
| 3 | Mobile Identity (The Confused Deputy) | D5 IAM, D8 AppSec, D3 Arch | Universal links + PKCE bind OAuth codes to apps, stopping redirect hijacks. |
| 4 | Auth at the Edge (Passkeys) | D5 IAM, D3 Arch, D1 Risk | WebAuthn passkeys provide origin-bound phishing resistance; rollout choices balance recovery and support. |
| 5 | BeyondCorp (Zero Trust Proxy) | D4 Comms, D5 IAM, D3 Arch | Identity-aware proxy enforces contextual policy at Layer 7, replacing VPN perimeter assumptions. |
| 6 | ALTS (Service Identity) | D4 Comms, D5 IAM, D3 Arch | Mutual auth with workload identity tickets secures east-west traffic beyond IP topology. |
| 7 | The Cloud Metadata Attack (SSRF) | D8 AppSec, D4 Comms, D3 Arch | IMDSv2 tokens + egress filtering mitigate SSRF theft of cloud instance credentials. |
| 8 | Supply Chain (SLSA) | D8 AppSec, D2 Assets, D3 Arch | SLSA provenance and deploy-time signature verification protect build artifacts from tampering. |
| 9 | Detection Engineering | D7 Ops, D6 Test | Detection engineering uses tested telemetry rules to improve signal-to-noise in operations. |
| 10 | Crypto Agility (Post-Quantum) | D3 Arch, D4 Comms, D1 Risk | Hybrid TLS (X25519+ML-KEM) and crypto agility reduce post-quantum migration risk. |
| 11 | Data Protection (Envelope Encryption) | D2 Assets, D3 Arch | Envelope encryption separates DEK/KEK so rotations rewrap keys, not petabytes of data. |
| 12 | Insider Risk (Multi-Party Auth) | D1 Risk, D5 IAM, D7 Ops | JIT + multi-party authorization reduces insider abuse; break-glass pathways stay auditable. |
| 13 | Frontier Digest A (E1–4): Binding, Revocation, Mobile OAuth, Passkeys (Feb 2026) | D5 IAM, D3 Arch, D8 AppSec | Feb 2026 updates on binding, revocation, mobile OAuth, and passkeys standardization. |
| 14 | Frontier Digest B (E5–8): Zero Trust, Workload Identity, SSRF, Supply Chain (Feb 2026) | D3 Arch, D4 Comms, D8 AppSec | Feb 2026 updates on zero trust, workload identity, SSRF defenses, and SLSA adoption. |
| 15 | Frontier Digest C (E9–12): Detection, PQC, Encryption, Insider Risk (Feb 2026) | D7 Ops, D3 Arch, D1 Risk | Feb 2026 updates on detection trends, PQC deployment, key management, and insider controls. |

---

## Syllabus Index (LISTENING ORDER)
| Episode # | Title | Primary Focus | Primary CISSP domains (tags) | Primary Interview Axis (Domain / RRK / Mixed) | Key trade-off (≤10 words) |
|---:|---|---|---|---|---|
| 1 | The Binding Problem (mTLS vs DPoP) | Prevent token theft & replay via sender-constrained tokens | D5 IAM, D4 Comms | Domain | mTLS transparency vs DPoP device agility |
| 2 | The Session Kill Switch (Revocation) | Event-driven revocation for immediate access termination | D5 IAM, D7 Ops | Mixed | Long sessions vs fast kill-time |
| 3 | Mobile Identity (The Confused Deputy) | Secure OAuth redirects by proving app identity | D5 IAM, D8 AppSec | Domain | Deep links UX vs redirect hijack risk |
| 4 | Auth at the Edge (Passkeys) | Phishing-resistant auth and practical rollout strategy | D5 IAM, D3 Arch | Domain | Phishing resistance vs recovery and support friction |
| 13 | Frontier Digest A (E1–4): Binding, Revocation, Mobile OAuth, Passkeys (Feb 2026) | Recent + near-future shifts for user auth and token binding | D5 IAM, D3 Arch | Mixed | Adopt now vs wait for ecosystem maturity |
| 5 | BeyondCorp (Zero Trust Proxy) | Replace VPN with identity-aware proxy + context policy | D4 Comms, D5 IAM | Mixed | Central policy vs app autonomy and latency |
| 6 | ALTS (Service Identity) | Service-to-service auth via workload identity | D4 Comms, D5 IAM | Domain | Strong identity vs handshake overhead and debugging |
| 7 | The Cloud Metadata Attack (SSRF) | Stop SSRF from stealing cloud metadata credentials | D8 AppSec, D4 Comms | Mixed | Platform controls vs app fixes and flexibility |
| 8 | Supply Chain (SLSA) | Trust binaries via provenance and deploy-time verification | D8 AppSec, D2 Assets | Mixed | Hermetic builds vs developer velocity |
| 14 | Frontier Digest B (E5–8): Zero Trust, Workload Identity, SSRF, Supply Chain (Feb 2026) | Updates for infra identity controls and software provenance | D3 Arch, D8 AppSec | Mixed | Standardize platform vs per-team customization |
| 9 | Detection Engineering | High-signal detections as code; reduce noise sustainably | D7 Ops, D6 Test | RRK | Coverage breadth vs alert quality |
| 10 | Crypto Agility (Post-Quantum) | Hybrid TLS + abstraction to rotate crypto without rewrites | D3 Arch, D4 Comms | Domain | Agility layers vs performance and interoperability |
| 11 | Data Protection (Envelope Encryption) | Encrypt at scale; rotate access fast via DEK/KEK | D2 Assets, D3 Arch | Domain | Rotation speed vs key management complexity |
| 12 | Insider Risk (Multi-Party Auth) | JIT + peer approval to limit admin abuse | D1 Risk, D5 IAM | RRK | Operational urgency vs governance controls |
| 15 | Frontier Digest C (E9–12): Detection, PQC, Encryption, Insider Risk (Feb 2026) | Evolving threats + controls for ops, crypto, and privileged access | D7 Ops, D3 Arch | Mixed | Move fast vs evidence-driven rollout safety |