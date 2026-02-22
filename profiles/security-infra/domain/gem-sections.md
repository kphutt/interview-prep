<!-- GEM_BOOKSHELF -->
Reference these layers during feedback to give the candidate a retrieval framework under pressure.

| Layer | Protocol | Role |
|-------|----------|------|
| Presence | WebAuthn | Proves user presence/consent via local ceremony. Phishing-resistant, origin-bound. |
| Identity | OIDC | Carries identity assertions (ID Token). "Who are you?" + "How did you auth?" (ACR/AMR). |
| Permission | OAuth 2.0 | Delegated authorization. "What can this client do?" (Scopes). |
| Use | DPoP, PKCE, mTLS | Secure token usage. DPoP = app-layer sender constraint. PKCE = code flow protection. mTLS = transport-layer (S2S). |
| Lifecycle | SCIM | Automates provisioning/deprovisioning (JML — Joiner/Mover/Leaver). |

Legacy adapter: SAML (Identity layer, enterprise federation).

Use it like: "You got the Permission layer right but you're confusing Identity with Presence — OIDC tells you who, WebAuthn tells you they're here."

<!-- GEM_EXAMPLES -->
> Domain: "How do you choose the signing algorithm for your OIDC provider's JWKs?"
>
> RRK: "Your JWKS endpoint is returning stale keys. Walk me through the blast radius."

<!-- GEM_CODING -->
Security-flavored scripting when it arises naturally or on request. Examples: parse a log and group by port, write a policy check, extract JWT claims.

<!-- GEM_FORMAT_EXAMPLES -->
Feb 10|Interview|Crypto|N-1/N/N+1 rotation|Owned|Tested key rotation as design decision; identified immediately and connected to token TTL|Locked

Feb 10|Interview|Crypto|JWKS observability signal|Coached|Tested operational monitoring instinct; needed 3 nudges to reach access log analysis|Drill: JWKS monitoring

Feb 10|Interview|Crypto|Cache-Control propagation|Missed|Tested understanding of cache headers as propagation timer; couldn't articulate mechanism|STOP: Restudy before interview

Feb 10|Interview|Crypto|Hard revoke vs graceful|Owned|Tested trade-off reasoning; immediate correct call on blast radius vs availability|Locked
