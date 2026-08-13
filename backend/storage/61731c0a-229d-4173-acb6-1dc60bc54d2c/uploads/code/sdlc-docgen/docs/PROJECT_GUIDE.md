# SDLC DocGen — Project Guide

This guide explains what the project is for, how it is structured, and how it
works end-to-end. It is the companion to `README.md` (quick start) and
`docs/architecture.md` (design decisions); this document is the detailed
walkthrough of every component.

---

## 1. Purpose

SDLC DocGen automatically generates SDLC documents for an **on-prem / air-gapped
defence R&D environment**. It produces five document types from engineering
inputs that already exist in the organisation:

| Doc type | Name                              | Primary inputs                                  |
| -------- | --------------------------------- | ----------------------------------------------- |
| SRS      | Software Requirements Specification | System Requirement Spec (SysRS), IRS, MoM       |
| SDD      | Software Design Description        | SRS + codebase (tree-sitter analysis)           |
| ICD      | Interface Control Document         | IRS, SysRS, codebase                            |
| STP      | Software Test Plan                 | SRS/SDD testable units (derived deterministically) |
| STR      | Software Test Report               | STP + MoM test outcomes                         |

**Non-negotiable constraints** (from `docs/architecture.md`):

1. **Air-gapped** — no external API calls. The backend only talks to endpoints
   listed in `backend/app/config.py` (`LLM_BASE_URL`, `EMBEDDING_MODEL`). LLM
   inference, embeddings, vector search, storage and git all run in the local
   network.
2. **Grounded generation** — requirements and traceability sections are filled
   from the database registry, not free text. The compliance checker rejects
   text that references a requirement id absent from the registry.
3. **Full audit** — every generate/edit stores a complete JSON snapshot in
   `document_versions`, a git commit, and an `audit_log` row carrying
   who/when/which source versions.
4. **Template-driven, not hardcoded** — all layout/field rules live in YAML
   schemas in `backend/app/templates/`. Adding a new doc type = adding a YAML
   file.
5. **Review is first-class** — `reviews` is per (document, version, section);
   reject-with-comment regenerates only that section.

---

## 2. System overview

```
MoM / SysRS / IRS / codebase (.zip)
        |
        v   Phase 1 - INGEST
[ parse & extract ]      parsers.py  (python-docx, pdfplumber/PyMuPDF, text)
                         requirements_extractor.py  (regex req-id registry)
                         mom_extractor.py           (decisions/actions/changes)
                         code_analyzer.py           (tree-sitter + .proto)
                         linker.py                  (traceability links)
        |
        v
[ requirement registry + traceability_links ]   (Postgres, JSONB)
        |
        v   Phase 2 - RAG + GENERATION
[ chunk + embed ]        chunker.py (800 chars / 80 overlap) + embeddings.py
        -> pgvector (cosine distance)
[ section-wise LLM generation ]   generator.py + llm/client.py
        -> structured JSON (primary contract)
        |
        v
[ compliance checker ]   compliance.py (every req id grounded, sections present)
        |
        v
[ template renderer ]    renderer.py -> DOCX (python-docx)
        |
        v   Phase 3 - VERSION CONTROL + AUDIT
[ git auto-commit ]      git_service.py (bare repo + work tree, GitPython)
[ audit_log + version diff ]
        |
        v   Phase 4 - REVIEW
[ submit -> review section -> regenerate section -> approve + git tag ]
        |
        v   Phase 5 - per-doc-type strategies (SDD/ICD/STP/STR)
        v   Phase 6 - web UI (React/Vite, frontend/)
        v   Phase 7 - evaluation harness (eval/evaluator.py)
```

The full repository layout is:

