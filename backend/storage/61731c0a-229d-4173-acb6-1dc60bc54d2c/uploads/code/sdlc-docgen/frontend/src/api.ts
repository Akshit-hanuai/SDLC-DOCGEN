import type {
  DiffRow,
  DocumentDetail,
  DocumentSummary,
  EvalReport,
  Project,
  RequirementRow,
  TraceLink,
  VersionDetail,
} from "./types";

const API_BASE = "/api/v1";

export interface UploadResult {
  source_file_id: string;
  filename: string;
  doc_type: string;
  hash?: string;
  artifacts?: number;
  chunks?: number;
}

function errorMessage(path: string, resp: Response, body: string): string {
  let requestId: string | null = null;
  try {
    const json = JSON.parse(body);
    if (json?.request_id) requestId = String(json.request_id);
  } catch {
    /* body is not JSON */
  }
  requestId = requestId ?? resp.headers.get("X-Request-ID");
  const detail = body.slice(0, 300);
  return requestId ? `${path} -> ${resp.status} (request ${requestId}): ${detail}` : `${path} -> ${resp.status}: ${detail}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    headers: init?.body instanceof FormData ? undefined : { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(errorMessage(path, resp, body));
  }
  if (resp.status === 204) return undefined as T;
  return resp.json();
}

export const api = {
  health: () => request<{ status: string; app: string; version: string }>("/health"),

  listProjects: () => request<Project[]>("/projects"),
  createProject: (name: string, description?: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  deleteProject: (projectId: string) =>
    request<void>(`/projects/${projectId}`, { method: "DELETE" }),

  uploadFiles: (projectId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{ project_id: string; ingested: UploadResult[] }>(`/projects/${projectId}/uploads`, {
      method: "POST",
      body: form,
    });
  },

  requirements: (projectId: string) =>
    request<{ total: number; requirements: RequirementRow[] }>(`/projects/${projectId}/requirements`),
  traceability: (projectId: string) =>
    request<{ total: number; links: TraceLink[] }>(`/projects/${projectId}/traceability`),

  documents: (projectId: string) =>
    request<{ documents: DocumentSummary[] }>(`/projects/${projectId}/documents`),
  document: (documentId: string) => request<DocumentDetail>(`/documents/${documentId}`),
  version: (documentId: string, version: number) =>
    request<VersionDetail>(`/documents/${documentId}/versions/${version}`),
  diff: (documentId: string, version: number) =>
    request<{ version: number; changes: DiffRow[] }>(`/documents/${documentId}/versions/${version}/diff`),

  generate: (projectId: string, docType: string, sectionId?: string, comment?: string) =>
    request<{ version: number; compliance: { status: string }; model_metadata: { llm_client: string } }>(
      `/projects/${projectId}/generate/${docType}`,
      {
        method: "POST",
        body: JSON.stringify({ section_id: sectionId || null, reviewer_comment: comment || null }),
      }
    ),

  submit: (documentId: string, username: string) =>
    request(`/documents/${documentId}/submit`, { method: "POST", body: JSON.stringify({ username }) }),
  reviewSection: (documentId: string, version: number, sectionId: string, username: string, decision: string, comment?: string) =>
    request(`/documents/${documentId}/versions/${version}/sections/${sectionId}/review`, {
      method: "POST",
      body: JSON.stringify({ username, decision, comment }),
    }),
  regenerateSection: (documentId: string, version: number, sectionId: string, comment: string, targetField?: string) =>
    request(`/documents/${documentId}/versions/${version}/sections/${sectionId}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ comment, target_field: targetField || null }),
    }),
  approve: (documentId: string, username: string) =>
    request(`/documents/${documentId}/approve`, { method: "POST", body: JSON.stringify({ username }) }),

  runEval: (projectId: string) => request<EvalReport>(`/projects/${projectId}/eval/run`, { method: "POST" }),
  evalReport: (projectId: string) => request<EvalReport>(`/projects/${projectId}/eval/report`),
  downloadUrl: (projectId: string, docType: string) =>
    `${API_BASE}/projects/${projectId}/documents/${docType}/download`,
};
