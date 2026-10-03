// Runs once on first container start (docker-entrypoint-initdb.d).
// Creates least-privilege roles for the SecAudit results store. Passwords come from env vars.

const appDb = db.getSiblingDB("secaudit");

appDb.createRole({
  role: "secaudit_app",
  privileges: [
    {
      resource: { db: "secaudit", collection: "" },
      actions: ["find", "insert", "update", "createIndex", "listCollections"],
    },
  ],
  roles: [],
});

appDb.createUser({
  user: process.env.SECAUDIT_APP_USER || "secaudit_app",
  pwd: process.env.SECAUDIT_APP_PASSWORD,
  roles: [{ role: "secaudit_app", db: "secaudit" }],
  mechanisms: ["SCRAM-SHA-256"],
});

// Findings schema: reject documents that are missing the core fields or have an unknown severity.
appDb.createCollection("findings", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["id", "scan_id", "agent", "title", "severity", "target", "created_at"],
      properties: {
        severity: { enum: ["info", "low", "medium", "high", "critical"] },
        cwe: { bsonType: ["string", "null"], pattern: "^CWE-\\d+$" },
      },
    },
  },
  validationAction: "error",
});
appDb.createCollection("scans");