```
sdlc-docgen/
├── backend/                 FastAPI application (Python)
│   ├── app/
│   │   ├── main.py          create_app(): CORS + routers under /api/v1
│   │   ├── config.py        pydantic-settings, all environment knobs
│   │   ├── database.py      async SQLAlchemy engine / session
│   │   ├── models/          SQLAlchemy ORM models
│   │   ├── schemas/         Pydantic schemas (template, project)
│   │   ├── api/routes/      FastAPI routers (9 routers)
│   │   ├── services/        all business logic (ingest, rag, generate, eval…)
│   │   └── templates/       YAML doc-type schemas (srs/sdd/icd/stp/str)
│   ├── tests/               pytest (health, template loader)
│   ├── Dockerfile, requirements*.txt, pyproject.toml
├── frontend/                React 18 + Vite 6 SPA
│   └── src/                 api.ts, types.ts, components/ (6 tabs/pages)
├── infra/                   docker-compose, postgres init.sql, git server
├── scripts/                 demo.py (end-to-end demo), gen_fixtures.py
├── sample_data/
│   ├── fixtures/            SysRS_v3.1.docx, IRS_v2.0.docx, MoM_DesignReview04.docx
│   └── telemetry_acq/       reference codebase (py + proto)
└── Makefile                 docker/native targets
```

---

## 3. Backend — entrypoint, config, database

### `app/main.py`
Builds the FastAPI app, adds CORS (origins from `CORS_ORIGINS`), and mounts
nine routers under `API_PREFIX = /api/v1`:
`health`, `templates`, `projects`, `uploads`, `requirements`, `documents`,
`review`, `eval`, `audit`.

### `app/config.py`
Single source of truth (`pydantic-settings`, overridable by env vars). Key
settings:

| Env var               | Default                                    | Meaning                              |
| --------------------- | ------------------------------------------ | ------------------------------------ |
| `DATABASE_URL`        | `postgresql+asyncpg://docgen:docgen@localhost:5432/docgen` | Postgres+pgvector |
| `LLM_MODE`            | `auto`                                     | `vllm` \| `mock` \| `auto` (probe then fall back) |
| `LLM_BASE_URL`        | `http://localhost:8001/v1`                 | OpenAI-compatible vLLM/TGI endpoint  |
| `LLM_API_KEY`         | `EMPTY`                                    |                                   |
| `LLM_MODEL`           | `Qwen/Qwen2.5-7B-Instruct`                 | model name sent to the vLLM server  |
| `LLM_TIMEOUT_S` / `LLM_PROBE_S` | 120.0 / 3.0                     |                                   |
| `LLM_EXTRACTION_ENABLED` | `true`                                   | ask Qwen to extract rich details during ingestion |
| `LLM_EXTRACTION_MAX_CHARS` | `20000`                                | document-text cap for the extraction prompt |
| `EMBEDDING_MODEL`     | `BAAI/bge-base-en-v1.5`                    | SentenceTransformer model            |
| `EMBEDDING_DIM`       | 768                                        | pgvector dimension (must match schema) |
| `RETRIEVER_TOP_K`     | 8                                          | RAG hits per prompt                  |
| `GIT_REPOS_ROOT`      | `/repos`                                   | bare repos directory                 |
| `GIT_WORK_ROOT`       | `/tmp/docgen-work`                         | checkout work trees                  |
| `STORAGE_ROOT`        | `storage`                                  | uploads + rendered artifacts         |
| `REQ_ID_PATTERN`      | `(?:REQ-|SR-|IR-|TR-\d+/)?\b(?:REQ|SR|IR)-\d{3,4}(\.\d+)*\b` | requirement-id regex |
| `CORS_ORIGINS`        | `http://localhost:5173,…`                  | comma-separated                      |

### `app/database.py`
`create_async_engine` (pool_pre_ping) → `SessionLocal` async session factory →
`get_db()` dependency for routes.

---

## 4. Data model (`app/models/`)

All rows below are SQLAlchemy models on `Base`.

- **`Project`** (`document.py`): id (UUID), name (unique), description, status,
  git_repo_path. One project = one demo/system.
- **`Document`** (`document.py`): `UNIQUE(project_id, doc_type)` — one live
  document per type per project; `current_version`, `status`
  (`draft|in_review|changes_requested|approved`), `git_commit_sha`.
