import { useMemo, useRef, useState } from "react";
import { marked } from "marked";
import { api } from "../api";
import type { ProjectAnalysis } from "../types";
import { ProjectAnalyzerCard, ProjectAnalysisView } from "./ProjectAnalyzerCard";
import { Alert, Button, Card, Chip, Icon, Spinner, toast } from "./ui";

const DOC_TYPES = ["SRS", "SDD", "ICD", "STP", "STR"] as const;

const DOC_META: Record<
  string,
  { title: string; subtitle: string; tone: "cyan" | "teal" | "violet" | "amber" | "green"; badge: string }
> = {
  SRS: {
    title: "Software Requirements Specification",
    subtitle: "Functional & non-functional requirements grounded in source code or analysis.",
    tone: "cyan",
    badge: "Specification",
  },
  SDD: {
    title: "Software Design Description",
    subtitle: "Architectural decomposition, module specs, and component interface designs.",
    tone: "teal",
    badge: "Description",
  },
  ICD: {
    title: "Interface Control Document",
    subtitle: "External APIs, protocol schemas, I/O boundaries, and data format definitions.",
    tone: "violet",
    badge: "Document",
  },
  STP: {
    title: "Software Test Plan",
    subtitle: "Verification strategy, test cases, compliance matrix, and acceptance criteria.",
    tone: "amber",
    badge: "Plan",
  },
  STR: {
    title: "Software Test Report",
    subtitle: "Test execution results, coverage metrics, and compliance pass/fail verdict.",
    tone: "green",
    badge: "Report",
  },
};

// ─── Markdown Viewer ──────────────────────────────────────────────────────────

function cleanMarkdown(text: string): string {
  if (!text) return "";
  let s = text.trim();
  for (const fence of ["```markdown", "```md", "```"]) {
    if (s.startsWith(fence)) { s = s.slice(fence.length); break; }
  }
  if (s.endsWith("```")) s = s.slice(0, -3);
  return s.trim();
}

