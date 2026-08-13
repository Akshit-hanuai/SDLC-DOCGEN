import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { RequirementRow } from "../types";
import { Alert, Button, Card, Chip, EmptyState, Icon, Spinner } from "./ui";

const TYPE_TONES: Record<string, "cyan" | "teal" | "violet" | "amber" | "green" | "red"> = {
  functional: "cyan",
  non_functional: "teal",
  interface: "violet",
  constraint: "amber",
  code_artifact: "green",
  test_case: "red",
};

export default function RequirementsTab({ projectId }: { projectId: string }) {
  const [rows, setRows] = useState<RequirementRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("all");
  const [type, setType] = useState("all");

  useEffect(() => {
    setLoading(true);
    api
      .requirements(projectId)
      .then((r) => setRows(r.requirements))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [projectId]);

  const sources = useMemo(() => ["all", ...Array.from(new Set(rows.map((r) => r.source)))], [rows]);
  const types = useMemo(() => ["all", ...Array.from(new Set(rows.map((r) => r.req_type)))], [rows]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return rows.filter((row) => {
      if (source !== "all" && row.source !== source) return false;
      if (type !== "all" && row.req_type !== type) return false;
      if (!q) return true;
      return (
        row.req_id.toLowerCase().includes(q) ||
        row.text.toLowerCase().includes(q) ||
        row.context.toLowerCase().includes(q)
      );
    });
  }, [rows, query, source, type]);

  return (
    <div className="stack">
      <Card
        title={`Requirements registry (${filtered.length}/${rows.length})`}
        icon="list"
        right={
          <div className="row" style={{ gap: 8 }}>
            <input
              className="input"
              style={{ width: 220 }}
              placeholder="Search id / text / context…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select className="select" value={source} onChange={(e) => setSource(e.target.value)}>
              {sources.map((s) => (
                <option key={s} value={s}>
                  {s === "all" ? "All sources" : s}
                </option>
              ))}
            </select>
            <select className="select" value={type} onChange={(e) => setType(e.target.value)}>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t === "all" ? "All types" : t}
                </option>
              ))}
            </select>
            <Button variant="ghost" size="sm" icon="refresh" onClick={() => setError(null)} />
          </div>
        }
      >
        {loading ? (
          <div className="center">
            <Spinner large />
          </div>
        ) : error ? (
          <Alert tone="error">{error}</Alert>
        ) : rows.length === 0 ? (
          <EmptyState icon="list" title="Registry is empty" body="Ingest SysRS / IRS / MoM sources to populate the requirement registry." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Source</th>
                  <th>Type</th>
                  <th>Requirement</th>
                  <th>Context</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((row) => (
                  <tr key={row.req_id}>
                    <td className="mono" style={{ color: "var(--accent)", fontWeight: 600, whiteSpace: "nowrap" }}>
                      {row.req_id}
                    </td>
                    <td>
                      <Chip>{row.source}</Chip>
                    </td>
                    <td>
                      <Chip tone={TYPE_TONES[row.req_type] || "neutral"}>{row.req_type}</Chip>
                    </td>
                    <td style={{ maxWidth: 480 }}>{row.text}</td>
                    <td className="faint" style={{ maxWidth: 260, fontSize: 12 }}>
                      {row.context || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <div className="row" style={{ justifyContent: "flex-end" }}>
        <span className="faint" style={{ fontSize: 12.5 }}>
          <Icon name="info" size={13} /> Requirements are stored in the Postgres registry; generated docs reproduce them verbatim.
        </span>
      </div>
    </div>
  );
}