- **`DocumentVersion`** (`document.py`): `UNIQUE(document_id, version)`; full
  JSON snapshot `content` (the primary output contract), `rendered_docx_path`,
  `source_versions` (JSONB: `{sysrs: hash12, ...}` of inputs used),
  `model_metadata` (JSONB: llm client, model, elapsed_s, prompt version),
  `git_commit_sha`. History lives here.
- **`SourceFile`** (`source.py`): ingested input; `doc_type`
  (`sysrs|irs|mom|code|doc`), `content_hash` (sha256), `parsed_json` (JSONB).
- **`Chunk`** (`source.py`): pgvector row; `embedding vector(768)`, `text`,
  `source_doc_type`, `requirement_id`, `extra` JSONB (heading, source_file,
  req_ids). Note: the filename lives in `extra["source_file"]`, not in a column.
- **`Requirement`** (`requirement.py`): `UNIQUE(project_id, req_id)`; `source`
  (`sysrs|irs|mom|code|stp`), `req_type`
  (`functional|non_functional|interface|constraint|code_artifact|test_case`),
  `text`, `extra` JSONB (context, priority, interface, module, procedure, …).
  This table is the **requirement registry**.
- **`TraceabilityLink`** (`requirement.py`): `(project_id, from_req_id,
  to_req_id, link_type)` with composite FKs into `requirements`; `link_type`
  (`refines|derives|traces_to|implements|verifies`), `source`
  (`linker|generator|manual`), `confidence`.
- **`Review`** (`review.py`): per (document, version, section_id) decision
  (`approved|rejected`) + comment + reviewer.
- **`AuditLog`** (`review.py`): `action`, `entity_type`, `entity_id`,
  `details` JSONB, `created_at` — append-only trail.
- **`User`** (`user.py`): username, role (`viewer|reviewer`). Reviewers are
  auto-created by username on first use.

In-process dataclasses (not DB rows) in `app/services/ingest/models.py`:
`Block` (heading/level/text), `ParsedDocument`, `RequirementExtract`,
`MoMRecord`, `CodeArtifact`, `CodeAnalysis`.

---

## 5. Templates (`app/templates/*.yaml` + `app/services/template_store.py`)

Each doc type is one YAML file validated by the Pydantic `TemplateSchema`
(`app/schemas/template.py`). The generator, renderer, compliance checker and
frontend editor read **only** these schemas — nothing about layout is hardcoded.

Top-level keys: `template_id` (must equal filename stem), `doc_type`
(SRS|SDD|ICD|STP|STR), `name`, `numbering` (section/requirement id formats),
`header.document_control` (field list for the title page), `sections`.

Section keys:
- `id`, `title` — rendered as "`<id> <title>`" heading.
- `type` — `free_text` (LLM+RAG) | `requirements` (from registry, no LLM) |
  `traceability_matrix` (from links).
- `required`, `annexure`, `description`, `instructions` (appended to the LLM
  prompt).
- `fields` — ordered sub-blocks; field types `free_text|text|date|enum|list|
  table|requirements|traceability_matrix`; `columns` for tables; `instructions`
  per field.
- `data_sources` — which ingested inputs feed the section (`mom|sysrs|irs|code|
  srs|sdd|stp`). If a section omits it, `generator.DOC_SOURCE_MAP` supplies a
  doc-type default.
- `requirement_filter.req_type` + `output.columns` — for `requirements`
  sections.

`template_store.validate_all()` checks duplicate section/field ids and schema
validity (used by `/api/v1/templates/validate`).

---

## 6. Ingestion (Phase 1)

### 6.1 Upload routing (`api/routes/uploads.py`)
`POST /projects/{id}/uploads` accepts multiple files. Doc type is detected from
filename: `*.zip` → code, `*mom*`/`*meeting*` → mom, `*sysrs*`/`*system
requirement*` → sysrs, `*irs*`/`*interface requirement*` → irs, else `doc`.
`pipeline.extract_upload` stores raw files or unzips codebase zips.

### 6.2 Parsers (`services/ingest/parsers.py`)
`parse_file` dispatches by suffix:
- `.docx/.doc` → python-docx; headings from paragraph style, table rows joined
  with ` | `.