function MarkdownViewer({ content, onClose, onDownload }: { content: string; onClose: () => void; onDownload: () => void }) {
  const [mode, setMode] = useState<"rendered" | "raw">("rendered");
  const html = useMemo(() => {
    try { return marked.parse(cleanMarkdown(content), { gfm: true, breaks: true }) as string; }
    catch { return cleanMarkdown(content); }
  }, [content]);

  return (
    <div
      style={{
        marginTop: 16,
        border: "1px solid var(--border)",
        borderRadius: "var(--radius)",
        background: "var(--bg-card)",
        overflow: "hidden",
      }}
    >
      {/* Viewer toolbar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 16px",
          borderBottom: "1px solid var(--border)",
          background: "var(--bg-inset)",
        }}
      >
        <span style={{ fontWeight: 600, fontSize: 13 }}>Generated Document</span>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {/* Preview / Raw toggle */}
          <div
            style={{
              display: "flex",
              background: "var(--bg-card)",
              padding: 2,
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)",
            }}
          >
            {(["rendered", "raw"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                style={{
                  padding: "3px 10px",
                  borderRadius: 4,
                  border: "none",
                  background: mode === m ? "var(--accent)" : "transparent",
                  color: mode === m ? "#fff" : "var(--text-muted)",
                  fontSize: 12,
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                {m === "rendered" ? "Preview" : "Raw"}
              </button>
            ))}
          </div>
          <Button size="sm" variant="ghost" icon="copy" onClick={() => { navigator.clipboard.writeText(cleanMarkdown(content)); toast("Copied!", "success"); }}>
            Copy
          </Button>
          <Button size="sm" variant="primary" icon="download" onClick={onDownload}>
            Download
          </Button>
          <Button size="sm" variant="ghost" icon="x" onClick={onClose} />
        </div>
      </div>

      {/* Content */}
      {mode === "rendered" ? (
        <div
          className="markdown-body"
          style={{ padding: "18px 20px", maxHeight: 480, overflowY: "auto" }}
          dangerouslySetInnerHTML={{ __html: html }}
        />
      ) : (
        <pre
          style={{
            padding: "18px 20px",
            maxHeight: 480,
            overflowY: "auto",
            fontFamily: "var(--mono)",
            fontSize: 12.5,
            lineHeight: 1.65,
            whiteSpace: "pre-wrap",
            color: "var(--text)",
            margin: 0,
          }}
        >
          {cleanMarkdown(content)}
        </pre>
      )}
    </div>
  );
}

// ─── Generate Card ─────────────────────────────────────────────────────────────

function GenerateCard({
  projectId,
  docType,
  analysis,
  onDone,
}: {
  projectId: string;
  docType: string;
  analysis: ProjectAnalysis | null;
  onDone?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<{ tone: "info" | "error" | "success"; text: string } | null>(null);
  const [generatedDoc, setGeneratedDoc] = useState<string | null>(null);

  const meta = DOC_META[docType];
  const hasAnalysis = !!analysis;

  async function runRag() {
    setBusy(true); setState(null);
    try {
      const report = await api.generate(projectId, docType);
      setState({
        tone: report.compliance.status === "pass" ? "success" : "error",
        text: `v${report.version} · compliance ${report.compliance.status} · ${report.model_metadata.llm_client}`,
      });
      toast(`${docType} v${report.version} generated (RAG)`, report.compliance.status === "pass" ? "success" : "error");
      onDone?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ tone: "error", text: msg });
      toast(msg, "error");
    } finally { setBusy(false); }
  }

  async function runFromAnalysis() {
    if (!analysis) return;
    setBusy(true); setState(null); setGeneratedDoc(null);
    try {
      const result = await api.generateFromAnalysis(docType, analysis as unknown as Record<string, unknown>);
      setGeneratedDoc(result.content);
      setState({ tone: "success", text: `Generated in ${result.elapsed_s}s from project analysis` });
      toast(`${docType} generated from project analysis ✓`, "success");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setState({ tone: "error", text: msg });
      toast(msg, "error");
    } finally { setBusy(false); }
  }

  function download() {
    if (!generatedDoc) return;
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([cleanMarkdown(generatedDoc)], { type: "text/markdown" }));
    a.download = `${docType}.md`;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    toast(`${docType}.md downloaded`, "success");
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
      <div
        className="card card-hover"
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          padding: "16px 14px",
          borderRadius: "var(--radius-sm)",
        }}
      >
        {/* Header row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <strong style={{ fontFamily: "var(--mono)", fontSize: 17 }}>{docType}</strong>
          <Chip tone={meta.tone}>{meta.badge}</Chip>
        </div>

        <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)" }}>{meta.title}</div>
        <div className="faint" style={{ fontSize: 11.5, lineHeight: 1.5, flex: 1 }}>{meta.subtitle}</div>

        {/* Mode indicators */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <Chip tone="cyan">📄 RAG</Chip>
          {hasAnalysis && <Chip tone="violet">🔬 Analysis</Chip>}
        </div>

        {state && (
          <span style={{ fontSize: 11, fontFamily: "var(--mono)", color: state.tone === "error" ? "var(--danger)" : "var(--success)" }}>
            {state.text}
          </span>
        )}

        {/* Action buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
          {/* Primary: from Analysis if available, else RAG */}
          {hasAnalysis ? (
            <Button
              variant={busy ? "ghost" : "primary"}
              icon={busy ? undefined : "send"}
              disabled={busy}
              onClick={runFromAnalysis}
              style={{ width: "100%" }}
            >
              {busy ? <><Spinner /> Generating…</> : `⚡ Generate from Analysis`}
            </Button>
          ) : (
            <Button
              variant={busy ? "ghost" : "primary"}
              icon={busy ? undefined : "send"}
              disabled={busy}
              onClick={runRag}
              style={{ width: "100%" }}
            >
              {busy ? <><Spinner /> Generating…</> : `Generate ${docType}`}
            </Button>
          )}

          {/* Secondary: RAG button when analysis is available */}
          {hasAnalysis && (
            <Button
              variant="ghost"
              size="sm"
              icon="database"
              disabled={busy}
              onClick={runRag}
              style={{ width: "100%", fontSize: 12 }}
            >
              Generate via RAG (ingested docs)
            </Button>
          )}
        </div>
      </div>

      {/* Inline document viewer */}
      {generatedDoc && (
        <MarkdownViewer
          content={generatedDoc}
          onClose={() => setGeneratedDoc(null)}
          onDownload={download}
        />
      )}
    </div>
  );
}

// ─── Main Upload Tab ──────────────────────────────────────────────────────────

