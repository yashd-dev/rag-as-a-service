CREATE TABLE IF NOT EXISTS document_sources (
  document_id TEXT PRIMARY KEY REFERENCES documents(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_key TEXT NOT NULL,
  source_record_id TEXT NOT NULL,
  current_generation TEXT,
  UNIQUE (organization_id, project_id, source_key, source_record_id)
);
CREATE TABLE IF NOT EXISTS index_generations (
  id TEXT PRIMARY KEY,
  document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  organization_id TEXT NOT NULL,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  source_text TEXT NOT NULL,
  source_metadata TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  chunker_version TEXT NOT NULL,
  recipe_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('pending','processing','text_ready','failed','graph_partial')),
  error_code TEXT,
  attempts INTEGER NOT NULL DEFAULT 0,
  lease_token TEXT,
  lease_until INTEGER NOT NULL DEFAULT 0,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS canonical_chunks (
  id TEXT PRIMARY KEY,
  generation_id TEXT NOT NULL REFERENCES index_generations(id) ON DELETE CASCADE,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  start_char INTEGER NOT NULL,
  end_char INTEGER NOT NULL,
  source_pages TEXT NOT NULL,
  UNIQUE (generation_id, chunk_index),
  CHECK (start_char >= 0 AND end_char > start_char)
);
CREATE INDEX IF NOT EXISTS index_generations_document_idx ON index_generations(document_id);
