import { useEffect, useState } from "react";
import { api } from "../api";
import type { EvalReport } from "../types";
import { Alert, Button, Card, Chip, EmptyState, Icon, Progress, Spinner, Stat, toast } from "./ui";

function pct(value: number): string {
  return `${(value * 100).toFixed(0)}%`;
}

export default function EvalTab({ projectId }: { projectId: string }) {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function refresh() {
    try {
      setReport(await api.evalReport(projectId));
    } catch {
      setReport(null);
    }
  }

  useEffect(() => {
    refresh();
  }, [projectId]);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setReport(await api.runEval(projectId));
      toast("Evaluation completed", "success");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      setRunning(false);
    }
  }

  return (
    <Card
      title="Evaluation"
      icon="flask"
      right={
        <Button variant="primary" size="sm" icon="activity" disabled={running} onClick={run}>
          {running ? (
            <>
              <Spinner /> Running…
            </>
          ) : (
            "Run evaluation"
          )}
        </Button>
      }
    >
      {error && <Alert tone="error">{error}</Alert>}

      {!report ? (
        <EmptyState
          icon="flask"
          title="No evaluation report yet"
          body="Run the evaluation to measure requirement coverage, traceability completeness, template conformance and cross-document consistency."
        />
      ) : (
        <div className="stack">
          <div className="stats" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))" }}>
            <Stat icon="link" value={report.traceability.links} label="Links" tone="violet" />
            <Stat icon="xCircle" value={report.traceability.dangling} label="Dangling" tone="red" />
            <Stat icon="target" value={pct(report.traceability.completeness)} label="Completeness" tone="teal" />
            <Stat icon="list" value={report.requirements.real} label="Real reqs" tone="cyan" />
          </div>

          <Card title="Document metrics" icon="filetext">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Doc</th>
                    <th>Coverage</th>
                    <th>Conformance</th>
                    <th>Compliance</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.documents).map(([docType, metrics]) => (
                    <tr key={docType}>
                      <td className="mono" style={{ fontWeight: 600, color: "var(--accent)", whiteSpace: "nowrap" }}>
                        {docType}
                      </td>
                      <td style={{ minWidth: 140 }}>
                        <div className="row" style={{ gap: 8 }}>
                          <Progress
                            value={metrics.covered}
                            max={metrics.total_requirements}
                            tone={metrics.covered >= metrics.total_requirements ? "green" : "amber"}
                          />
                          <span className="tnum faint" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                            {metrics.covered}/{metrics.total_requirements}
                          </span>
                        </div>
                      </td>
                      <td style={{ minWidth: 140 }}>
                        <div className="row" style={{ gap: 8 }}>
                          <Progress
                            value={metrics.sections_present}
                            max={metrics.sections_expected}
                            tone={metrics.sections_present >= metrics.sections_expected ? "green" : "amber"}
                          />
                          <span className="tnum faint" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                            {metrics.sections_present}/{metrics.sections_expected}
                          </span>
                        </div>
                      </td>
                      <td>
                        <Chip tone={metrics.compliance_status === "pass" ? "green" : "red"} dot>
                          {metrics.compliance_status}
                        </Chip>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card title="Cross-document consistency" icon="link">
            {Object.entries(report.cross_document_consistency).length === 0 ? (
              <div className="muted" style={{ fontSize: 13 }}>
                Only one document exists — no pairs to compare.
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data">
                  <thead>
                    <tr>
                      <th>Pair</th>
                      <th>Shared ids</th>
                      <th>Jaccard</th>
                      <th>Similarity</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(report.cross_document_consistency).map(([pair, metrics]) => (
                      <tr key={pair}>
                        <td className="mono" style={{ whiteSpace: "nowrap" }}>
                          {pair}
                        </td>
                        <td className="tnum">{metrics.overlap}</td>
                        <td className="tnum">{metrics.jaccard.toFixed(3)}</td>
                        <td style={{ minWidth: 130 }}>
                          <div className="row" style={{ gap: 8 }}>
                            <Progress value={metrics.jaccard} tone={metrics.jaccard > 0.5 ? "green" : "amber"} />
                            <span className="tnum faint" style={{ fontSize: 12, whiteSpace: "nowrap" }}>
                              {pct(metrics.jaccard)}
                            </span>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          <Card title="Similarity vs source (ROUGE / BERTScore-like)" icon="scale">
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Doc</th>
                    <th>ROUGE-1</th>
                    <th>ROUGE-2</th>
                    <th>ROUGE-L</th>
                    <th>BERTScore-like</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.similarity).map(([docType, metrics]) => (
                    <tr key={docType}>
                      <td className="mono" style={{ fontWeight: 600, color: "var(--accent)", whiteSpace: "nowrap" }}>
                        {docType}
                      </td>
                      <td className="tnum">{pct(metrics.rouge1)}</td>
                      <td className="tnum">{pct(metrics.rouge2)}</td>
                      <td className="tnum">{pct(metrics.rougeL)}</td>
                      <td className="tnum">{pct(metrics.bertscore_like_f1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="row" style={{ justifyContent: "flex-end" }}>
            <a
              className="btn btn-ghost btn-sm"
              href={`/api/v1/projects/${projectId}/eval/scoring-sheet.csv`}
              target="_blank"
              rel="noreferrer"
            >
              <Icon name="download" size={15} />
              Download human-review scoring sheet (CSV)
            </a>
          </div>
        </div>
      )}
    </Card>
  );
}
