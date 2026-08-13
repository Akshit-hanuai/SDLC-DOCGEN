import { useEffect, useState } from "react";
import { api } from "../api";
import type { DocumentDetail, DocumentSummary, VersionDetail } from "../types";
import { Alert, Button, Card, Chip, Icon, Spinner, toast } from "./ui";

const STATUS_TONES: Record<string, "neutral" | "green" | "amber" | "red"> = {
  draft: "neutral",
  in_review: "amber",
  changes_requested: "red",
  approved: "green",
};

export default function DocumentEditor({
  document,
  onBack,
  onChanged,
}: {
  document: DocumentSummary;
  onBack: () => void;
  onChanged: () => void;
}) {
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [version, setVersion] = useState<VersionDetail | null>(null);
  const [activeVersion, setActiveVersion] = useState(0);
  const [diff, setDiff] = useState<string[]>([]);
  const [username, setUsername] = useState("reviewer-demo");
  const [message, setMessage] = useState<{ tone: "info" | "error" | "success"; text: string } | null>(null);

  async function refresh() {
    const loaded = await api.document(document.id);
    setDetail(loaded);
    const versionData = await api.version(document.id, loaded.current_version);
    setVersion(versionData);
    setActiveVersion(loaded.current_version);
    try {
      const diffResult = await api.diff(document.id, loaded.current_version);
      setDiff(diffResult.changes.filter((c) => c.changed).map((c) => `${c.section_id} (${c.action})`));
    } catch {
      setDiff([]);
    }
  }

  useEffect(() => {
    refresh();
  }, [document.id]);

  async function loadVersion(v: number) {
    try {
      setVersion(await api.version(document.id, v));
      setActiveVersion(v);
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof Error ? e.message : String(e) });
    }
  }

  async function run(action: () => Promise<unknown>) {
    setMessage(null);
    try {
      const result = await action();
      setMessage({ tone: "success", text: JSON.stringify(result).slice(0, 400) });
      toast("Action completed", "success");
      await refresh();
      onChanged();
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof Error ? e.message : String(e) });
      toast(e instanceof Error ? e.message : String(e), "error");
    }
  }

  if (!detail || !version) {
    return (
      <div className="center">
        <Spinner large />
      </div>
    );
  }

  const compliance = (version.content._compliance || {}) as Record<string, unknown>;
  const compliancePass = compliance.status === "pass";
  const modelName = String((version.model_metadata as Record<string, unknown> | null | undefined)?.llm_client || "—");
  const sections = version.content.sections || {};
  const evidence = version.content._evidence || {};

  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <Button variant="ghost" size="sm" icon="arrowLeft" onClick={onBack}>
          Documents
        </Button>
        <div className="row">
          <Chip tone={STATUS_TONES[detail.status] || "neutral"} dot>
            {detail.status}
          </Chip>
          <Button variant="success" size="sm" icon="check" onClick={() => run(() => api.approve(document.id, username))}>
            Approve (baseline)
          </Button>
          <Button variant="primary" size="sm" icon="send" onClick={() => run(() => api.submit(document.id, username))}>
            Submit for review
          </Button>
        </div>
      </div>

      <div className="doc-hero">
        <span
          style={{
            display: "grid",
            placeItems: "center",
            width: 52,
            height: 52,
            borderRadius: 14,
            background: "var(--accent-soft)",
            color: "var(--accent)",
          }}
        >
          <Icon name="filetext" size={26} />
        </span>
        <div className="grow">
          <h2 className="doc-title">
            {document.doc_type}{" "}
            <span className="faint" style={{ fontWeight: 700 }}>
              v{activeVersion}
            </span>
          </h2>
          <div className="faint" style={{ fontSize: 13 }}>
            {document.title}
          </div>
        </div>
        <div className="kv" style={{ gridTemplateColumns: "auto 1fr", marginLeft: "auto" }}>
          <dt>git</dt>
          <dd className="mono">{detail.versions.find((v) => v.version === activeVersion)?.git_commit_sha || "—"}</dd>
          <dt>model</dt>
          <dd className="mono">{modelName}</dd>
        </div>
      </div>

      {message && (
        <Alert tone={message.tone}>
          <pre>{message.text}</pre>
        </Alert>
      )}

      <Card title="Review controls" icon="git">
        <div className="row">
          <span className="faint" style={{ fontSize: 12.5 }}>
            Reviewer
          </span>
          <input
            className="input"
            style={{ width: 180 }}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <span className="faint" style={{ fontSize: 12.5 }}>
            Approving creates a signed baseline tag; submitting moves the document to <em>in_review</em>.
          </span>
        </div>
      </Card>

      {diff.length > 0 && (
        <Card title="Changed since previous version" icon="activity">
          <div className="row">
            {diff.map((change) => (
              <Chip key={change} tone="amber">
                {change}
              </Chip>
            ))}
          </div>
        </Card>
      )}

      <Card title="Compliance report" icon="shield">
        <div className="row" style={{ marginBottom: 10 }}>
          <Chip tone={compliancePass ? "green" : "red"} dot>
            {String(compliance.status)}
          </Chip>
          <span className="faint" style={{ fontSize: 12.5 }}>
            Every requirement referenced by the document must be real and present in the registry.
          </span>
        </div>
        <div className="kv" style={{ gridTemplateColumns: "auto 1fr" }}>
          <dt>missing refs</dt>
          <dd>{(compliance.missing_requirement_references as string[] | undefined || []).length}</dd>
          <dt>missing sections</dt>
          <dd>{(compliance.missing_sections as string[] | undefined || []).join(", ") || "—"}</dd>
          <dt>uncovered reqs</dt>
          <dd>{(compliance.uncovered_requirements as string[] | undefined || []).length}</dd>
        </div>
      </Card>

      <Card title={`Sections (${Object.keys(sections).length})`} icon="layers">
        <div className="stack">
          {Object.entries(sections).map(([sectionId, section]) => (
            <SectionCard
              key={sectionId}
              document={document}
              currentVersion={activeVersion}
              sectionId={sectionId}
              section={section as Record<string, unknown>}
              evidence={evidence[sectionId] as Record<string, unknown[]> | undefined}
              username={username}
              onAction={run}
            />
          ))}
        </div>
      </Card>

      <Card title="Versions" icon="clock">
        <div className="version-timeline">
          {[...detail.versions]
            .reverse()
            .map((v) => (
              <div
                key={v.version}
                className={`vt-row ${v.version === activeVersion ? "active" : ""}`}
                onClick={() => loadVersion(v.version)}
              >
                <span className={`vt-dot ${v.status}`} />
                <strong className="mono" style={{ fontSize: 13 }}>
                  v{v.version}
                </strong>
                <Chip tone={STATUS_TONES[v.status] || "neutral"}>{v.status}</Chip>
                <span className="mono faint grow" style={{ fontSize: 11.5, overflow: "hidden", textOverflow: "ellipsis" }}>
                  {v.git_commit_sha}
                </span>
                <span className="faint" style={{ fontSize: 11.5 }}>
                  {String((v.model_metadata as Record<string, unknown> | null | undefined)?.llm_client || "")}
                </span>
              </div>
            ))}
        </div>
      </Card>
    </div>
  );
}

