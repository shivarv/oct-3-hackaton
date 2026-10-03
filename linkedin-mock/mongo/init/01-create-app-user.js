// Runs once, on first start of an empty data volume.
// Creates a least-privilege user for the backend: readWrite on the app database only.
const dbName = process.env.MONGO_DB || "linkedin_mock";

db.getSiblingDB(dbName).createUser({
  user: process.env.MONGO_APP_USER,
  pwd: process.env.MONGO_APP_PASSWORD,
  roles: [{ role: "readWrite", db: dbName }],
});
