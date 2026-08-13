# SDLC DocGen

Automated generation of SDLC documents (**SRS, SDD, ICD, STP, STR**) for an
on-premises / air-gapped defence R&D environment. Every stage runs inside the
local network — LLM inference (via a self-hosted OpenAI-compatible endpoint),
embeddings, vector search (pgvector), storage and git-based version control.

No external API calls. No cloud dependencies. Your documents stay on-site.

---

## Table of contents

- [1. What it does](#1-what-it-does)
- [2. High-level architecture & data flow](#2-high-level-architecture--data-flow)
- [3. Repository structure](#3-repository-structure)
- [4. Technology stack](#4-technology-stack)
- [5. Configuration reference](#5-configuration-reference)
- [6. Database schema](#6-database-schema)
- [7. Document template system](#7-document-template-system)
- [8. REST API reference](#8-rest-api-reference)
- [9. Web UI: screens & buttons](#9-web-ui-screens--buttons)
- [10. End-to-end workflow (step by step)](#10-end-to-end-workflow-step-by-step)
- [11. Getting started](#11-getting-started)
- [12. Running the automated demo](#12-running-the-automated-demo)
- [13. Tests, lint & builds](#13-tests-lint--builds)
- [14. Operations](#14-operations)
- [15. Production hardening](#15-production-hardening)
- [16. Troubleshooting](#16-troubleshooting)
- [17. Roadmap](#17-roadmap)

---

## 1. What it does

The system turns engineering sources into formal, version-controlled, reviewable
documents:

| Input source | Example | What the system extracts |
| --- | --- | --- |
| **SysRS** (`*sysrs*`) | System Requirements Specification (DOCX / PDF / TXT) | Requirements, types, priorities |
| **IRS** (`*irs*`) | Interface Requirements Specification | Interface requirements & contracts |
| **MoM** (`*mom*`) | Minutes of Meeting | Action items, decisions, requirement changes |
| **Codebase** (`*.zip`) | Source repository archive | Code artifacts, endpoints, modules (tree-sitter AST) |

Output documents:

| Doc | Title | Grounded on |
| --- | --- | --- |
| **SRS** | Software Requirements Specification | SysRS + MoM + IRS |
| **SDD** | Software Design Description | SRS + codebase + SysRS + MoM |
| **ICD** | Interface Control Document | IRS + SysRS + codebase |
| **STP** | Software Test Plan | SRS + SDD + SysRS |
| **STR** | Software Test Report | STP + MoM |

Every generated version is:
- **RAG-grounded** — each section is written from retrieved chunks (pgvector
  cosine search) of the ingested sources.
- **Version-controlled** — committed to a per-project bare git repository.
- **Reviewable** — section-by-section approve / reject / regenerate workflow
  with comments, plus a document-level submit → approve (baseline tag) flow.
- **Audited** — every action is written to an `audit_log`.
- **Rendered to DOCX** — one `.docx` per version, downloadable from the UI or API.

---

## 2. High-level architecture & data flow

```
                 ┌──────────────────────────────────────────────────────────┐
                 │                          FRONTEND                        │
                 │              React 18 + Vite (port 5174)                 │
                 └───────────────┬──────────────────────────────────────────┘
                                 │ HTTP/JSON (/api proxied to :8002)
┌────────────────────────────────▼───────────────────────────────────────────┐
│                              BACKEND (FastAPI)                             │
│  app/api/routes        routers: health, templates, projects, uploads,      │
│  app/services          requirements, documents, review, eval, audit        │
│                        ├─ ingest/    parsers, extractors, linker, code AST │
│                        ├─ rag/       chunker, embeddings, pgvector search │
│                        ├─ generate/  generator, compliance, DOCX renderer │
│                        ├─ review/    submit/approve/regenerate, version diff│
│                        ├─ eval/      ROUGE, BERTScore-like, consistency    │
│                        └─ llm/       OpenAI-compatible client (mock fallback)│
│  app/core              logging, request-id middleware, error envelope      │
│  app/models            SQLAlchemy async models (Postgres)                  │
└──────────┬──────────────────────────────┬──────────────────────┬───────────┘
           │                              │                      │
           ▼                              ▼                      ▼
    ┌─────────────┐            ┌────────────────────┐   ┌──────────────────┐
    │  POSTGRES   │            │  GIT repositories  │   │   FILE STORAGE   │
    │  + pgvector │            │  storage/repos/*.git│   │  storage/{id}/   │
    │  (docker)   │            │  + work trees      │   │    uploads, {doc} │
    └─────────────┘            └────────────────────┘   └──────────────────┘
                                                              ▲
                                                              │ OpenAI-compatible
                                                    ┌─────────┴─────────┐
                                                    │  LLM (Qwen via    │
                                                    │  vLLM or Ollama)  │
                                                    │  localhost:11434  │
                                                    └───────────────────┘
```

**End-to-end flow**

1. **Create project** → a row in `projects`, an id, and a slug.
2. **Upload sources** → files stored under `storage/{project_id}/uploads`.
   Zips are expanded; the doc type is auto-detected from the filename
   (`*mom*`, `*sysrs*`, `*irs*`, `*.zip`).
3. **Ingest** → each file is parsed into blocks, requirements are extracted
   (regex + optional LLM enrichment), linked (traceability), chunked, embedded
   and indexed into pgvector.
4. **Generate** → per document type, each section's text is produced by the LLM
   from retrieved grounding chunks; requirement and traceability sections are
   filled deterministically from the registry (never invented by the LLM).
   Content is rendered to DOCX, stored as JSON, committed to git.
5. **Compliance** → a report checks every referenced requirement id exists,
   all mandatory sections are present, and all registry requirements are covered.
6. **Review** → reviewers submit, review sections (approve / reject), regenerate
   with comments, and finally approve → a git baseline tag is created.
7. **Evaluate** → the harness measures coverage, conformance, consistency and
   ROUGE/BERTScore similarity vs the sources, and exports a human scoring CSV.

---

## 3. Repository structure

```
sdlc-docgen/
├── Makefile                      # dev/docker shortcuts (make up, make backend-dev, ...)
├── README.md                     # this document
├── backend/
│   ├── .env.example              # template for environment configuration
│   ├── pyproject.toml            # packaging + ruff + pytest config
│   ├── requirements.txt          # runtime dependencies (pinned)
│   ├── requirements-dev.txt      # dev/test dependencies
│   ├── app/
│   │   ├── main.py               # FastAPI app factory, middleware, error handlers
│   │   ├── config.py             # pydantic-settings configuration
│   │   ├── database.py           # async engine + session factory
│   │   ├── core/                 # production infra (added for hardening)
│   │   │   ├── context.py        #   request-id contextvar
│   │   │   ├── logging.py        #   centralised structured logging
│   │   │   └── middleware.py     #   RequestContextMiddleware (id + access log)
│   │   ├── api/routes/           # HTTP routers
│   │   │   ├── health.py         #   GET /health
│   │   │   ├── templates.py      #   GET /templates[/{id}|/validate]
│   │   │   ├── projects.py       #   GET/POST /projects, DELETE /projects/{id}
│   │   │   ├── uploads.py        #   POST /projects/{id}/uploads, /ingest/run
│   │   │   ├── requirements.py   #   GET requirements, traceability
│   │   │   ├── documents.py      #   list/get/version/diff/generate/download
│   │   │   ├── review.py         #   submit, review section, regenerate, approve
│   │   │   ├── eval.py           #   run/report/scoring-sheet
│   │   │   └── audit.py          #   GET /audit
│   │   ├── models/               # SQLAlchemy async models
│   │   │   ├── base.py, mixins.py, user.py, project->document.py,
│   │   │   ├── source.py, requirement.py, review.py
│   │   ├── schemas/              # Pydantic schemas (project, template)
│   │   ├── services/
│   │   │   ├── ingest/           # pipeline, parsers, extractors, linker, code_analyzer, llm_extractor
│   │   │   ├── rag/              # chunker, embeddings, vector_store
│   │   │   ├── generate/         # generator, compliance, renderer
│   │   │   ├── llm/              # OpenAI-compatible LLM client + mock fallback
│   │   │   ├── review_service.py # review orchestration + version diff
│   │   │   ├── git_service.py    # per-project git repos, commits, baseline tags
│   │   │   ├── template_store.py # YAML template loader/validator
│   │   │   ├── audit.py          # audit_log writer
│   │   │   └── eval/evaluator.py # metrics: coverage, ROUGE, consistency
│   │   └── templates/            # srs.yaml, sdd.yaml, icd.yaml, stp.yaml, str.yaml
│   ├── storage/                  # runtime artifacts (uploads, rendered docs, repos)
│   └── tests/                    # pytest suite
├── frontend/
│   ├── package.json              # react 18, vite 6, typescript
│   ├── vite.config.ts            # dev port 5174, /api proxy -> :8002
│   └── src/
│       ├── main.tsx, App.tsx     # app shell, project list + create/delete
│       ├── api.ts                # typed HTTP client for every endpoint
│       ├── types.ts              # shared TypeScript interfaces
│       ├── index.css             # design tokens + component styles
│       └── components/
│           ├── ui.tsx            # Icon, Button, Card, Chip, Stat, Alert, ...
│           ├── ProjectPage.tsx   # workspace header, stats, tabs
│           ├── UploadTab.tsx     # ingest + generate
│           ├── RequirementsTab.tsx
│           ├── TraceabilityTab.tsx
│           ├── DocumentsTab.tsx
│           ├── DocumentEditor.tsx
│           └── EvalTab.tsx
├── infra/
│   ├── docker-compose.yml        # db (pgvector), git-server, backend, frontend
│   ├── postgres/init.sql         # schema DDL (also the source of truth)
│   └── git/                      # bare git server image
├── scripts/
│   ├── demo.py                   # full API pipeline demo
│   └── gen_fixtures.py           # generate sample fixtures
├── sample_data/                  # fixtures (SysRS/IRS/MoM docx) + telemetry_acq code
└── docs/                         # PROJECT_GUIDE.md, architecture.md
```

---

## 4. Technology stack

| Layer | Technology |
| --- | --- |
| Backend | Python 3.11+, FastAPI 0.115, Uvicorn, SQLAlchemy 2 (async), asyncpg |
| Vector search | PostgreSQL 16 + pgvector (`cosine_distance`) |
| Embeddings | `BAAI/bge-base-en-v1.5` via sentence-transformers (fallback: MD5 HashEmbedder, same 768 dim) |
| LLM | OpenAI-compatible endpoint (vLLM/TGI or Ollama) — default model `qwen2:7b`; `mock` client fallback |
| Parsing | python-docx, pdfplumber, PyMuPDF, tree-sitter (Python/TS/JS/Java) |
| Docs | python-docx / docxtpl rendering to DOCX |
| Git | GitPython (per-project bare repos + work trees) |
| Frontend | React 18, Vite 6, TypeScript 5 (strict) |
| Infra | Docker Compose, Makefile |

---

## 5. Configuration reference

All settings live in `backend/app/config.py` (pydantic-settings). They can be
set via environment variables (uppercase) or a `backend/.env` file.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `SDLC DocGen API` | API title |
| `APP_VERSION` | `0.2.0` | Version string |
| `DEBUG` | `False` | SQL echo + verbose behaviour |
| `LOG_LEVEL` | `INFO` | Root log level (`DEBUG`/`INFO`/`WARNING`/`ERROR`) |
| `DATABASE_URL` | `postgresql+asyncpg://docgen:docgen@localhost:5432/docgen` | Async Postgres DSN |
| `DB_POOL_SIZE` | `5` | SQLAlchemy async pool size |
| `DB_MAX_OVERFLOW` | `10` | Pool overflow connections |
| `LLM_MODE` | `auto` | `auto` (probe endpoint) · `vllm` · `mock` |
| `LLM_BASE_URL` | `http://localhost:8001/v1` | OpenAI-compatible base URL (e.g. Ollama `http://localhost:11434/v1`) |
| `LLM_API_KEY` | `EMPTY` | Bearer key for the endpoint |
| `LLM_MODEL` | `Qwen/Qwen2.5-7B-Instruct` | Model id sent to the endpoint |
| `LLM_TIMEOUT_S` | `120.0` | Completion timeout |
| `LLM_PROBE_S` | `3.0` | Probe (models list) timeout |
| `LLM_EXTRACTION_ENABLED` | `True` | Use the LLM during ingestion for rich details |
| `LLM_EXTRACTION_MAX_CHARS` | `20000` | Text cap for extraction prompts |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | Sentence-transformer model id |
| `EMBEDDING_DIM` | `768` | Vector dimension |
| `RETRIEVER_TOP_K` | `8` | Grounding chunks retrieved per field |
| `GIT_REPOS_ROOT` | `/repos` | Where per-project bare repos live |
| `GIT_WORK_ROOT` | `/tmp/docgen-work` | Where git work trees live |
| `STORAGE_ROOT` | `storage` | Uploads + rendered outputs |
| `REQ_ID_PATTERN` | `(?:REQ-\|SR-\|IR-...)` | Requirement-id regex used by extractors |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `MAX_UPLOAD_MB` | `100` | Per-file upload size cap (returns 413) |
| `REQUEST_ID_HEADER` | `X-Request-ID` | Correlation-id header name |

> The current dev setup uses `backend/.env` with
> `LLM_BASE_URL=http://localhost:11434/v1`, `LLM_MODEL=qwen2:7b` (local Ollama)
> and git/storage paths under `backend/storage/`. See [§11 Getting started](#11-getting-started).

---

## 6. Database schema

Schema DDL: `infra/postgres/init.sql`. Async models: `backend/app/models/`.

| Table | Purpose | Key columns |
| --- | --- | --- |
| `users` | Reviewers / users | `username`, `role`, `full_name` |
| `projects` | Project root (name unique) | `name`, `description`, `status`, `git_repo_path` |
| `source_files` | Ingested raw files | `filename`, `doc_type`, `path`, `content_hash`, `parsed_json` |
| `requirements` | Requirement registry | `req_id`, `source`, `req_type`, `text`, `extra` |
| `traceability_links` | Requirement links | `from_req_id`, `to_req_id`, `link_type`, `source`, `confidence` |
| `documents` | Per-doc-type rows | `doc_type`, `status`, `current_version`, `git_commit_sha` |
| `document_versions` | Immutable version snapshots | `version`, `content` (JSONB), `model_metadata`, `rendered_docx_path`, `git_commit_sha` |
| `reviews` | Section review decisions | `version`, `section_id`, `decision`, `comment` |
| `audit_log` | Every auditable action | `action`, `entity_type`, `entity_id`, `details` |
| `chunks` | Vectorised source chunks | `text`, `embedding` (vector(768)), `metadata`, `requirement_id` |

All child tables use `ON DELETE CASCADE` from `projects`, so deleting a project
removes everything (the DELETE endpoint also cleans git repos and storage dirs).

---

## 7. Document template system

Nothing about section layout is hardcoded. Each document type is a YAML file in
`backend/app/templates/` (`srs.yaml`, `sdd.yaml`, `icd.yaml`, `stp.yaml`,
`str.yaml`), validated by `TemplateStore.validate_all()`.

Key structure:

```yaml
template_id: srs
doc_type: SRS
name: Software Requirements Specification
numbering: { section: "{N}", requirement: "{PROJECT}-{NNNN}" }
header:
  document_control:        # title-page control fields
    - { field: document_id, default: "SDD-001" }
sections:
  - id: "1"
    title: "Introduction"
    type: free_text         # free_text | table | requirements | traceability_matrix
    required: true
    fields:
      - { id: scope, type: text, title: "Scope",
          instructions: "Describe the system scope." }
    data_sources: [sysrs, mom, irs]
```

- `requirements` sections are filled from the requirement registry — **never the
  LLM** — so IDs are always real.
- `traceability_matrix` sections are filled from `traceability_links`.
- `free_text`/`table` fields are LLM-generated, RAG-grounded on `data_sources`.

Inspect templates: `GET /api/v1/templates`, `GET /api/v1/templates/srs`,
`GET /api/v1/templates/validate`.

---

## 8. REST API reference

Base URL: `http://<host>:8002/api/v1`. Interactive docs: `http://<host>:8002/docs`.

### Health & system

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/` | App banner |
| GET | `/health` | Status + DB reachability + LLM client/model/endpoint reachability |
| GET | `/templates` | List template summaries |
| GET | `/templates/{id}` | Full template schema |
| GET | `/templates/validate` | Validation errors |

### Projects

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/projects` | List projects (newest first) |
| POST | `/projects` | Create `{name, description?}` |
| DELETE | `/projects/{id}` | Delete project + all data + git/storage artifacts |

### Ingestion

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/projects/{id}/uploads` | Upload multiple files (`multipart`, field `files`), auto-detect type, ingest. Max 20 files, 100 MB each. |
| POST | `/projects/{id}/ingest/run` | (Re)ingest pending source files |

### Requirements & traceability

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/projects/{id}/requirements` | Registry: `{total, requirements[]}` |
| GET | `/projects/{id}/traceability` | Links: `{total, links[]}` |

### Documents & generation

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/projects/{id}/documents` | Document summaries |
| GET | `/documents/{id}` | Detail + version history |
| GET | `/documents/{id}/versions/{v}` | Full version content + evidence + compliance |
| GET | `/documents/{id}/versions/{v}/diff` | Section-level diff vs previous |
| POST | `/projects/{id}/generate/{DOC}` | Generate/regenerate `SRS|SDD|ICD|STP|STR` (body: `{section_id?, reviewer_comment?}`) |
| GET | `/projects/{id}/documents/{DOC}/download` | Latest rendered DOCX |

### Review workflow

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/documents/{id}/submit` | Move to `in_review` |
| POST | `/documents/{id}/versions/{v}/sections/{s}/review` | `{username, decision: approved|rejected, comment?}` |
| POST | `/documents/{id}/versions/{v}/sections/{s}/regenerate` | Regenerate a section (new version) |
| POST | `/documents/{id}/approve` | Approve + create git baseline tag |
| GET | `/documents/{id}/reviews` | Review list + per-section status |

### Evaluation & audit

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/projects/{id}/eval/run` | Run evaluation |
| GET | `/projects/{id}/eval/report` | Latest report |
| GET | `/projects/{id}/eval/scoring-sheet.csv` | Human scoring sheet (CSV) |
| GET | `/audit?project_id={id}` | Audit log (last 200) |

**Error envelope** (production-hardened): HTTP 4xx keep FastAPI's `detail`;
422 validation errors return `{detail: [...], request_id}`; unexpected 500s
return `{detail: "An unexpected internal server error occurred.", request_id}`.
Every response carries `X-Request-ID`.

---

## 9. Web UI: screens & buttons

Dev server: `http://localhost:5174` (Vite proxies `/api` to `:8002`).

### 9.1 Home / project list (`App.tsx`)

Top bar:
- **Brand** — SDLC DocGen logo + tagline (click = home).
- **Backend status chip** — green `backend v0.2.0` when reachable, red `backend unreachable` otherwise.

Left column:
- **Page title / subtitle** — headline + capability chips (RAG-grounded, Review workflow, Git baseline).

Right column — **Create project** card:
- **Project name** input (required, Enter creates).
- **Description (optional)** input.
- **Create project** button (primary; disabled until a name is entered; shows *Creating…*).

Projects section:
- **Refresh** button (reloads list) + project count.
- Each **project card** (click card = open workspace):
  - **name**, status chip, **delete (×)** button, description, truncated id, created date, **Open workspace** button (arrow icon).

Delete flow (two-step confirmation):
1. Click **×** on a card → the button area becomes `Delete this project?` + **Delete** + **Cancel**.
2. Click **Delete** to permanently remove the project (DB rows, git repos, storage); click **Cancel** to abort.

### 9.2 Project workspace (`ProjectPage.tsx`)

Top bar:
- **Projects** button (back to home).
- **Project name** + description.
- **created** chip.

Stats row: **Requirements**, **Traceability links**, **Documents**, **pgvector** (vector index).
- **Refresh counts** button next to the tab bar.

Tabs:
- **Ingest & Generate**
- **Documents**
- **Requirements**
- **Traceability**
- **Evaluation**

### 9.3 Ingest & Generate tab (`UploadTab.tsx`)

**Ingest sources** card:
- **Dropzone** — drag & drop files, or click to browse (multiple files). Hints show the naming convention (`*mom* · *sysrs* · *irs* · *.zip`).
- Queued file list — each row shows the filename, size and a **Remove** button.
- **Upload & ingest** button (primary) — uploads, detects doc types, ingests, shows a success/error alert.
- **Clear** button (removes queued files).

**Generate documents** card:
- One card per doc type: **SRS, SDD, ICD, STP, STR** with full title and a **Generate {DOC}** button.
- While running the button shows a spinner (**Generating**); the result line under each card shows version + compliance + LLM client.

### 9.4 Documents tab (`DocumentsTab.tsx`)

- **Refresh** button.
- Grid of document cards, one per doc type:
  - doc-type icon, **status chip** (`draft` / `in_review` / `changes_requested` / `approved` with colored dot),
  - `SRS v3` + full title, **git sha** row,
  - **Open** button (opens the editor),
  - **DOCX** button (downloads the latest rendered document).
- Empty state if no documents.

### 9.5 Document editor (`DocumentEditor.tsx`)

Top row:
- **Documents** (back), **status chip**, **Approve (baseline)** button, **Submit for review** button.

Header:
- Doc icon + `SRS v3` + title; **git** sha and **model** info (right).

Cards:
- **Review controls** — reviewer username input.
- **Changed since previous version** — amber chips of changed sections (when a diff exists).
- **Compliance report** — pass/fail chip + missing refs / missing sections / uncovered reqs counts.

**Sections** card — one collapsible row per section:
- Click a header to expand/collapse; shows evidence group count.
- Fields render as text or tables; **evidence** blocks show grounding chunks (`[source] file — heading`).
- Per-section actions: comment input + **Approve section**, **Reject**, **Regenerate** buttons.

**Versions** card — timeline of versions (`v1 … vN`):
- Click a row to load that version (active row highlighted), shows status chip, git sha, LLM client.

### 9.6 Requirements tab (`RequirementsTab.tsx`)

- Search box (matches id / text / context) + **source** and **type** filter dropdowns.
- Table: ID, source chip, type chip, requirement text, context.

### 9.7 Traceability tab (`TraceabilityTab.tsx`)

- Search box + **link type** filter.
- Table: from → to, link-type chip (`refines`/`derives`/`traces_to`/`implements`/`verifies`), source, confidence %.

### 9.8 Evaluation tab (`EvalTab.tsx`)

- **Run evaluation** button (primary, spinner while running).
- Stat cards: **Links**, **Dangling**, **Completeness**, **Real reqs**.
- **Document metrics** table — coverage + conformance progress bars, compliance chip.
- **Cross-document consistency** table — shared ids, jaccard, similarity bar.
- **Similarity vs source** table — ROUGE-1/2/L, BERTScore-like.
- **Download human-review scoring sheet (CSV)** link.

---

## 10. End-to-end workflow (step by step)

1. **Start the stack** (see [§11](#11-getting-started)).
2. **Create a project** — from the UI card or:
   ```bash
   curl -X POST http://localhost:8002/api/v1/projects \
     -H 'Content-Type: application/json' \
     -d '{"name":"telemetry-acquisition","description":"Telemetry acquisition chain"}'
   ```
3. **Upload sources** — SysRS/IRS/MoM DOCX/PDF/TXT and the codebase ZIP, via the
   UI dropzone or:
   ```bash
   curl -X POST http://localhost:8002/api/v1/projects/<ID>/uploads \
     -F "files=@sample_data/fixtures/SysRS_v3.1.docx" \
     -F "files=@sample_data/fixtures/IRS_v2.0.docx" \
     -F "files=@sample_data/fixtures/MoM_DesignReview04.docx"
   ```
   Filenames must follow `*mom*` / `*sysrs*` / `*irs*` / `*.zip`.
4. **Inspect the registry** — open the **Requirements** tab (or
   `GET /projects/<ID>/requirements`) and **Traceability** tab.
5. **Generate documents** — click **Generate** for each doc type in order
   (SRS → SDD → ICD → STP → STR). Wait for the spinner; the result line shows
   version + compliance. Downloads appear in **Documents**.
6. **Review** — open a document, **Submit for review**, expand sections,
   approve/reject/regenerate, then **Approve (baseline)** to create the git tag.
7. **Evaluate** — open **Evaluation**, **Run evaluation**, inspect metrics,
   download the scoring CSV.
8. **Repeat/iterate** — upload revisions of sources and regenerate; diffs show
   what changed; the version timeline keeps the full history.

---

## 11. Getting started

### Prerequisites

- Linux/macOS, Python 3.11+, Node.js 20+, Docker + Docker Compose (for Postgres).
- A reachable OpenAI-compatible LLM endpoint (recommended: Ollama serving
  `qwen2:7b` on `localhost:11434`; or vLLM/TGI on `localhost:8001`). If none is
  available the backend falls back to a **mock** client that still exercises the
  whole pipeline.

### Option A — Docker (Postgres + git server + backend + frontend)

```bash
make up
# verify
curl localhost:8000/api/v1/health
curl localhost:8000/api/v1/templates
```

### Option B — Native dev

```bash
# 1. Postgres + pgvector (only the DB in Docker)
docker compose -f infra/docker-compose.yml up -d db

# 2. Backend
make backend-install          # creates .venv + installs deps
cd backend && cp .env.example .env   # then edit LLM_BASE_URL/LLM_MODEL to taste
cd backend && ../.venv/bin/uvicorn app.main:app --port 8002 --host 127.0.0.1

# 3. Frontend (another terminal)
make frontend-install
cd frontend && npm run dev    # http://localhost:5174 (proxy -> :8002)
```

> **Port conventions (this repo):** 8000/5173 are commonly taken, so the dev
> setup runs the backend on **:8002** and the frontend on **:5174**, with the
> Vite proxy pointed at 8002. `make backend-dev` starts uvicorn on :8000 by
> default — override if needed.

### Pointing the LLM at Ollama

```bash
# backend/.env
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=qwen2:7b
LLM_MODE=auto
```

Verify:
```bash
curl http://localhost:11434/v1/models        # endpoint up
curl http://localhost:8002/api/v1/health     # "llm":{"client":"vllm",...} = real model in use
```

---

## 12. Running the automated demo

A script drives the entire pipeline through the REST API
(create → ingest → generate all 5 docs → review → diff → evaluate):

```bash
BASE_URL=http://localhost:8002 /tmp/opencode/docgen-venv/bin/python scripts/demo.py
# or from the Makefile venv:
BASE_URL=http://localhost:8002 .venv/bin/python scripts/demo.py
```

Sample fixtures live in `sample_data/fixtures` (SysRS/IRS/MoM DOCX) and
`sample_data/telemetry_acq` (a reference codebase).

---

## 13. Tests, lint & builds

```bash
# Backend tests (19 tests: template loader, health, production hardening)
cd backend && ../.venv/bin/pytest -q

# Backend lint (ruff)
cd backend && ../.venv/bin/ruff check .

# Frontend typecheck + production build
cd frontend && npm run build        # tsc --noEmit && vite build
```

---

## 14. Operations

### Health & readiness

`GET /api/v1/health` reports:
```json
{
  "status": "ok",
  "app": "SDLC DocGen API",
  "version": "0.2.0",
  "database": "reachable",
  "llm": { "mode": "auto", "client": "vllm", "model": "qwen2:7b", "endpoint_reachable": true }
}
```

### Logging & correlation

- Logs go to **stderr** in the format:
  `2026-08-12 12:17:07 | INFO | api.access | req=<id> | GET /api/v1/health -> 200 (12.0 ms)`.
- Every request gets an `X-Request-ID` (generated or forwarded), echoed in the
  response and attached to all log lines — filter logs by `req=<id>` to trace a
  single request.
- Unhandled errors are logged with a full traceback and the request id, while
  the client only sees a masked 500 message.

### Storage layout

```
backend/storage/
├── {project_id}/uploads/         # raw uploads + extracted code zips
├── {slug}/{doc_type}/            # rendered DOCX + JSON + compliance per version
├── repos/{slug}.git              # per-project bare repositories
└── work/{slug}/                  # git work trees
```

### Audit

Every ingest / generate / review / approve action is recorded in `audit_log`
and queryable via `GET /api/v1/audit`.

---

## 15. Production hardening

What has been put in place for a production-shaped deployment:

- **Request correlation** — `X-Request-ID` end-to-end (middleware + contextvar).
- **Structured access logging** — method, path, status, duration, request id.
- **Graceful error envelope** — masked 500s (no stack traces leaked), structured
  422 validation errors with `request_id`, explicit `HTTPException` handling.
- **Lifecycle management** — startup health checks (DB + LLM client logging),
  shutdown disposes the connection pool.
- **DB pooling** — configurable `pool_size` / `max_overflow` + `pool_pre_ping`.
- **Upload hardening** — per-file size cap (413), max 20 files, sanitised
  filenames (strips paths/control chars), and **zip-slip protection** that
  rejects archive members escaping the extraction directory.
- **Config-driven** — every tunable is an env var (`.env` supported).
- **Versioning** — immutable per-version JSONB snapshots + git commits/tags.
- **Auditability** — full action audit log.

---

## 16. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Generation returns `DRAFT (mock, …)` | No reachable LLM endpoint. Start Ollama/vLLM or set `LLM_MODE=mock` intentionally. Check `GET /health` → `llm.client`. |
| `500 ... /repos PermissionError` | `GIT_REPOS_ROOT` points at an unwritable path. Set it to a writable dir, e.g. `backend/storage/repos`. |
| Frontend shows "backend unreachable" | Wrong port: Vite proxy targets `:8002`. Confirm the backend is up: `curl localhost:8002/api/v1/health`. |
| Upload fails with 413 | File exceeds `MAX_UPLOAD_MB`. |
| Backend dies after a shell exit | Run uvicorn detached: `setsid uvicorn app.main:app --port 8002 ... &`. |
| Killing the backend | `ss -tlnp | rg ':8002'` → kill by PID. Avoid `pkill -f "uvicorn app.main:app"` from the same shell (matches its own cmdline). |
| Documents keep old markdown (`**text**`) | Stored before the LLM-output cleaner was added — regenerate the document. |

---

## 17. Roadmap

Phase 1 ingestion → Phase 2 RAG + SRS → Phase 3 version control + audit →
Phase 4 review workflow → Phase 5 SDD/ICD/STP/STR → Phase 6 web UI →
Phase 7 evaluation harness — all implemented. Remaining organisational inputs:

1. The real organisational DOCX/PDF templates for the five document types.
2. The authoritative requirement-ID pattern(s) in use.
3. Signed-off production model card (quantisation, GPU sizing) for Qwen.
4. Hardening on the review signing (PKI / certificate-based approval).

See `docs/architecture.md` and `docs/PROJECT_GUIDE.md` for deep-dive design notes.
