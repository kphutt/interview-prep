**Episode 1 — Token Binding Basics**

2) **The Hook**
- Bearer tokens are vulnerable to replay once stolen.
- Sender-constrained tokens bind proof to the request.

3) **The Mental Model**
Cash (bearer) vs. credit card with PIN (sender-constrained).

4) **The Common Trap**
- "Rotate tokens faster." Fails to stop immediate replay.

5) **The Nitty Gritty**
- mTLS: client cert thumbprint in `cnf` claim.
- DPoP: per-request signed JWT proof with `htu`, `htm`, `ath`.

6) **The Staff Pivot**
- mTLS for server-to-server; DPoP for mobile/SPAs.

7) **Scenario Challenge**
- Migrate from bearer to sender-constrained tokens without breaking existing clients.
