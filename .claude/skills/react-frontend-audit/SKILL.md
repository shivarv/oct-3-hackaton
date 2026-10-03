---
name: react-frontend-audit
description: Audit ReactJS client-side code, build output and frontend scripts for security vulnerabilities (XSS, secret leakage, insecure storage, CSP gaps, vulnerable dependencies). Use when reviewing or scanning a React/Vite/Next.js frontend, or when extending FrontendScannerAgent.
---

# React Frontend Security Audit

Use this skill to review a React codebase or its built bundle. Record each issue as a `Finding`
(see `backend/src/secaudit/models/finding.py`) with a CWE id, severity, file:line and remediation.

## 0. Confirm scope
- Check that the repo or URL is listed in the active `ScanScope`. If it is not, stop.
- Record the commit SHA or bundle hash so the results can be reproduced.

## 1. Inventory
- Identify the framework and build tool (`package.json`, `vite.config.*`, `next.config.*`).
- List every entry point, route and place where external data enters the app:
  URL params, `location.hash`, `postMessage`, `localStorage`, API responses and WebSocket messages.

## 2. Dependency risk (CWE-1104)
```bash
npm audit --json --omit=dev
npx --yes osv-scanner --lockfile=package-lock.json
```
- Flag known-vulnerable packages, abandoned packages and suspicious `postinstall` scripts.
- Look for typosquats: names one edit away from popular packages.

## 3. DOM XSS sinks (CWE-79)
Grep for each sink, then trace whether attacker-controlled data reaches it:
```bash
rg -n "dangerouslySetInnerHTML|innerHTML|outerHTML|insertAdjacentHTML|document\.write" src
rg -n "eval\(|new Function\(|setTimeout\(\s*['\"\`]|setInterval\(\s*['\"\`]" src
rg -n "href=\{|src=\{|window\.location\s*=|location\.href\s*=" src
```
- Treat `href={userValue}` as a sink for `javascript:` URLs. A fix must check that the protocol is `http:` or `https:`.
- If HTML is rendered, confirm it is sanitised (DOMPurify) right before the sink.
- Check markdown renderers (`react-markdown` with `rehype-raw`, or `marked`) for unsafe settings.

## 4. Secrets & sensitive data in the client (CWE-200, CWE-798)
```bash
rg -n "(api[_-]?key|secret|token|password|private[_-]?key)\s*[:=]" src
rg -n "VITE_|REACT_APP_|NEXT_PUBLIC_" src .env* 2>/dev/null
npx --yes gitleaks detect --no-banner --source .
```
- Every `VITE_*`, `REACT_APP_*` or `NEXT_PUBLIC_*` value ships to the browser. None of them may hold a secret.
- Check built `dist/`, `build/` or `.next/static` output for source maps (`*.map`) in production, plus any embedded keys.

## 5. Auth tokens & storage (CWE-922)
- Search for `localStorage.setItem` and `sessionStorage.setItem` storing JWTs or refresh tokens.
  Prefer `HttpOnly; Secure; SameSite` cookies.
- Confirm route guards are UX only. Every protected action must also be enforced server-side
  (pass this to `python-backend-audit`).
- Check that logout clears client state and revokes tokens on the server.

## 6. Cross-origin & messaging (CWE-346)
- In `window.addEventListener('message', ...)`, check `event.origin` against an allowlist.
- `postMessage(data, '*')` with sensitive data is a finding.
- Check that `target="_blank"` links have `rel="noopener noreferrer"`. React adds this by default, but it can be overridden.

## 7. Security headers / CSP (CWE-1021, CWE-693)
Fetch the deployed app (only if it is in scope) and check:
- `Content-Security-Policy` must not contain `unsafe-inline` or `unsafe-eval` in `script-src`, and should set `frame-ancestors`.
- `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`.
- External `<script>` tags should use Subresource Integrity.

## 8. Client-side logic flaws
- Prices, roles or feature flags trusted from client state.
- Hidden admin routes that are only "protected" by not appearing in the nav.
- Overly verbose error boundaries that leak stack traces or API internals.

## 9. Report
- Remove duplicate findings. Assign severity using CVSS 3.1 base metrics.
- Each finding needs: title, CWE, severity, `file:line`, a redacted evidence snippet,
  reproduction steps and a concrete fix (code diff when possible).
- Summarise: totals by severity, top 3 risks and quick wins.
