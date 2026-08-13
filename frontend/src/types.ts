export interface Project {
  id: string;
  name: string;
  description: string | null;
  git_repo_path: string | null;
  status: string;
  created_at: string;
}

export interface AuditRow {
  id: number;
  project_id: string | null;
  action: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface ProjectAnalysis {
  structure: string;
  plan: string;
  flow: string;
  working_purpose: string;
  functioning: string;
  improvements_and_corrections: string;
  readme_markdown: string;
  total_files: number;
  file_tree: string[];
  ast_element_count: number;
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

export interface ProjectAnalysis {
  // 1. Structure & Architecture
  structure: string;
  // 2. Development Plan & Strategy
  plan: string;
  // 3. Execution Flow & Data Movement
  flow: string;
  // 4. Working Purpose & Utility
  working_purpose: string;
  // 5. Component Functioning & Logic
  functioning: string;
  // 6. Design Decisions & Trade-offs
  design_decisions: string;
  // 7. Assumptions & Constraints
  assumptions_and_constraints: string;
  // 8. Error Handling & Failure Modes
  error_handling: string;
  // 9. Configuration Reference
  configuration_reference: string;
  // 10. Security Overview
  security_overview: string;
  // 11. Extension Guide
  extension_guide: string;
  // 12. Glossary & FAQ
  glossary_and_faq: string;
  // 13. Dependency Report & Technical Debt Inventory
  tech_debt_and_dependencies: string;
  // 14. Data Flow & Sequence Diagrams (Mermaid.js)
  sequence_diagrams: string;
  // 15. Module Dependency Graph & Test Coverage
  module_graph_and_coverage: string;
  // 16. Known Limitations & Deployment Runbook
  limitations_and_runbook: string;
  // 17. Production-Ready README.md
  readme_markdown: string;
  // Metadata
  total_files: number;
  file_tree: string[];
  ast_element_count: number;
}