function SectionCard({
  sectionId,
  section,
  evidence,
  username,
  onAction,
  document,
  currentVersion,
}: {
  sectionId: string;
  section: Record<string, unknown>;
  evidence?: Record<string, unknown[]>;
  username: string;
  onAction: (action: () => Promise<unknown>) => Promise<void>;
  document: DocumentSummary;
  currentVersion: number;
}) {
  const [open, setOpen] = useState(false);
  const [feedback, setFeedback] = useState("");
  const [targetField, setTargetField] = useState<string>("");

  const fields = Object.entries(section);
  const textFieldIds = fields.filter(([, value]) => typeof value === "string").map(([id]) => id);
  const activeField = targetField || textFieldIds[0] || "";

  return (
    <div className="section-card">
      <div className="sc-head" onClick={() => setOpen((o) => !o)}>
        <Icon name={open ? "chevronDown" : "chevronRight"} size={16} className="faint" />
        <span className="sc-title">Section {sectionId}</span>
        <span className="grow" />
        {evidence && <span className="faint" style={{ fontSize: 11.5 }}>{Object.keys(evidence).length} evidence groups</span>}
        <Chip tone={open ? "cyan" : "neutral"}>{open ? "open" : "collapsed"}</Chip>
      </div>
      {open && (
        <div className="sc-body">
          {fields.map(([fieldId, value]) => (
            <div key={fieldId} style={{ marginBottom: 16 }}>
              <div
                className="faint"
                style={{ fontSize: 11.5, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}
              >
                {fieldId}
              </div>
              {Array.isArray(value) ? (
                <div className="table-wrap">
                  <table className="data">
                    <thead>
                      <tr>
                        {Object.keys(value[0] as Record<string, unknown> || {}).map((key) => (
                          <th key={key}>{key}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {(value as Record<string, unknown>[]).map((row, index) => (
                        <tr key={index}>
                          {Object.entries(row).map(([key, cell]) => (
                            <td key={key}>
                              <span className="faint" style={{ fontSize: 11.5 }}>
                                {key}:{" "}
                              </span>
                              {String(cell)}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div style={{ whiteSpace: "pre-wrap", fontSize: 13.5, color: "var(--text-muted)" }}>{String(value)}</div>
              )}
              {evidence?.[fieldId] && (
                <div className="evidence">
                  <div className="faint" style={{ marginBottom: 6 }}>
                    evidence · {evidence[fieldId].length} chunks
                  </div>
                  {evidence[fieldId].map((hit, index) => (
                    <div key={index} style={{ marginBottom: 3 }}>
                      <span style={{ color: "var(--accent)" }}>[{String((hit as { source?: string }).source)}]</span>{" "}
                      {(hit as { source_file?: string }).source_file} — {(hit as { heading?: string }).heading}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}

          <div className="stack" style={{ marginTop: 4, gap: 8 }}>
            <div className="row" style={{ gap: 8 }}>
              <select
                className="input"
                style={{ width: 240 }}
                value={activeField}
                onChange={(e) => setTargetField(e.target.value)}
                title="Field where inserted content should land"
              >
                {textFieldIds.length === 0 && <option value="">(no text fields)</option>}
                {textFieldIds.map((id) => (
                  <option key={id} value={id}>
                    Insert into: {id}
                  </option>
                ))}
              </select>
              <input
                className="input grow"
                placeholder="Review comment (required for reject / regenerate)"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
              />
            </div>
            <div className="row" style={{ gap: 8 }}>
              <Button
                variant="success"
                size="sm"
                icon="check"
                onClick={() => onAction(() => api.reviewSection(document.id, currentVersion, sectionId, username, "approved", feedback || undefined))}
              >
                Approve section
              </Button>
              <Button
                variant="danger"
                size="sm"
                icon="x"
                onClick={() => onAction(() => api.reviewSection(document.id, currentVersion, sectionId, username, "rejected", feedback))}
              >
                Reject
              </Button>
              <Button
                variant="primary"
                size="sm"
                icon="refresh"
                onClick={() =>
                  onAction(() =>
                    api.regenerateSection(
                      document.id,
                      currentVersion,
                      sectionId,
                      feedback,
                      activeField || undefined
                    )
                  )
                }
              >
                Regenerate (insert into {activeField || "field"})
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