export default function UploadTab({ projectId, onDone }: { projectId: string; onDone?: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "error" | "success"; text: string } | null>(null);
  const [analysis, setAnalysis] = useState<ProjectAnalysis | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function addFiles(list: FileList | null) {
    if (!list) return;
    const next = Array.from(list);
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`));
      return [...prev, ...next.filter((f) => !seen.has(`${f.name}:${f.size}`))];
    });
  }

  async function upload() {
    if (files.length === 0) return;
    setBusy(true); setMessage(null);
    try {
      const response = await api.uploadFiles(projectId, files);
      const parts = response.ingested
        .map((r) => `${r.filename} → ${r.doc_type}${r.doc_type === "code" ? ` (${r.artifacts ?? 0} artifacts, ${r.chunks ?? 0} chunks)` : ` (${r.hash ?? ""})`}`)
        .join("\n");
      setMessage({ tone: "success", text: `Ingested ${response.ingested.length} source(s):\n${parts}` });
      toast(`Ingested ${response.ingested.length} source(s)`, "success");
      setFiles([]);
      onDone?.();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessage({ tone: "error", text: msg });
      toast(msg, "error");
    } finally { setBusy(false); }
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 28 }}>

      {/* ── Row 1: Ingest Sources + AI Analyzer side-by-side ── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, alignItems: "start" }}>

        {/* Left: Ingest Sources */}
        <Card title="Ingest sources" icon="upload" right={<Chip tone="cyan">Doc type auto-detected</Chip>}>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onClick={() => inputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files); }}
            style={{ minHeight: 168 }}
          >
            <div className="dz-icon"><Icon name="upload" size={34} /></div>
            <strong>Drop documents here, or click to browse</strong>
            <div className="faint" style={{ fontSize: 12, marginTop: 6 }}>
              MoM, SysRS, IRS (DOCX / PDF / TXT) and codebase ZIP.{" "}
              <span className="mono">*mom* · *sysrs* · *irs* · *.zip</span>
            </div>
          </div>
          <input ref={inputRef} type="file" multiple hidden onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} />

          {files.length > 0 && (
            <div className="file-list" style={{ marginTop: 12 }}>
              {files.map((file) => (
                <div className="file-row" key={`${file.name}:${file.size}`}>
                  <span className="muted"><Icon name="file" size={16} /></span>
                  <div className="file-meta">
                    <div className="file-name">{file.name}</div>
                    <div className="file-size">{Math.round(file.size / 1024)} KB</div>
                  </div>
                  <Button variant="ghost" size="sm" icon="x" onClick={() => setFiles((prev) => prev.filter((f) => f !== file))}>Remove</Button>
                </div>
              ))}
            </div>
          )}

          {message && (
            <div style={{ marginTop: 12 }}>
              <Alert tone={message.tone}>
                <pre style={{ margin: 0, fontSize: 12 }}>{message.text}</pre>
              </Alert>
            </div>
          )}

          <div className="row" style={{ marginTop: 16 }}>
            <Button variant="primary" icon="upload" disabled={busy || files.length === 0} onClick={upload}>
              {busy ? <><Spinner /> Ingesting…</> : "Upload & ingest"}
            </Button>
            {files.length > 0 && (
              <span className="faint" style={{ fontSize: 12 }}>{files.length} file{files.length === 1 ? "" : "s"} queued</span>
            )}
          </div>
        </Card>

        {/* Right: AI Project Analyzer & 17-Section Engine */}
        <ProjectAnalyzerCard
          onAnalyze={async (file) => {
            const res = await api.analyzeProject(file);
            setAnalysis(res);
          }}
        />
      </div>

      {/* ── Analysis Results Inline ── */}
      {analysis && (
        <ProjectAnalysisView analysis={analysis} onClose={() => setAnalysis(null)} />
      )}

      {/* ── Row 2: SDLC Document Generation ── */}
      <Card
        title="Generate official SDLC documents"
        icon="sparkles"
        right={
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {analysis && (
              <Chip tone="violet">🔬 Analysis context loaded</Chip>
            )}
            <Chip tone={analysis ? "green" : "neutral"}>
              {analysis ? "2 generation modes" : "RAG-grounded"}
            </Chip>
          </div>
        }
      >
        {analysis && (
          <div
            style={{
              marginBottom: 16,
              padding: "10px 14px",
              background: "rgba(99,102,241,.08)",
              border: "1px solid rgba(99,102,241,.25)",
              borderRadius: "var(--radius-sm)",
              fontSize: 13,
              color: "var(--text-muted)",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <Icon name="checkCircle" size={16} style={{ color: "var(--success)", flexShrink: 0 }} />
            <span>
              <strong style={{ color: "var(--text)" }}>Project analysis loaded.</strong>{" "}
              Each document can be generated from the AI analysis context <em>(recommended)</em> or
              from RAG-indexed ingested documents.
            </span>
          </div>
        )}

        <div className="grid grid-5" style={{ gap: 16 }}>
          {DOC_TYPES.map((docType) => (
            <GenerateCard
              key={docType}
              projectId={projectId}
              docType={docType}
              analysis={analysis}
              onDone={onDone}
            />
          ))}
        </div>
      </Card>
    </div>
  );
}
