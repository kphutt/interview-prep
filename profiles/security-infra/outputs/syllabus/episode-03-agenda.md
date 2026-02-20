**Episode 3 — Mobile Identity: Defeating the Confused Deputy with Universal/App Links + PKCE**

2) **The Hook (The core problem/tension).**
- Mobile OAuth failures are rarely “bad crypto”—they’re “the OS launched the wrong app.”  
- Custom URL schemes make redirect capture and app impersonation surprisingly easy at scale.  
- You need to prove *app identity* (binary signature + domain binding) before you trust any OAuth redirect.

3) **The "Mental Model" (A simple analogy).**  
A uniform isn’t identity; a badge is. In mobile OAuth, the “uniform” is the redirect URI—any app can wear it. Universal/App Links are the OS checking the badge (app signature bound to a domain) before handing over the redirect.

4) **The "Common Trap" (Common junior mistake + why it fails at scale).**
- “Use `myapp://callback` and hide a `client_secret` in the app.” Secrets in apps are extractable, and URL schemes are hijackable—security-only thinking ignores platform realities.  
- “Use an embedded WebView for control.” It harms SSO, increases phishing surface, and breaks modern platform guidance.

5) **The "Nitty Gritty" (Headers, JSON keys, protocols, patterns, operational reality).**
- **OAuth for Native Apps BCP:** use Authorization Code flow in a **system browser** (ASWebAuthenticationSession / Chrome Custom Tabs), not an embedded WebView.  
- **PKCE (crypto detail):** generate `code_verifier` (43–128 chars), compute `code_challenge = BASE64URL(SHA256(code_verifier))`, send `code_challenge_method=S256`.  
- **Token exchange:** redeem with `grant_type=authorization_code`, `code`, `redirect_uri`, and `code_verifier`; no `client_secret` for public clients.  
- **Redirect URI strategy:** prefer **claimed HTTPS redirects** (e.g., `https://login.example.com/oauth/callback`) bound to the app via OS link verification; avoid new `myapp://` schemes.  
- **iOS Universal Links:** host `https://login.example.com/apple-app-site-association` (no redirects); includes `applinks.details[].appID` and `paths` allowlist patterns.  
- **Android App Links:** host `https://login.example.com/.well-known/assetlinks.json` with `package_name` and `sha256_cert_fingerprints` under `target`.  
- **State integrity (protocol detail):** generate and validate `state` for CSRF; for OIDC, generate and validate `nonce` in the ID Token.  
- **Data-plane caching gotcha:** OS caches association files; CDN misconfig (302 redirect, wrong `Content-Type`) can break app-link verification for hours until caches refresh.  
- **IdP registration hygiene:** register exact `redirect_uri` values; wildcard redirects are a confused-deputy footgun and are hard to audit.  
- **Operational observability:** instrument login funnel stages (browser opened → redirect received → `state` ok → PKCE exchange ok) and break down by OS/app version for rollback decisions.  
- **Policy/control:** require PKCE + app-link verification for privileged scopes; keep legacy scheme redirects behind a time-bounded allowlist with explicit owner.  
- **Explicit threat/failure mode:** with custom URL schemes, a malicious app can register the same scheme and intercept authorization codes (and confuse users about which app they’re authenticating).

6) **The "Staff Pivot" (Architectural trade-off argument).**
- Competing architectures:  
  - **A)** Custom scheme redirect + embedded WebView (fast to ship; easy to hijack; poor SSO).  
  - **B)** **System browser + PKCE + Universal/App Links** (best practice; requires domain association and careful ops).  
  - **C)** Add optional app/device attestation for high-risk actions (extra friction; harder cross-platform).  
- I choose **B as the default baseline**, then selectively add **C** only for highest-risk scopes (e.g., money movement) where friction is acceptable.  
- What I’d measure: **auth completion rate**, **redirect/association failure rate**, **support tickets by error class**, **incidents of redirect hijack/code interception**, and time-to-ship for new apps.  
- Risk acceptance: I’ll accept some setup friction (domain ownership, association files) to eliminate a class of ATOs; I won’t accept “secrets in apps” as a compensating control.  
- Stakeholder/influence: this crosses boundaries (Mobile, Web/domain owners, Identity/IdP, Support). Drive alignment via a “golden path” SDK + an automated validator that checks association files in CI.  
- Operational angle: treat association files like production config—own them, monitor them, and have a rollback plan when a CDN change breaks logins.

7) **A "Scenario Challenge" (Constraint-based problem).**
- You’re launching a fintech mobile app with OAuth sign-in; **p95 login must be <1.5s**, and overall service availability target is **99.99%**.  
- Security requirement: must prevent redirect hijack/app impersonation; assume attackers can install malicious apps on the same device.  
- Privacy/compliance: logs must be auditable for fraud, but must not store raw auth codes/tokens or unnecessary device identifiers.  
- Developer friction: multiple mobile teams and three branded apps share the same IdP; you need a standardized approach, not per-app hacks.  
- Reliability constraint: login must survive partial outages (IdP latency spikes, CDN issues) with graceful degradation and clear user messaging.  
- Migration/back-compat: legacy app versions already use `myapp://callback`; you cannot break them, but you must deprecate safely.  
- On-call twist: a CDN change starts 302-redirecting `apple-app-site-association`; iOS stops opening your app and users get stuck in the browser—how do you detect fast and mitigate?  
- Multi-team/leadership twist: web team owns `login.example.com`, mobile team owns the app, identity team owns redirect registration—drive a rollout plan, ownership model, and SLOs for link verification health.  


1) **The Title (Catchy and technical).**