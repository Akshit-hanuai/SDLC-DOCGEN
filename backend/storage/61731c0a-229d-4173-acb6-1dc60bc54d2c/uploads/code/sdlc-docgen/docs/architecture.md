# Architecture notes

## Pipeline overview

```
MoM / SysRS / IRS / codebase
        |
        v   Phase 1
[ ingest & parse ]   (pdfplumber/PyMuPDF, python-docx, pytesseract, tree-sitter)
        |
        v
[ requirement registry + traceability_links ]   (Postgres)
        |
        v   Phase 2
[ chunk + embed ] -> pgvector -> [ section-wise LLM generation ] -> raw JSON
        |
        v
[ compliance checker ]   (every req id grounded, all required sections present)
        |
        v
[ template renderer ] -> DOCX
        |
        v   Phase 3
[ git auto-commit + audit_log + version diff ]
        |
        v   Phase 4
[ review workflow: author -> reviewer -> approver ]
```

## Non-negotiable constraints and how the design meets them

1. **Air-gapped.** The backend only talks to endpoints configured in
   `app/config.py` (`LLM_BASE_URL`, `EMBEDDING_MODEL`). No hardcoded external
   hosts; all models/embeddings must be on the local network or pre-cached.
2. **Grounded generation.** `requirements` and `traceability_matrix` template
   sections are filled from the DB registry, not free text. The compliance
   checker rejects any generated text that references a requirement id absent
   from `traceability_links`.
3. **Full audit.** Every generate/edit writes a complete JSON snapshot into
   `document_versions`, a git commit, and an `audit_log` row carrying
   who/when/which source versions (the `source_versions` JSONB).
4. **Template-driven, not hardcoded.** All layout/field rules live in the YAML
   schemas in `backend/app/templates/`. Adding a new doc type = adding a YAML
   file.
5. **Review is first-class.** `reviews` table is per (document, version,
   section); reject-with-comment re-invokes generation for that section only.

## Phase 5: input-to-section mapping (target)

| Output | Primary inputs                       | Notes |
| ------ | ------------------------------------ | ----- |
| SRS    | MoM, SysRS, IRS                      | section-wise generation, traceability matrix |
| SDD    | SRS + codebase AST                   | structure from tree-sitter, narrative from LLM |
| ICD    | IRS + interface clauses              | mechanical extraction first; LLM only for narrative |
| STP    | SRS/SDD testable units               | derived mostly deterministically |
| STR    | STP + MoM outcomes/logs              | compare expected vs actual |

## Key decisions

- Requirement identity is `(project_id, req_id)`; `traceability_links` uses
  composite FKs so links cannot leak across projects.
- `documents` has `UNIQUE (project_id, doc_type)` — one live document per
  type per project; history lives in `document_versions`.
- Embedding dimension is configurable (`EMBEDDING_DIM`). The `chunks` table
  is created with `vector(768)`; change the ALTER + config together if you
  switch models.
- Git backend is a bare-repo git-daemon in the compose stack (GitPython on the
  backend). The `git_repo_path` column keeps the door open for Gitea/GitLab.
- Structured JSON is the primary output contract; DOCX/PDF are renderers.
  This keeps everything inspectable and diffable per section.

## Open questions for the organisation

1. Exact requirement-ID pattern(s) across SysRS/IRS/MoM.
2. Numbering conventions for sections/figures/tables in org templates.
3. Review role policy (who may approve; is two-person review required?).
4. Classification labeling requirements for headers/footers.
5. Whether generated docs must be exported as DOCX only, or PDF as well.
