CREATE TABLE IF NOT EXISTS platform_api_keys (
  id TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  name TEXT NOT NULL,
  prefix TEXT NOT NULL,
  secret_hash TEXT NOT NULL UNIQUE,
  created_at INTEGER NOT NULL,
  revoked_at INTEGER
);
CREATE TABLE IF NOT EXISTS platform_api_key_corpora (
  key_id TEXT NOT NULL REFERENCES platform_api_keys(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  PRIMARY KEY(key_id,project_id)
);
CREATE TABLE IF NOT EXISTS platform_api_usage (
  id TEXT PRIMARY KEY,
  key_id TEXT NOT NULL REFERENCES platform_api_keys(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  generation_config TEXT NOT NULL,
  requested_at INTEGER NOT NULL,
  lease_until INTEGER NOT NULL,
  finished_at INTEGER,
  status_code INTEGER,
  query_run_id TEXT,
  usage_json TEXT
);
CREATE INDEX IF NOT EXISTS platform_api_usage_key ON platform_api_usage(key_id,requested_at);
CREATE INDEX IF NOT EXISTS platform_api_usage_org ON platform_api_usage(organization_id,requested_at);
