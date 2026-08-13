import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocumentSummary, Project } from "../types";
import DocumentEditor from "./DocumentEditor";
import { Button, Card, Chip, EmptyState, Icon, Spinner } from "./ui";

const STATUS_TONES: Record<string, "neutral" | "green" | "amber" | "red" | "cyan"> = {
  draft: "neutral",
  in_review: "amber",
  changes_requested: "red",
  approved: "green",
};

const DOC_TITLES: Record<string, string> = {
  SRS: "Software Requirements Specification",
  SDD: "Software Design Description",
  ICD: "Interface Control Document",
  STP: "Software Test Plan",
  STR: "Software Test Report",
};

const DOC_ICONS: Record<string, Parameters<typeof Icon>[0]["name"]> = {
  SRS: "filetext",
  SDD: "cpu",
  ICD: "link",
  STP: "target",
  STR: "activity",
};

export default function DocumentsTab({ project, onChanged }: { project: Project; onChanged?: () => void }) {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [active, setActive] = useState<DocumentSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    setLoading(true);
    try {
      setDocuments((await api.documents(project.id)).documents);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refresh();
  }, [project.id]);

  if (active) {
    return (
      <DocumentEditor
        document={active}
        onBack={() => setActive(null)}
        onChanged={() => {
          refresh();
          onChanged?.();
        }}
      />
    );
  }

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <Button variant="ghost" size="sm" icon="refresh" onClick={refresh}>
          Refresh
        </Button>
      </div>

      {loading ? (
        <div className="center">
          <Spinner large />
        </div>
      ) : error ? (
        <Card>
          <div className="muted">{error}</div>
        </Card>
      ) : documents.length === 0 ? (
        <Card>
          <EmptyState
            icon="filetext"
            title="No documents yet"
            body="Ingest sources and generate SRS / SDD / ICD / STP / STR documents from the Ingest tab."
          />
        </Card>
      ) : (
        <div className="grid grid-3">
          {documents.map((document) => {
            const tone = STATUS_TONES[document.status] || "neutral";
            return (
              <div key={document.id} className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <span
                    style={{
                      display: "grid",
                      placeItems: "center",
                      width: 40,
                      height: 40,
                      borderRadius: 11,
                      background: "var(--accent-soft)",
                      color: "var(--accent)",
                    }}
                  >
                    <Icon name={DOC_ICONS[document.doc_type] || "filetext"} size={20} />
                  </span>
                  <Chip tone={tone} dot>
                    {document.status}
                  </Chip>
                </div>
                <div>
                  <div style={{ fontFamily: "var(--mono)", fontSize: 18, fontWeight: 800, letterSpacing: "-0.01em" }}>
                    {document.doc_type}{" "}
                    <span className="faint" style={{ fontWeight: 600 }}>
                      v{document.current_version}
                    </span>
                  </div>
                  <div className="faint" style={{ fontSize: 12.5, marginTop: 2 }}>
                    {DOC_TITLES[document.doc_type] || "Document"}
                  </div>
                </div>
                <div className="kv" style={{ gridTemplateColumns: "auto 1fr" }}>
                  <dt>git</dt>
                  <dd className="mono">{document.git_commit_sha || "—"}</dd>
                </div>
                <div className="row" style={{ marginTop: "auto" }}>
                  <Button variant="primary" size="sm" icon="filetext" onClick={() => setActive(document)}>
                    Open
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon="download"
                    onClick={() => window.open(api.downloadUrl(project.id, document.doc_type), "_blank")}
                  >
                    DOCX
                  </Button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
