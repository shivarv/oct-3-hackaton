---
name: python-backend-audit
description: Security-test a Python backend (FastAPI/Flask/Django) - authentication, authorization (BOLA/IDOR), injection, deserialisation, SSRF, secrets and dependency risk. Use when auditing Python API code or endpoints, or when extending AuthValidatorAgent.
---

# Python Backend Security Audit

Combine static review with careful dynamic testing of in-scope endpoints only. Record each issue
as a `Finding` with a CWE id, severity, location and remediation.

## 0. Confirm scope & safety
- The target base URL or repo must be listed in the active `ScanScope`.
- Dynamic tests must be **non-destructive**: no DELETE/PUT on real data, rate-limited
  (at most 5 req/s by default), and run only against test accounts supplied with the scope.

## 1. Inventory
- Framework and version, ASGI/WSGI server, entry points.
- Get the route map. For FastAPI, fetch `/openapi.json` or walk `app.routes`. For Flask, use `app.url_map`.
  For Django, use `show_urls` or `urls.py`.
- For each route, note: method, path, auth dependency, input models and the data it touches.

## 2. Automated static analysis
```bash
uv run bandit -r src -f json -o reports/bandit.json
uv run semgrep --config p/python --config p/owasp-top-ten --json -o reports/semgrep.json src
uv run pip-audit -f json -o reports/pip-audit.json
npx --yes gitleaks detect --no-banner --source .
```
Review every high or medium result by hand. Mark false positives with the reason.

## 3. Authentication (CWE-287, CWE-345)
- JWT: algorithm pinned (reject `none` and alg confusion between HS256 and RS256), `exp`, `nbf`, `iss` and `aud`
  validated, and the secret has enough entropy and comes from the environment.
- Passwords are hashed with argon2id or bcrypt. Plain or unsalted SHA hashes are a critical finding.
- Login and reset endpoints are rate-limited and lock out after repeated failures. Reset tokens are single-use and short-lived.
- Sessions or refresh tokens rotate on use and are revoked on logout.

## 4. Authorization (CWE-285, CWE-639, OWASP API1/API5)
For every route that takes an object id:
- Test with token A against a resource owned by user B. Expect 403 or 404 (BOLA/IDOR).
- Test with a low-privilege token against admin routes. Expect 403 (BFLA).
- Test with no token, an expired token and a token with a bad signature. Expect 401.
- Check for mass assignment: Pydantic input models must not accept `role`, `is_admin`, `owner_id`.
Build a matrix of route × role × expected status code and diff it against the actual results.

## 5. Injection (CWE-89, CWE-943, CWE-78, CWE-94)
```bash
rg -n "execute\(.*(%|\.format\(|f['\"])" src            # SQL string building
rg -n "subprocess|os\.system|os\.popen|shell=True" src
rg -n "\beval\(|\bexec\(|compile\(" src
rg -n "\\\$where|\\\$function|\\\$accumulator" src       # Mongo server-side JS
rg -n "find\(.*request|find_one\(.*request" src           # raw request into Mongo filter
```
- For NoSQL injection, request bodies such as `{"password": {"$ne": null}}` must be rejected by schema validation.
  The `mongodb-audit` skill covers this in depth.

## 6. Deserialisation & parsing (CWE-502, CWE-611)
- `pickle.loads`, `yaml.load` without `SafeLoader`, `jsonpickle`, `marshal` on untrusted data.
- XML parsing without `defusedxml`.
- File uploads: size limits, content-type checks, path traversal (`../`) in filenames (CWE-22).

## 7. SSRF & outbound requests (CWE-918)
- Any URL fetched from user input must use an allowlist and block private, link-local and
  metadata IPs (`169.254.169.254`). Check that redirects are re-validated.

## 8. Configuration
- `DEBUG`/`reload` is off in production. Error responses do not leak stack traces.
- CORS: no `allow_origins=["*"]` together with `allow_credentials=True`.
- Security headers are set. TLS is enforced. Secrets are never logged (grep logging calls for token or password).

## 9. Report
Same format as the other skills: CWE, CVSS severity, `file:line` or endpoint, redacted evidence,
reproduction steps (curl), remediation, plus a summary of the auth matrix results.
