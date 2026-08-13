import { useEffect, useState } from "react";
import { api } from "./api";
import type { Project } from "./types";
import ProjectPage from "./components/ProjectPage";
import { Alert, Button, Card, Chip, EmptyState, Icon, toast } from "./components/ui";

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function DeleteButton({
  busy,
  confirming,
  onRequest,
  onCancel,
  onConfirm,
}: {
  busy: boolean;
  confirming: boolean;
  onRequest: () => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  return (
    <span
      onClick={(e) => e.stopPropagation()}
      style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
    >
      {confirming ? (
        <>
          <span className="faint" style={{ fontSize: 11.5, color: "var(--danger)" }}>
            Delete this project?
          </span>
          <Button variant="danger" size="sm" disabled={busy} onClick={onConfirm}>
            {busy ? "Deleting…" : "Delete"}
          </Button>
          <Button variant="ghost" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        </>
      ) : (
        <Button
          variant="ghost"
          size="icon"
          icon="x"
          title="Delete project"
          onClick={onRequest}
          style={{ color: "var(--text-faint)" }}
        />
      )}
    </span>
  );
}

export default function App() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [active, setActive] = useState<Project | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [health, setHealth] = useState<{ status: string; app: string; version: string } | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<string | null>(null);


  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
    refresh();
  }, []);

  async function refresh() {
    try {
      setProjects(await api.listProjects());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function create() {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const project = await api.createProject(name.trim(), description || undefined);
      setName("");
      setDescription("");
      await refresh();
      toast(`Project "${project.name}" created`, "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  async function removeProject(projectId: string) {
    setDeleting(projectId);
    setError(null);
    try {
      await api.deleteProject(projectId);
      setConfirming(null);
      await refresh();
      toast("Project deleted", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setDeleting(null);
    }
  }

  if (active) {
    return <ProjectPage project={active} onBack={() => setActive(null)} />;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand" onClick={() => setActive(null)}>
          <div className="brand-mark">
            <Icon name="shield" size={22} />
          </div>
          <div className="brand-name">
            SDLC DocGen
            <small>Document Automation &middot; Defence R&amp;D</small>
          </div>
        </div>
        <div className="topbar-spacer" />
        {health ? (
          <Chip tone="green" dot title="Backend status">
            {health.app} v{health.version}
          </Chip>
        ) : (
          <Chip tone="red" dot title="Backend status">
            backend unreachable
          </Chip>
        )}
      </header>

      <main className="container fade-in">
        <div className="hero-grid">
          <div>
            <h1 className="page-title" style={{ fontSize: 30 }}>
              Automated SDLC document generation
            </h1>
            <p className="page-subtitle">
              Ingest SysRS, IRS, MoM and codebase sources to produce grounded, version-controlled and
              reviewable SRS / SDD / ICD / STP / STR documents — fully air-gapped.
            </p>
            <div className="row" style={{ marginTop: 18, color: "var(--text-faint)", fontSize: 12.5 }}>
              <Chip tone="cyan">RAG-grounded</Chip>
              <Chip tone="violet">Review workflow</Chip>
              <Chip tone="teal">Git baseline</Chip>
            </div>
          </div>

          <Card title="Create project" icon="plus">
            <div className="field">
              <label htmlFor="proj-name">Project name</label>
              <input
                id="proj-name"
                className="input"
                placeholder="e.g. telemetry-acquisition"
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && create()}
              />
            </div>
            <div className="field">
              <label htmlFor="proj-desc">Description (optional)</label>
              <input
                id="proj-desc"
                className="input"
                placeholder="What is being documented?"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && create()}
              />
            </div>
            <Button variant="primary" icon="send" disabled={busy || !name.trim()} onClick={create} style={{ width: "100%" }}>
              {busy ? "Creating…" : "Create project"}
            </Button>
          </Card>
        </div>




        {error && (
          <Alert tone="error">
            <strong>Error:</strong> {error}
          </Alert>
        )}



        <section className="section-block" style={{ marginTop: 32 }}>
          <div className="section-head">
            <h2>Projects</h2>
            <div className="row">
              <span className="hint">
                {projects.length} project{projects.length === 1 ? "" : "s"}
              </span>
              <Button size="sm" variant="ghost" icon="refresh" onClick={refresh}>
                Refresh
              </Button>
            </div>
          </div>

          {projects.length === 0 ? (
            <Card>
              <EmptyState
                icon="folder"
                title="No projects yet"
                body="Create a project above to begin ingesting sources and generating documents."
              />
            </Card>
          ) : (
            <div className="grid grid-2">
              {projects.map((project) => (
                <div key={project.id} className="card card-hover project-card" onClick={() => setActive(project)}>
                  <div className="pc-top">
                    <h3 className="pc-title" style={{ fontFamily: "var(--mono)", fontSize: 15 }}>
                      {project.name}
                    </h3>
                    <div className="row" style={{ gap: 8 }}>
                      <Chip tone={project.status === "active" ? "green" : "neutral"} dot>
                        {project.status}
                      </Chip>
                      <DeleteButton
                        busy={deleting === project.id}
                        confirming={confirming === project.id}
                        onRequest={() => setConfirming(project.id)}
                        onCancel={() => setConfirming(null)}
                        onConfirm={() => removeProject(project.id)}
                      />
                    </div>
                  </div>
                  <p className="pc-desc">{project.description || "No description."}</p>
                  <div className="pc-foot">
                    <span className="mono" style={{ fontSize: 11.5 }}>
                      {project.id.slice(0, 8)}…
                    </span>
                    <span>{formatDate(project.created_at)}</span>
                  </div>
                  <Button variant="ghost" size="sm" icon="arrowRight">
                    Open workspace
                  </Button>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