- `.pdf` → pdfplumber, fallback PyMuPDF; `_looks_like_heading` heuristic
  (heading markdown, ALL-CAPS, or `N.M Title`).
- else text; markdown `#`-headings or ALL-CAPS lines become heading levels.

Every parser collapses content into `Block(heading, level, text)` and a single
`ParsedDocument.text`.

### 6.3 Requirement extraction (`requirements_extractor.py`)
`find_req_ids` finds all matches of `REQ_ID_PATTERN` (from config). For each id,
`extract_requirements` captures the following sentence (~400 chars) as `text`,
the surrounding ±120/200 chars as `context`, and classifies via keyword hints
(performance/reliability/security/maintainab/mtbf → `non_functional`, interface
→ `interface`, constraint → `constraint`, else `functional`).

### 6.4 MoM extraction (`mom_extractor.py`)
`extract_mom` walks lines and classifies records by regex:
- **action items** (`Action item:`, `Owner:`, …) with `owner`/`due` extracted;
- **decisions** (`Decision:`, `decided that`, …);
- **requirement changes** (`Requirement change:`, `modified to`, …).

Each record keeps the requirement ids found on its line/bullet.

### 6.5 Code analysis (`code_analyzer.py`)
tree-sitter grammars for `.py/.ts/.tsx/.js/.java` + regex parser for `.proto`.
`analyze_code` produces a `CodeAnalysis` per file:
- functions and classes → `CodeArtifact(id=C-{module}.{name})`, docstring as
  description, any `REQ-`/`SR-` ids found in the node as `req_ids`;
- decorated routes (`@app.`/`@router.`/`@bp.` get/post/...) → `endpoints`;
- proto `message` blocks → `messages`; imports → dependencies.

> Note: tree-sitter 0.23 returns PyCapsule for grammars — the `_LANG_EXT`
> loaders wrap them in `Language(...)`, and `_analyze_text` builds
> `Parser(language_obj)` without re-wrapping.

### 6.6 Linker (`linker.py`)
- `link_extracts(extracts)` — for every extracted requirement, cross-references
  the req-ids that appear in its `context`; `link_type` comes from
  `LINK_TYPES` (`sysrs→sysrs` refines, `sysrs↔irs` derives, `mom→*` traces_to,
  `code→sysrs/irs` implements), default `traces_to`; confidence 0.7.
- `link_code_artifacts` — every artifact/endpoint/message `req_ids` becomes an
  `implements` link (0.8).
- `link_mom` — pairs of req-ids on the same MoM record become `traces_to`
  (0.6); ids not yet in the registry are returned as **new requirements**
  (e.g. the demo MoM adds `REQ-0011`).

### 6.7 Pipeline (`services/ingest/pipeline.py`)
- `ingest_file`: hash → parse → persist `SourceFile` → extract requirements →
  (MoM: also `link_mom` for new reqs + links) → `_store_extracts` (dedup by
  known ids) → `_store_links` → `chunk_blocks` → `index_chunks` → audit log.
- `ingest_codebase`: `analyze_code` → store artifacts as `code_artifact`
  requirements → persist `SourceFile` with `parsed_json` via
  `_serialize_analysis` (plain dicts, JSON-safe) → `link_code_artifacts` →
  chunk every supported source file → index → audit log.
- `extract_upload`: zips expand into a `code/` dir; everything else stored
  byte-for-byte.

### 6.8 LLM detail extraction (Qwen) — `services/ingest/llm_extractor.py`
`llm_extract_details(parsed, doc_type)` runs **before** the regex extractors and
asks the configured model (default **Qwen/Qwen2.5-7B-Instruct** via vLLM) for a
single JSON object of details that regex cannot capture:

- **sysrs/irs/doc**: `{"requirements": [{req_id, text, type, priority,
  verification, measure, target, interface, direction, protocol, module,
  context}]}` — this is what populates the rich `requirements.extra` metadata
  the generator reads (priority, verification, interface fields, NFR
  measure/target, module, …).
- **mom**: `{"mom_records": [{kind: action_item|decision|requirement_change,
  text, owner, due, req_ids}]}` — fed straight into `link_mom` for trace links
  and new-requirement discovery.

