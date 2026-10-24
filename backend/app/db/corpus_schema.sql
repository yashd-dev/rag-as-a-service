CREATE TABLE IF NOT EXISTS shared_corpora (
  id TEXT PRIMARY KEY CHECK (id = 'legal'),
  project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS project_corpus_references (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  shared_corpus_id TEXT NOT NULL REFERENCES shared_corpora(id) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS shared_corpus_no_retarget
BEFORE UPDATE ON shared_corpora
BEGIN
  SELECT RAISE(ABORT, 'Shared corpus registration is immutable');
END;

CREATE TRIGGER IF NOT EXISTS shared_corpus_not_reference
BEFORE INSERT ON shared_corpora
WHEN EXISTS (SELECT 1 FROM project_corpus_references WHERE project_id = NEW.project_id)
BEGIN
  SELECT RAISE(ABORT, 'A shared corpus cannot reference another corpus');
END;

CREATE TRIGGER IF NOT EXISTS corpus_reference_new_project_only
BEFORE INSERT ON project_corpus_references
WHEN EXISTS (SELECT 1 FROM documents WHERE project_id = NEW.project_id)
  OR EXISTS (SELECT 1 FROM shared_corpora WHERE project_id = NEW.project_id)
BEGIN
  SELECT RAISE(ABORT, 'A reference cannot replace source data');
END;

CREATE TRIGGER IF NOT EXISTS corpus_reference_no_retarget
BEFORE UPDATE ON project_corpus_references
BEGIN
  SELECT RAISE(ABORT, 'Corpus references are immutable');
END;

CREATE TRIGGER IF NOT EXISTS corpus_reference_no_document_insert
BEFORE INSERT ON documents
WHEN EXISTS (SELECT 1 FROM project_corpus_references WHERE project_id = NEW.project_id)
BEGIN
  SELECT RAISE(ABORT, 'Cannot upload into a shared corpus reference');
END;

CREATE TRIGGER IF NOT EXISTS corpus_reference_no_document_move
BEFORE UPDATE OF project_id ON documents
WHEN EXISTS (SELECT 1 FROM project_corpus_references WHERE project_id = NEW.project_id)
BEGIN
  SELECT RAISE(ABORT, 'Cannot move documents into a shared corpus reference');
END;
