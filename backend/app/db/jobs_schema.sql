CREATE TABLE IF NOT EXISTS ingestion_jobs (
  document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL,
  file_path TEXT,
  file_hash TEXT,
  state TEXT NOT NULL DEFAULT 'queued' CHECK(state IN ('queued','active','completed','failed')),
  stage TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  chunk_count INTEGER NOT NULL DEFAULT 0,
  vector_count INTEGER NOT NULL DEFAULT 0,
  error_code TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS ingestion_jobs_pending ON ingestion_jobs(state,next_attempt_at);
CREATE TABLE IF NOT EXISTS ingestion_project_leases (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  token TEXT NOT NULL,
  expires_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS upload_cleanup (
  path TEXT PRIMARY KEY,
  organization_id TEXT NOT NULL,
  project_id TEXT NOT NULL,
  error_code TEXT,
  created_at INTEGER NOT NULL
);
