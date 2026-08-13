import { useEffect, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import UploadTab from "./UploadTab";
import RequirementsTab from "./RequirementsTab";
import TraceabilityTab from "./TraceabilityTab";
import DocumentsTab from "./DocumentsTab";
import EvalTab from "./EvalTab";
import { Button, Icon, Stat } from "./ui";

type Tab = "upload" | "documents" | "requirements" | "traceability" | "eval";

const TABS: { id: Tab; label: string; icon: Parameters<typeof Icon>[0]["name"] }[] = [
  { id: "upload", label: "Ingest & Generate", icon: "upload" },
  { id: "documents", label: "Documents", icon: "filetext" },
  { id: "requirements", label: "Requirements", icon: "list" },
  { id: "traceability", label: "Traceability", icon: "link" },
  { id: "eval", label: "Evaluation", icon: "target" },
];

export default function ProjectPage({ project, onBack }: { project: Project; onBack: () => void }) {
  const [tab, setTab] = useState<Tab>("documents");
  const [counts, setCounts] = useState<{ requirements: number; links: number; documents: number } | null>(null);
  const [stamp, setStamp] = useState(0);

  useEffect(() => {
    let mounted = true;
    Promise.all([api.requirements(project.id), api.traceability(project.id), api.documents(project.id)])
      .then(([reqs, links, docs]) => {
        if (mounted) setCounts({ requirements: reqs.total, links: links.total, documents: docs.documents.length });
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, [project.id, stamp]);

  const created = new Date(project.created_at);
  const createdLabel = Number.isNaN(created.getTime())
    ? project.created_at
    : created.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });

  return (
    <div className="app-shell">
      <header className="topbar">
        <Button variant="ghost" size="sm" icon="arrowLeft" onClick={onBack}>
          Projects
        </Button>
        <div className="brand-name" style={{ lineHeight: 1.3 }}>
          {project.name}
          <small style={{ textTransform: "none", letterSpacing: "0.02em", fontWeight: 400 }}>
            {project.description || "Project workspace"}
          </small>
        </div>
        <div className="topbar-spacer" />
        <ChipSmall label="created" value={createdLabel} />
      </header>

      <main className="container fade-in">
        <div className="stats">
          <Stat icon="list" value={counts?.requirements ?? "—"} label="Requirements" tone="cyan" />
          <Stat icon="link" value={counts?.links ?? "—"} label="Traceability links" tone="violet" />
          <Stat icon="filetext" value={counts?.documents ?? "—"} label="Documents" tone="teal" />
          <Stat icon="database" value="pgvector" label="Vector index" tone="green" />
        </div>

        <div className="row" style={{ marginBottom: 22 }}>
          <nav className="tabs">
            {TABS.map((t) => (
              <button key={t.id} className={`tab ${tab === t.id ? "active" : ""}`} onClick={() => setTab(t.id)}>
                <Icon name={t.icon} size={15} />
                {t.label}
              </button>
            ))}
          </nav>
          <Button variant="ghost" size="sm" icon="refresh" onClick={() => setStamp((s) => s + 1)}>
            Refresh counts
          </Button>
        </div>

        <div className="tab-pane">
          {tab === "upload" && <UploadTab projectId={project.id} onDone={() => setStamp((s) => s + 1)} />}
          {tab === "documents" && <DocumentsTab project={project} onChanged={() => setStamp((s) => s + 1)} />}
          {tab === "requirements" && <RequirementsTab projectId={project.id} />}
          {tab === "traceability" && <TraceabilityTab projectId={project.id} />}
          {tab === "eval" && <EvalTab projectId={project.id} />}
        </div>
      </main>
    </div>
  );
}

function ChipSmall({ label, value }: { label: string; value: string }) {
  return (
    <span className="chip">
      <span className="faint">{label}</span>
      <span className="mono" style={{ color: "var(--text)" }}>
        {value}
      </span>
    </span>
  );
}
