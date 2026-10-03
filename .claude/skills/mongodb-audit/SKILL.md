---
name: mongodb-audit
description: Audit MongoDB deployments and application access - connection/TLS security, authentication and RBAC, network exposure, NoSQL injection, encryption, auditing, and cardholder-data (PCI DSS) partitioning. Use when testing MongoDB connections, database permissions or data segregation, or when extending DatabaseAuditorAgent / MongoManager.
---

# MongoDB Security Audit

All checks are **read-only**. Use the audit credential supplied with the `ScanScope`. It should
hold only `clusterMonitor` plus `read` on the target databases. Never run write commands against a target.

## 0. Confirm scope
- The cluster host and database names must be listed in the active `ScanScope`.
- Store the connection string as a secret reference, never inline. Redact it in every log line.

## 1. Network exposure (PCI DSS Req 1)
- `net.bindIp` is not `0.0.0.0` unless a firewall or security group restricts access.
- Port 27017 is not reachable from the internet. Check this from an out-of-network vantage point only if the scope allows it.
- Atlas: the IP access list has no `0.0.0.0/0`. Prefer private endpoints or VPC peering.

## 2. Transport security (PCI DSS Req 4)
```js
db.adminCommand({ getCmdLineOpts: 1 }).parsed.net.tls
```
- `tls.mode` must be `requireTLS`. `allowTLS` or `preferTLS` is a finding.
- Minimum TLS 1.2 (`net.tls.disabledProtocols: TLS1_0,TLS1_1`).
- On the client side, look for `tlsAllowInvalidCertificates=true` or `tlsInsecure=true`. Either is high severity.

## 3. Authentication (PCI DSS Req 8)
```js
db.adminCommand({ getCmdLineOpts: 1 }).parsed.security        // authorization: "enabled"
db.adminCommand({ getParameter: 1, authenticationMechanisms: 1 })
```
- `security.authorization: enabled` is required. Without it, the cluster is a critical finding.
- Mechanisms: SCRAM-SHA-256, x.509 or LDAP/OIDC. Flag SCRAM-SHA-1-only setups.
- Check for default or shared accounts and credentials in app repos (`mongodb://user:pass@`).

## 4. Authorization / RBAC (PCI DSS Req 7)
```js
db.getSiblingDB("admin").system.users.find({}, { user: 1, db: 1, roles: 1 })   // needs userAdmin; else usersInfo
db.adminCommand({ usersInfo: 1, showPrivileges: true })
db.adminCommand({ rolesInfo: 1, showPrivileges: true, showBuiltinRoles: false })
```
Flag:
- Application users holding `root`, `dbOwner`, `userAdminAnyDatabase`, `readWriteAnyDatabase` or `__system`.
- Any user able to `grantRole`, `createUser` or `dropDatabase` who is not a named admin.
- Users whose roles span both cardholder-data (CDE) databases and non-CDE databases.

## 5. Cardholder data partitioning (PCI DSS Req 3, 7)
Goal: confirm that primary account numbers (PANs) live only in designated CDE collections and are protected there.
1. List databases and collections. Map each one to `cde` or `non_cde` using the scope's data map.
2. **Sample** up to N documents per collection (default N=200, using `$sample`). Run a PAN detector:
   13–19 digit sequences that pass the **Luhn** check, plus BIN prefix heuristics.
   Report only a masked form (`411111******1111`). **Never persist a full PAN.**
3. Findings:
   - PAN in a `non_cde` collection: **critical** (scope creep).
   - PAN stored in clear text in a CDE collection without field-level encryption (CSFLE/Queryable
     Encryption) or tokenisation: **high**.
   - CVV/CVC or full track data stored anywhere: **critical** (PCI 3.3.1 prohibits storing it after authorisation).
4. Check that CDE collections have a `$jsonSchema` validator and that only CDE service roles can read them.

## 6. Encryption at rest & keys (PCI DSS Req 3.5–3.7)
- WiredTiger encryption (Enterprise or Atlas) is enabled, or volume encryption is documented.
- CSFLE / Queryable Encryption keys live in a KMS, not on local disk, and the key vault collection is access-restricted.

## 7. Auditing & logging (PCI DSS Req 10)
- `auditLog` is enabled (Enterprise or Atlas). At minimum it captures `authenticate`, `authCheck`
  failures and user or role changes.
- Logs are shipped off-host and retained for at least 12 months.
- `redactClientLogData` is enabled where possible.

## 8. Application-layer NoSQL injection (CWE-943)
In the app code that talks to Mongo:
- Filters built straight from request JSON (`collection.find(request.json)`): **high**.
- Operator injection: request values must be scalars after validation. Test payloads
  `{"$ne": null}`, `{"$gt": ""}`, `{"$regex": ".*"}` against login and search endpoints.
- `$where`, `$function`, `$accumulator`, or `mapReduce` with user input: **critical**.
  Recommend `security.javascriptEnabled: false`.

## 9. Configuration hygiene
- Version is supported (not EOL), and the replica set or backups are encrypted.
- `--enableLocalhostAuthBypass` is off after bootstrap. HTTP interface or REST is disabled.

## 10. Report
Map every finding to CWE **and** the PCI DSS v4.0 requirement. Include the exact read-only command
used as evidence (with redacted output) and a remediation config snippet.
