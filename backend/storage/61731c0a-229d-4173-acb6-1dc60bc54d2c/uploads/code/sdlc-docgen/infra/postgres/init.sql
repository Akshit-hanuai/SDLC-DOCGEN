-- =============================================================================
-- SDLC Document Generation System - PostgreSQL schema (Phase 0 proposal)
-- -----------------------------------------------------------------------------
-- Applies at first boot via /docker-entrypoint-initdb.d.
-- Requires the pgvector extension (pgvector/pgvector:pg16 image provides it).
--
-- Conventions:
--   * JSONB columns hold structured data; every generated/edit action writes
--     a full JSON snapshot to document_versions so nothing depends on the
--     renderer being reproducible later.
--   * Requirement identity is (project_id, req_id). traceability_links uses
--     composite FKs back to requirements so links are scoped per project.
--   * The chunks.embedding vector dimension must match the configured
--     sentence-transformers model. Default below is 768 (bge-base-en-v1.5).
--     If you change EMBEDDING_DIM in the backend config, ALTER this column.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Users / roles
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username   TEXT NOT NULL UNIQUE,
    email      TEXT UNIQUE,
    full_name  TEXT,
    role       TEXT NOT NULL DEFAULT 'viewer',     -- author | reviewer | approver | admin
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Projects (workspace scope for documents, requirements and repos)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    description   TEXT,
    git_repo_path TEXT,                            -- bare repo URL/path under git server
    status        TEXT NOT NULL DEFAULT 'active',  -- active | archived
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Source inputs (MoM / SysRS / IRS / code dump) and parsed chunks
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS source_files (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    doc_type     TEXT NOT NULL,                    -- mom | sysrs | irs | code
    path         TEXT NOT NULL,                    -- canonical store path (content-addressed)
    content_hash TEXT NOT NULL,                    -- sha256, enables dedup + version pinning
    parsed_json  JSONB,                            -- Phase 1 structured extraction output
    uploaded_by  UUID REFERENCES users(id),
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_source_files_project   ON source_files (project_id);
CREATE INDEX IF NOT EXISTS ix_source_files_hash      ON source_files (content_hash);

-- ---------------------------------------------------------------------------
-- Requirements registry (canonical, per project)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS requirements (
    id             BIGSERIAL PRIMARY KEY,
    req_id         TEXT NOT NULL,                  -- e.g. REQ-0042 / SR-3.2.1
    project_id     UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source         TEXT NOT NULL,                  -- sysrs | irs | mom | code
    source_file    TEXT,                           -- file it was extracted from
    source_version TEXT,                           -- hash/tag of that file's version
    req_type       TEXT,                           -- functional | non_functional | interface | constraint
    text           TEXT NOT NULL,                  -- verbatim requirement statement
    metadata       JSONB,                          -- e.g. {severity, priority, status}
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, req_id)
);

CREATE INDEX IF NOT EXISTS ix_requirements_project   ON requirements (project_id);
CREATE INDEX IF NOT EXISTS ix_requirements_source    ON requirements (project_id, source);

-- ---------------------------------------------------------------------------
-- Traceability links (requirement <-> requirement, code, tests)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS traceability_links (
    id         BIGSERIAL PRIMARY KEY,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    from_req_id TEXT NOT NULL,
    to_req_id   TEXT NOT NULL,
    link_type   TEXT NOT NULL,                     -- derives | refines | satisfies | verifies | implements | traces_to
    source      TEXT NOT NULL DEFAULT 'manual',    -- manual | linker | llm
    confidence  REAL,                              -- 0..1, meaningful only for automated extraction
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, from_req_id, to_req_id, link_type),
    FOREIGN KEY (project_id, from_req_id) REFERENCES requirements (project_id, req_id),
    FOREIGN KEY (project_id, to_req_id)   REFERENCES requirements (project_id, req_id)
);

CREATE INDEX IF NOT EXISTS ix_trace_from ON traceability_links (project_id, from_req_id);
CREATE INDEX IF NOT EXISTS ix_trace_to   ON traceability_links (project_id, to_req_id);

-- ---------------------------------------------------------------------------
-- Documents and per-section version snapshots
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    doc_type        TEXT NOT NULL,                 -- SRS | SDD | ICD | STP | STR
    title           TEXT NOT NULL,
    template_name   TEXT NOT NULL,                 -- which YAML template schema
    status          TEXT NOT NULL DEFAULT 'draft', -- draft | in_review | changes_requested | approved
    current_version INT  NOT NULL DEFAULT 1,
    git_commit_sha  TEXT,                          -- HEAD commit of the auto-versioned doc repo
    created_by      UUID REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, doc_type)
);