Validation is strict: `parse_json_block` extracts the JSON block (fenced or
plain), `normalize_requirements` drops ids that don't match `REQ_ID_PATTERN`
(no hallucinated ids) and coerces types via an allowlist, and only allowlisted
metadata keys are kept. In `pipeline.ingest_file` the LLM extracts are **merged**
with the regex extracts by `req_id` (`_merge_extracts`) — LLM output fills in
metadata gaps without losing deterministic records. When no model is reachable
(`mock` client) or `LLM_EXTRACTION_ENABLED=false`, the extractor returns `None`
and ingestion is byte-for-byte the regex path.

---

## 7. Retrieval (Phase 2a)

### Chunking (`services/rag/chunker.py`)
`chunk_blocks` walks `Block`s maintaining a heading path (levels determine
depth); `ChunkRecord.source_file` = the file path/name, `heading` = `a / b / c`
path, `req_ids` = ids found in the text. Text is split at `MAX_CHARS=800` with
`OVERLAP=80`, cutting on the nearest newline when possible.

### Embeddings (`services/rag/embeddings.py`)
`get_embedder()` (cached):
- `SentenceTransformerEmbedder` if `sentence_transformers` is importable
  (BAAI/bge-base-en-v1.5), normalised, projected to `EMBEDDING_DIM`;
- else `HashEmbedder` — deterministic MD5 feature-hashing to the configured
  dimension (air-gapped, no model download). Used by the demo when no model is
  cached.

### Vector store (`services/rag/vector_store.py`)
`index_chunks` inserts `Chunk` rows (embedding vector). `search` computes
`Chunk.embedding.cosine_distance(query_vec)`, orders ascending, optionally
filters by `source_doc_type`, takes `top_k*3` rows then the closest `top_k`,
and returns `SearchHit` dataclasses (with `source_file`/`heading` read from
`extra` metadata).

---

## 8. Generation (Phase 2b) — `services/generate/generator.py`

`generate_document(session, project, doc_type, ..., regenerate_section,
reviewer_comment, previous_version)` is the heart of the system:

1. Load the YAML schema for the doc type.
2. `get_or_create_document` (one live doc per project/doc_type).
3. `_build_content`:
   - If regenerating, start from the previous version's content minus
     `_evidence`/`_compliance`, and only rebuild the targeted section;
     otherwise start from an empty `{header, sections}`.
   - Per section, `_build_section`:
     - `requirements` → `_requirements_rows` from the registry
       (filtered by `req_type`; STP → `_test_cases`, STR → `_test_outcomes`),
       plus a gap list for SRS/SDD (sysrs/irs reqs not covered).
     - `traceability_matrix` → `_matrix_rows` (all links + uncovered ids).
     - otherwise per field: `_generate_text_field` runs a RAG search for
       `"{section.title} {field.title}"`, builds grounding lines
       `"{source_file} | {heading} | {text}"` (newlines sanitised), and prompts
       the LLM via `GROUNDING_MARKER`; `_generate_table_field` builds table rows
       from the top hits (requirement_id column ← `hit.req_ids[0]`, else
       heading). Both record structured `evidence`.
4. `check_compliance` (`compliance.py`): collect all text; `referenced_ids` via
   `find_req_ids`; `missing_refs` = referenced ids not in registry;
   `missing_sections` = required sections that are empty; `uncovered` =
   registry ids (non code_artifact/test_case) never referenced. Status
   `pass` when no missing refs/sections. Stored as `content["_compliance"]`.
5. Version number: current+1 normally; `previous_version.version + 1` on
   section regeneration.
6. `render_document` (`renderer.py`, python-docx): title page with
   classification banner + document-control table, then each section as
   headings/tables; annexures handled; empty sections render "(not generated)".
7. Write the JSON snapshot (full `content`) next to the DOCX.
8. Collect `source_versions` (`{doc_type: content_hash[:12]}` of ingested
   `SourceFile`s).
