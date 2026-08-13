import { useRef, useState } from "react";
import { api } from "../api";
import { Alert, Button, Card, Chip, Icon, Spinner, toast } from "./ui";

const DOC_TYPES = ["SRS", "SDD", "ICD", "STP", "STR"] as const;
const DOC_TITLES: Record<string, string> = {
  SRS: "Software Requirements Specification",
  SDD: "Software Design Description",
  ICD: "Interface Control Document",
  STP: "Software Test Plan",
  STR: "Software Test Report",
};

export default function UploadTab({ projectId, onDone }: { projectId: string; onDone?: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [message, setMessage] = useState<{ tone: "info" | "error" | "success"; text: string } | null>(null);
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
    setBusy(true);
    setMessage(null);
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
      setMessage({ tone: "error", text: e instanceof Error ? e.message : String(e) });
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack">
      <Card title="Ingest sources" icon="upload" right={<Chip tone="cyan">Doc type auto-detected</Chip>}>
        <div
          className={`dropzone ${dragging ? "dragging" : ""}`}
          onClick={() => inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            addFiles(e.dataTransfer.files);
          }}
        >
          <div className="dz-icon">
            <Icon name="upload" size={34} />
          </div>
          <strong>Drop documents here, or click to browse</strong>
          <div className="faint" style={{ fontSize: 12.5, marginTop: 4 }}>
            MoM, SysRS, IRS (DOCX / PDF / TXT) and a codebase ZIP.{" "}
            <span className="mono">*mom* · *sysrs* · *irs* · *.zip</span>
          </div>
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          hidden
          onChange={(e) => {
            addFiles(e.target.files);
            e.target.value = "";
          }}
        />

        {files.length > 0 && (
          <div className="file-list">
            {files.map((file) => (
              <div className="file-row" key={`${file.name}:${file.size}`}>
                <span className="muted">
                  <Icon name="file" size={17} />
                </span>
                <div className="file-meta">
                  <div className="file-name">{file.name}</div>
                  <div className="file-size">{Math.round(file.size / 1024)} KB</div>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon="x"
                  onClick={() => setFiles((prev) => prev.filter((f) => f !== file))}
                >
                  Remove
                </Button>
              </div>
            ))}
          </div>
        )}

        {message && (
          <Alert tone={message.tone}>
            <pre>{message.text}</pre>
          </Alert>
        )}

        <div className="row" style={{ marginTop: 16 }}>
          <Button variant="primary" icon="upload" disabled={busy || files.length === 0} onClick={upload}>
            {busy ? (
              <>
                <Spinner /> Ingesting…
              </>
            ) : (
              "Upload & ingest"
            )}
          </Button>
          {files.length > 0 && (
            <span className="faint" style={{ fontSize: 12.5 }}>
              {files.length} file{files.length === 1 ? "" : "s"} queued
            </span>
          )}
        </div>
      </Card>

      <Card title="Generate documents" icon="sparkles" right={<Chip tone="violet">Qwen · RAG-grounded</Chip>}>
        <div className="grid grid-4">
          {DOC_TYPES.map((docType) => (
            <GenerateCard key={docType} projectId={projectId} docType={docType} onDone={onDone} />
          ))}
        </div>
      </Card>
    </div>
  );
}

function GenerateCard({
  projectId,
  docType,
  onDone,
}: {
  projectId: string;
  docType: string;
  onDone?: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [state, setState] = useState<{ tone: "info" | "error" | "success"; text: string } | null>(null);

  async function run() {
    setBusy(true);
    setState(null);
    try {
      const report = await api.generate(projectId, docType);
      setState({
        tone: report.compliance.status === "pass" ? "success" : "error",
        text: `v${report.version} · compliance ${report.compliance.status} · llm ${report.model_metadata.llm_client}`,
      });
      toast(
        `${docType} v${report.version} generated · compliance ${report.compliance.status}`,
        report.compliance.status === "pass" ? "success" : "error"
      );
      onDone?.();
    } catch (e) {
      setState({ tone: "error", text: e instanceof Error ? e.message : String(e) });
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card card-hover" style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong style={{ fontFamily: "var(--mono)", fontSize: 16 }}>{docType}</strong>
        <Chip tone={docType === "SRS" ? "cyan" : "teal"}>{DOC_TITLES[docType].split(" ").slice(-1)[0]}</Chip>
      </div>
      <div className="faint" style={{ fontSize: 12, flex: 1 }}>
        {DOC_TITLES[docType]}
      </div>
      {state && (
        <span
          className="faint"
          style={{
            fontSize: 11.5,
            fontFamily: "var(--mono)",
            color: state.tone === "error" ? "var(--danger)" : "var(--success)",
          }}
        >
          {state.text}
        </span>
      )}
      <Button variant={busy ? "ghost" : "primary"} icon={busy ? undefined : "send"} disabled={busy} onClick={run}>
        {busy ? (
          <>
            <Spinner /> Generating
          </>
        ) : (
          `Generate ${docType}`
        )}
      </Button>
    </div>
  );
}