CREATE INDEX IF NOT EXISTS ix_documents_project ON documents (project_id, doc_type);

CREATE TABLE IF NOT EXISTS document_versions (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id       UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version           INT  NOT NULL,
    content           JSONB NOT NULL,              -- {section_id: {field_id: value}, ...}
    rendered_docx_path TEXT,
    rendered_pdf_path TEXT,
    status            TEXT NOT NULL DEFAULT 'draft',
    git_commit_sha    TEXT,                        -- this version's commit
    source_versions   JSONB,                       -- {sysrs: "3.1", irs: "2.0", mom: "hash", code: "abc123"}
    model_metadata    JSONB,                       -- {model, prompt_version, params, elapsed_s}
    created_by        UUID REFERENCES users(id),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version)
);

CREATE INDEX IF NOT EXISTS ix_docversions_doc ON document_versions (document_id, version);

-- ---------------------------------------------------------------------------
-- Review workflow (per document version + section)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reviews (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version     INT  NOT NULL,
    section_id  TEXT NOT NULL,                     -- section id from template schema
    reviewer_id UUID NOT NULL REFERENCES users(id),
    decision    TEXT NOT NULL,                     -- approved | rejected
    comment     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (document_id, version) REFERENCES document_versions (document_id, version)
);

CREATE INDEX IF NOT EXISTS ix_reviews_doc ON reviews (document_id, version, section_id);

-- ---------------------------------------------------------------------------
-- Audit log (every action: generate, edit, comment, approve, import)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    project_id  UUID,
    user_id     UUID REFERENCES users(id),
    action      TEXT NOT NULL,                     -- generate | edit | comment | approve | reject | import | upload
    entity_type TEXT,                              -- document | document_version | requirement | source_file | review
    entity_id   TEXT,
    details     JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_audit_project ON audit_log (project_id, created_at);

-- ---------------------------------------------------------------------------
-- RAG chunk store (embedding column dimension must match EMBEDDING_DIM config)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id              BIGSERIAL PRIMARY KEY,
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_file_id  UUID REFERENCES source_files(id) ON DELETE SET NULL,
    source_doc_type TEXT,
    requirement_id  TEXT,                          -- req_id if chunk maps to a requirement
    chunk_index     INT,
    text            TEXT NOT NULL,
    metadata        JSONB,
    embedding       vector(768),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chunks_project      ON chunks (project_id);
CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw
    ON chunks USING hnsw (embedding vector_cosine_ops);

-- ---------------------------------------------------------------------------
-- Seed data for local development
-- ---------------------------------------------------------------------------
INSERT INTO users (username, full_name, role)
VALUES ('seed-admin', 'Seed Administrator', 'admin')
ON CONFLICT (username) DO NOTHING;

INSERT INTO projects (name, description, git_repo_path)
VALUES ('pilot-project-alpha', 'Phase 0 seed project for local development', '/repos/pilot-project-alpha.git')
ON CONFLICT DO NOTHING;

INSERT INTO requirements (req_id, project_id, source, source_file, req_type, text)
SELECT 'REQ-0001', p.id, 'sysrs', 'SysRS_v3.1.docx', 'functional',
       'The system shall acquire telemetry data from at least 3 sensor channels simultaneously.'
FROM projects p WHERE p.name = 'pilot-project-alpha'
ON CONFLICT (project_id, req_id) DO NOTHING;

INSERT INTO requirements (req_id, project_id, source, source_file, req_type, text)
SELECT 'REQ-0002', p.id, 'sysrs', 'SysRS_v3.1.docx', 'non_functional',
       'The system shall have a mean time between failures (MTBF) of not less than 2000 hours.'
FROM projects p WHERE p.name = 'pilot-project-alpha'
ON CONFLICT (project_id, req_id) DO NOTHING;

INSERT INTO traceability_links (project_id, from_req_id, to_req_id, link_type, source)
SELECT p.id, 'REQ-0001', 'REQ-0002', 'traces_to', 'seed'
FROM projects p WHERE p.name = 'pilot-project-alpha'
ON CONFLICT DO NOTHING;