9. `commit_version` (`git_service.py`): ensure bare repo
   `GIT_REPOS_ROOT/{slug}.git` + cloned work tree `GIT_WORK_ROOT/{slug}`, copy
   in the DOCX/JSON/compliance files, `git commit` with message
   `[SRS] v1 auto-version | source_versions=... llm=mock`, push to the bare
   repo if a remote exists. The sha lands on both `DocumentVersion` and
   `Document`.
10. `index_document_content`: the generated sections are themselves chunked and
    re-indexed under `source_doc_type={doc_type.lower()}`,
    `source_file={DOC_TYPE}.generated`, so downstream documents (SDD grounds
    on `srs`, STR on `stp`) can retrieve them.
11. `log_action(..., "generate", "document_version", ...)`.

### Test derivation & outcomes
- **STP** (`_test_cases`): if no `test_case` rows exist, derive `TP-NNNN` rows
  for every functional/interface/non_functional requirement, persist them as
  `test_case` requirements plus `verifies` traceability links. Deterministic,
  not LLM.
- **STR** (`_test_outcomes`): for each test case, read the MoM source text and
  mark `PASS`/`FAIL`/`UNTESTED` per referenced `REQ-`/`SR-` id (lines
  containing PASS/VERIFIED/FAIL), falling back to `UNTESTED`.

---

## 9. LLM client (`services/llm/client.py`)

- `GROUNDING_MARKER = "GROUNDING CHUNKS:"` — the marker separating instructions
  from grounding context in the prompt.
- `VLLMClient.complete` — OpenAI-compatible `POST {base}/chat/completions`,
  `temperature=0.2`, `max_tokens=1500`, bearer auth.
- `MockLLMClient.complete` — `_extract_chunks` parses each grounding line with
  `split("|", 2)` into `{source_file, heading, text}` (robust fallback when a
  line has fewer than 3 parts) and returns
  `DRAFT (mock, grounded on N retrieved chunks): …`. This makes the whole
  system runnable with **no model** and produces deterministic output.
- `probe_vllm()` — GET `{base}/models` with a short timeout.
- `get_llm_client()` (cached): `LLM_MODE=vllm` → vLLM; `mock` → mock;
  `auto` → vLLM if it responds, else mock. The default model name is
  `Qwen/Qwen2.5-7B-Instruct` (`LLM_MODEL`) and is used both for **section
  generation** and for **ingestion detail extraction** (see §6.8). With no
  vLLM server the demo reports `llm=mock`, uses the regex extractors, and
  v1→v2 diffs are empty (identical deterministic output).

---

## 10. Review workflow (Phase 4) — `services/review_service.py`

State machine on `Document.status`:
`draft → in_review → changes_requested → in_review → approved`.

- `submit_for_review` → `in_review`.
- `review_section(document, version, section_id, decision, comment)`:
  `approved` or `rejected`; a rejection flips the document to
  `changes_requested`. Every decision is a `Review` row + audit entry.
- `regenerate_section(..., comment)`: calls `generate_document` with
  `regenerate_section` + `previous_version` (so only that section is rebuilt
  and versioned), then returns the document to `in_review`.
- `approve_document`: status `approved`, `Document.git_commit_sha` = the
  version's sha, and `git_service.tag_baseline` creates
  `baseline-{doc_type.lower()}-v{version}` (force) in the repo.
- `section_statuses(reviews, section_ids)` maps each section to
  `approved|rejected|not_reviewed`.
- `version_diff(prev, curr)` compares `sections` per id →
  `added|removed|modified|unchanged`.

`get_user(username)` auto-creates a reviewer user (idempotent).

Routes (`api/routes/review.py`): `submit`, `sections/{section_id}/review`,
`sections/{section_id}/regenerate`, `approve`, `documents/{id}/reviews`.

---

## 11. Evaluation harness (Phase 7) — `services/eval/evaluator.py`

`run_evaluation(project_id)` produces a report:
- **Requirements**: total vs "real" (excluding `code_artifact`/`test_case`).
- **Traceability**: link count, dangling links (either end not in registry),
  completeness = `1 - dangling/total`.
- **Per document** (latest version): `requirement_coverage` (referenced real
  reqs / registry), `template_conformance` (sections present / expected),
  `compliance_status` from the stored `_compliance`.
