# Episode Frames for NotebookLM

Paste the frame for each episode above the generic prompt. Listening order shown in brackets.

---

## Episode 1 [listen: 1st]
Format: Architecture debate
Central argument: Which binding do you enforce — infrastructure-layer (mTLS) or application-layer (DPoP) — and where does each one break?
Stakes: Stolen tokens get replayed across networks because bearer tokens are cash — possession is enough.

## Episode 2 [listen: 2nd]
Format: P0 incident postmortem
Central argument: A stolen refresh token is minting new access tokens right now. Your kill switch doesn't exist yet.
Stakes: The attacker holds a valid refresh token and keeps minting access for hours while you watch.

## Episode 3 [listen: 3rd]
Format: Failure autopsy
Central argument: A redirect hijack drained accounts because the app trusted a URL scheme instead of a platform binding.
Stakes: Users lose money because a malicious app intercepted their OAuth redirect on the same device.

## Episode 4 [listen: 4th]
Format: Migration war story
Central argument: You're rolling out passkeys to millions of users without creating a support avalanche or locking people out.
Stakes: Either phishing continues unchecked, or you lock out thousands of legitimate users with no recovery path.

## Episode 13 — Frontier A [listen: 5th]
Format: Design review
Central argument: Four identity standards landed this year. You need to decide which to enforce now and which to defer.
Stakes: You deploy passkeys but attackers just steal sessions instead — the stack has gaps you didn't close.

## Episode 5 [listen: 6th]
Format: Migration war story
Central argument: You're retiring VPN access for 80,000 employees in 9 months and replacing it with a proxy that becomes tier-0 infrastructure.
Stakes: Lateral movement through VPN-trusted networks continues, or your new proxy becomes a company-wide outage button.

## Episode 6 [listen: 7th]
Format: Architecture debate
Central argument: Your services trust the network. After a lateral movement incident, that assumption is dead — now pick how to replace it.
Stakes: A compromised pod pivots freely across 3,000 services because nothing checks identity at the RPC layer.

## Episode 7 [listen: 8th]
Format: P0 incident postmortem
Central argument: An SSRF bug just handed an attacker your cloud credentials through the metadata endpoint. You have minutes.
Stakes: Attacker escalates from a web input bug to full cloud account takeover in seconds.

## Episode 8 [listen: 9th]
Format: Failure autopsy
Central argument: A compromised CI runner signed and shipped a backdoored binary that passed every existing check.
Stakes: A malicious artifact is running in production and your scanning pipeline didn't catch it because it wasn't looking for integrity.

## Episode 14 — Frontier B [listen: 10th]
Format: Design review
Central argument: You're proposing platform-wide guardrails — ZTNA, workload identity, metadata isolation, and SLSA. Leadership wants the architecture review.
Stakes: Platform controls become a single point of failure that takes down everything, or you ship nothing and attackers chain SSRF to supply chain.

## Episode 9 [listen: 11th]
Format: P0 incident postmortem
Central argument: Your Kafka backlog just hit 30 minutes. Detections aren't firing. And there's an active exfiltration happening right now.
Stakes: Attackers exfiltrate data undetected because your detection pipeline dropped the evidence when it mattered most.

## Episode 10 [listen: 12th]
Format: Migration war story
Central argument: You're adding post-quantum key exchange to live TLS traffic without breaking legacy clients or blowing your latency budget.
Stakes: Long-lived sensitive data gets harvested now and decrypted when quantum computing arrives — and you can't roll back the exposure.

## Episode 11 [listen: 13th]
Format: Architecture debate
Central argument: One key for everything is a ticking bomb. But calling KMS on every read kills your latency. Design the hierarchy.
Stakes: A key compromise means re-encrypting petabytes of data under emergency pressure with no playbook.

## Episode 12 [listen: 14th]
Format: P0 incident postmortem
Central argument: An engineer's laptop was compromised. They have standing prod access. The approval service is partially down. Go.
Stakes: A compromised admin account has standing access to production and your control plane is degraded.

## Episode 15 — Frontier C [listen: 15th]
Format: Failure autopsy
Central argument: You had controls for detection, encryption, PQC, and privileged access. None of them held under real operational pressure.
Stakes: Your dashboard says "healthy" while you're actively being breached through silent downgrades and telemetry gaps.
