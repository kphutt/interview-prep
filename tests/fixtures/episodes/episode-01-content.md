## Title
**Token Binding Basics**

## Hook
- Bearer JWTs are replayable once copied from logs or headers.
- Sender-constrained tokens (mTLS, DPoP) bind proof to each request.
- The challenge is rolling out binding without breaking existing clients.

## Mental Model
Bearer tokens are cash: possession is enough. Sender-constrained tokens are a card with PIN: the token alone is insufficient without cryptographic proof from the holder.

- Cash = bearer JWT: leaked tokens are immediately usable.
- Card + PIN = token + binding proof (cert thumbprint or signed JWT).

## Common Trap
- "Shorten token TTL to 5 minutes" — replay still works immediately; increases IdP load.
- "Mandate mTLS for all clients" — public clients can't manage X.509 certs.

## Nitty Gritty
- mTLS (RFC 8705): client presents X.509 cert; token `cnf` has `x5t#S256` thumbprint.
- DPoP (RFC 9449): `DPoP` header contains JWT with `htu`, `htm`, `ath` claims.
- Replay defense: cache `(jwk_thumbprint, jti)` pairs for proof lifetime.
- Nonce liveness: server returns `DPoP-Nonce` — adds RTT but proves freshness.

## Staff Pivot
- mTLS for controlled server-to-server traffic (invisible to app devs).
- DPoP for mobile/SPA clients (avoids cert management nightmare).
- Measure: binding mismatch rate, nonce retry rate, handshake failure rate.

## Scenario Challenge
- Migrate 200 services from bearer to sender-constrained tokens.
- Constraint: 99.95% availability SLO, no client-side cert infrastructure.
- Twist: a partner integration terminates TLS at their edge, stripping client certs.