- **Cross-document consistency**: for each doc pair, Jaccard of the set of
  req-ids referenced by each.
- **Similarity vs source**: for SRS↔sysrs, SDD↔srs, ICD↔irs, STP↔srs, STR↔stp —
  ROUGE-1/2/L plus `bertscore_like` (embedding-based F1 over sentence vectors).
- `write_scoring_sheet` exports a CSV with empty `human_review_score` /
  `human_comments` columns for manual scoring.

Routes (`api/routes/eval.py`): `POST /eval/run`, `GET /eval/report` (in-memory
cache), `GET /eval/scoring-sheet.csv`.

---

## 12. API reference (`/api/v1`)

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/health`, `/health/db` | liveness, DB reachability |
| GET/POST | `/templates`, `/templates/validate`, `/templates/{id}` | list/validate/get YAML schemas |
| GET/POST | `/projects` | list / create project |
| POST | `/projects/{id}/uploads` | multi-file ingest (docx/pdf/zip) |
| POST | `/projects/{id}/ingest/run` | re-run pending ingestions |
| GET | `/projects/{id}/requirements` | requirement registry |
| GET | `/projects/{id}/traceability` | traceability links |
| GET | `/projects/{id}/documents` | document list |
| GET | `/documents/{id}` | document + version history |
| GET | `/documents/{id}/versions/{v}` | full version content |
| GET | `/documents/{id}/versions/{v}/diff` | section-aware diff vs previous version |
| POST | `/projects/{id}/generate/{doc_type}` | generate (or regenerate a section) |
| GET | `/projects/{id}/documents/{doc_type}/download` | download latest DOCX |
| POST | `/documents/{id}/submit` | submit for review |
| POST | `/documents/{id}/versions/{v}/sections/{s}/review` | approve/reject a section |
| POST | `/documents/{id}/versions/{v}/sections/{s}/regenerate` | regenerate one section |
| POST | `/documents/{id}/approve` | approve + git baseline tag |
| GET | `/documents/{id}/reviews` | reviews + section status map |
| POST/GET | `/projects/{id}/eval/run`, `/eval/report` | run / fetch evaluation |
| GET | `/projects/{id}/eval/scoring-sheet.csv` | human scoring CSV |
| GET | `/audit?project_id=` | audit trail (last 200) |

---

## 13. Frontend (`frontend/`)

React 18 + Vite 6 SPA. `vite.config.ts` proxies `/api` to the backend
(currently `http://localhost:8002`; dev port is 5174).

- `src/api.ts` — thin typed fetch wrapper over `/api/v1`; `uploadFiles` sends
  `multipart/form-data`, everything else JSON.
- `src/types.ts` — shared interfaces (Project, RequirementRow, TraceLink,
  DocumentSummary/Detail, VersionDetail, DiffRow, ComplianceReport, EvalReport).
- `src/App.tsx` — app shell; `ProjectPage.tsx` lists/creates projects.
- Tabs: `UploadTab` (ingest sources + codebase zip), `RequirementsTab`,
  `TraceabilityTab`, `DocumentsTab` (list + `DocumentEditor`), `EvalTab`.
- `DocumentEditor.tsx` — version history, per-version content, section diff,
  generate/regenerate, submit → per-section review (approve/reject with
  comment) → approve, and DOCX download.

---

## 14. Infra & tooling

### `infra/docker-compose.yml`
- `db` — `pgvector/pgvector:pg16`, schema from `infra/postgres/init.sql`
  (mounted into `/docker-entrypoint-initdb.d`), healthcheck.
- `git-server` — git daemon on :9418 serving bare repos at `/repos`.
- `backend` — FastAPI image, `DATABASE_URL`/`GIT_REPOS_ROOT`/`LLM_BASE_URL`
  env, code volume-mounted, depends on healthy db.
- `frontend` — Vite on :5173.

### `Makefile`
`up/down/ps/logs/db-psql`, `backend-install/dev/test/lint`,
`frontend-install/dev/build`. Note: `make backend-dev` runs uvicorn on :8000.

