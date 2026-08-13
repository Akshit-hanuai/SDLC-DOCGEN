export interface Project {
  id: string;
  name: string;
  description: string | null;
  git_repo_path: string | null;
  status: string;
  created_at: string;
}

export interface RequirementRow {
  req_id: string;
  source: string;
  req_type: string;
  text: string;
  context: string;
}

export interface TraceLink {
  from: string;
  to: string;
  link_type: string;
  source: string;
  confidence: number | null;
}

export interface DocumentSummary {
  id: string;
  doc_type: string;
  title: string;
  status: string;
  current_version: number;
  git_commit_sha: string;
}

export interface DocumentDetail {
  id: string;
  project_id: string;
  doc_type: string;
  title: string;
  status: string;
  current_version: number;
  versions: {
    version: number;
    status: string;
    git_commit_sha: string;
    created_at: string | null;
    model_metadata: Record<string, unknown> | null;
  }[];
}

export interface VersionDetail {
  version: number;
  content: {
    sections: Record<string, Record<string, unknown>>;
    _evidence?: Record<string, Record<string, unknown[]>>;
    _compliance?: Record<string, unknown>;
  };
  source_versions: Record<string, string> | null;
  model_metadata: Record<string, unknown> | null;
}

export interface DiffRow {
  section_id: string;
  action: string;
  changed: boolean;
}

export interface ComplianceReport {
  status: string;
  passed: boolean;
  missing_requirement_references: string[];
  missing_sections: string[];
  uncovered_requirements: string[];
  referenced_ids: string[];
}

export interface EvalReport {
  requirements: { total: number; real: number };
  traceability: { links: number; dangling: number; completeness: number };
  documents: Record<
    string,
    {
      version: number;
      requirement_coverage: number;
      template_conformance: number;
      compliance_status: string;
      covered: number;
      total_requirements: number;
      sections_present: number;
      sections_expected: number;
    }
  >;
  cross_document_consistency: Record<string, { overlap: number; jaccard: number }>;
  similarity: Record<string, { rouge1: number; rouge2: number; rougeL: number; bertscore_like_f1: number }>;
}
