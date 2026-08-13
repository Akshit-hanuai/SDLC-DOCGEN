from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LLMHealth(BaseModel):
    mode: str
    client: str | None = None
    model: str | None = None
    endpoint_reachable: bool | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    database: str
    llm: LLMHealth
    error: str | None = None


class TemplateSummary(BaseModel):
    template_id: str
    doc_type: str
    name: str
    version: str
    organization: str | None = None
    num_sections: int
    required_sections: list[str]


class TemplateListResponse(BaseModel):
    templates: list[TemplateSummary]


class TemplateValidateResponse(BaseModel):
    valid: bool
    errors: list[str]


class UploadItem(BaseModel):
    filename: str | None = None
    doc_type: str
    source_file_id: str | None = None
    hash: str | None = None
    artifacts: int | None = None
    chunks: int | None = None


class UploadResponse(BaseModel):
    project_id: str
    ingested: list[UploadItem]


class IngestRunResponse(BaseModel):
    project_id: str
    ingested_files: int


class RequirementItem(BaseModel):
    req_id: str
    source: str
    req_type: str | None = None
    text: str
    context: str = ""


class RequirementsResponse(BaseModel):
    total: int
    requirements: list[RequirementItem]


class TraceLinkItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_req: str = Field(alias="from")
    to_req: str = Field(alias="to")
    link_type: str
    source: str
    confidence: float | None = None


class TraceabilityResponse(BaseModel):
    total: int
    links: list[TraceLinkItem]


class DocumentSummary(BaseModel):
    id: str
    doc_type: str
    title: str
    status: str
    current_version: int
    git_commit_sha: str = ""


class DocumentsResponse(BaseModel):
    documents: list[DocumentSummary]


class DocumentVersionSummary(BaseModel):
    version: int
    status: str
    git_commit_sha: str | None = None
    created_at: str | None = None
    model_metadata: dict[str, Any] | None = None


class DocumentDetail(BaseModel):
    id: str
    project_id: str
    doc_type: str
    title: str
    status: str
    current_version: int
    versions: list[DocumentVersionSummary]


class VersionDetail(BaseModel):
    version: int
    content: dict[str, Any]
    source_versions: dict[str, Any] | None = None
    model_metadata: dict[str, Any] | None = None
    git_commit_sha: str | None = None


class DiffChange(BaseModel):
    section_id: str
    action: str
    changed: bool


class DiffResponse(BaseModel):
    version: int
    changes: list[DiffChange]


class ComplianceReport(BaseModel):
    status: str
    passed: bool
    missing_requirement_references: list[str] = Field(default_factory=list)
    missing_sections: list[str] = Field(default_factory=list)
    uncovered_requirements: list[str] = Field(default_factory=list)
    referenced_ids: list[str] = Field(default_factory=list)
    registry_count: int = 0


class GenerateReport(BaseModel):
    document_id: str
    doc_type: str
    version: int
    compliance: ComplianceReport
    git_commit_sha: str | None = None
    model_metadata: dict[str, Any] | None = None
    rendered_path: str | None = None


class ActionResponse(BaseModel):
    id: str
    status: str


class ReviewResult(BaseModel):
    id: str
    decision: str
    section_id: str
    document_status: str


class RegenerateReport(GenerateReport):
    new_version: int


class ApproveResponse(BaseModel):
    id: str
    status: str
    version: int
    git_tag: str | None = None


class ReviewItem(BaseModel):
    version: int
    section_id: str
    decision: str
    comment: str | None = None


class ReviewsResponse(BaseModel):
    reviews: list[ReviewItem]
    section_status: dict[str, str]


class RequirementsCount(BaseModel):
    total: int
    real: int


class TraceabilityStats(BaseModel):
    links: int
    dangling: int
    completeness: float


class DocumentMetric(BaseModel):
    version: int
    requirement_coverage: float
    covered: int
    total_requirements: int
    template_conformance: float
    sections_present: int
    sections_expected: int
    compliance_status: str


class SimilarityMetrics(BaseModel):
    rouge1: float
    rouge2: float
    rougeL: float
    bertscore_like_f1: float


class PairConsistency(BaseModel):
    overlap: int
    jaccard: float


class EvalReport(BaseModel):
    project_id: str
    requirements: RequirementsCount
    traceability: TraceabilityStats
    documents: dict[str, DocumentMetric]
    cross_document_consistency: dict[str, PairConsistency]
    similarity: dict[str, SimilarityMetrics]


class AuditEntry(BaseModel):
    id: int
    project_id: str | None = None
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    details: dict[str, Any] | None = None
    created_at: str | None = None


class AuditResponse(BaseModel):
    entries: list[AuditEntry]