### `scripts/`
- `gen_fixtures.py` — regenerates the three sample DOCX fixtures
  (SysRS REQ-0001..0010, IRS IR-0101..0104 with interface links, MoM with
  decisions/action items/requirement changes/test outcomes incl. the new
  `REQ-0011`).
- `demo.py` — end-to-end demo through the REST API (see below).

### `sample_data/telemetry_acq/`
Reference codebase: `acquisition.py`, `processing.py`, `server.py`, `api.proto`,
`__init__.py` — exercised by the code analyzer (functions/classes/endpoints/
proto messages, e.g. `C-acquisition.acquire_samples`).

---

## 15. Running it

### Docker (all-in-one)
```bash
make up                      # db + git-server + backend + frontend
curl localhost:8000/api/v1/health
```

### Native (as used in development)
```bash
# 1. Postgres+pgvector container (or infra): db user docgen/docgen, db docgen
docker compose -f infra/docker-compose.yml up -d db git-server

# 2. Backend (choose a port; 8002 is used in dev because 8000 is often taken)
python3 -m venv /tmp/opencode/docgen-venv
/tmp/opencode/docgen-venv/bin/pip install -r backend/requirements.txt -r backend/requirements-dev.txt
export $(grep -v '^#' .env | xargs)      # or set env vars from §3
cd backend && /tmp/opencode/docgen-venv/bin/uvicorn app.main:app --port 8002 --host 127.0.0.1

# 3. Frontend
cd frontend && npm install && npm run dev   # proxy target must match backend port
```

Tests / lint:
```bash
cd backend && ../.venv/bin/pytest -q          # 6 passed
cd backend && ../.venv/bin/ruff check .       # clean
cd frontend && npm run build                  # TS + vite build clean
```

### End-to-end demo
```bash
BASE_URL=http://localhost:8002 /tmp/opencode/docgen-venv/bin/python scripts/demo.py
```
Drives: create project → upload SysRS/IRS/MoM/codebase-zip → registry +
traceability → generate SRS/SDD/ICD/STP/STR → review workflow (submit → reject
section → regenerate v2 → approve → `baseline-srs-v2` tag) → version diff →
evaluation. With the mock LLM this is fully offline and deterministic.

---

## 16. Behaviour notes & known quirks

- **Mock LLM default**: with no vLLM at `LLM_BASE_URL`, `auto` falls back to
  `MockLLMClient`; generation then needs no network/model. Downsides: output is
  deterministic (a regenerated section's diff vs v1 is empty — expected) and
  the LLM ingestion extractor reports no details, so ingestion uses the regex
  extractors (unchanged offline behaviour).
- **Qwen path**: start a vLLM server serving a Qwen model, set
  `LLM_MODE=vllm` (or leave `auto`) + `LLM_BASE_URL` + `LLM_MODEL`, and the
  same client drives both section generation and ingestion detail extraction.
- **Embedding fallback**: without a cached SentenceTransformer model,
  `HashEmbedder` (MD5 hashing, same 768 dim) keeps RAG fully offline.
- **Chunk filename location**: `source_file` is stored in `Chunk.extra` (the
  model has no such column); retrieval reads it back from metadata.
- **Version diff** compares section content structurally; identical regenerated
  sections report `unchanged`.
- **tree-sitter 0.23**: grammar loaders must wrap the PyCapsule in
  `Language(...)` before constructing a `Parser`.
- **pkill pitfall**: don't kill the backend with `pkill -f "uvicorn
  app.main:app"` from the same shell — the pattern matches the shell's own
  command line. Kill by PID from `ss -tlnp | rg ':8002'`.
- **Ports in dev**: 8000/5173 are commonly occupied; the current dev setup
  uses backend :8002 and frontend :5174 with the Vite proxy pointed at 8002.
- **Storage layout** (`STORAGE_ROOT`): `{project_id}/uploads/…`, plus per
  project `{slug}/{doc_type}/` holding `*_v{n}.docx`, `*_v{n}.json` and
  `compliance_v{n}.json`; git stores the same artifacts committed per version.
