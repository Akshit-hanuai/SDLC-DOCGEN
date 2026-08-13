import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { TraceLink } from "../types";
import { Alert, Card, Chip, EmptyState, Spinner } from "./ui";

const LINK_TONES: Record<string, "cyan" | "teal" | "violet" | "amber" | "green"> = {
  refines: "cyan",
  derives: "violet",
  traces_to: "teal",
  implements: "green",
  verifies: "amber",
};

export default function TraceabilityTab({ projectId }: { projectId: string }) {
  const [links, setLinks] = useState<TraceLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [linkType, setLinkType] = useState("all");
  const [query, setQuery] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .traceability(projectId)
      .then((r) => setLinks(r.links))
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [projectId]);

  const types = useMemo(() => ["all", ...Array.from(new Set(links.map((l) => l.link_type)))], [links]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return links.filter((link) => {
      if (linkType !== "all" && link.link_type !== linkType) return false;
      if (!q) return true;
      return (
        link.from.toLowerCase().includes(q) ||
        link.to.toLowerCase().includes(q) ||
        link.source.toLowerCase().includes(q)
      );
    });
  }, [links, linkType, query]);

  return (
    <div className="stack">
      <Card
        title={`Traceability links (${filtered.length}/${links.length})`}
        icon="link"
        right={
          <div className="row" style={{ gap: 8 }}>
            <input
              className="input"
              style={{ width: 200 }}
              placeholder="Filter by id…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select className="select" value={linkType} onChange={(e) => setLinkType(e.target.value)}>
              {types.map((t) => (
                <option key={t} value={t}>
                  {t === "all" ? "All link types" : t}
                </option>
              ))}
            </select>
          </div>
        }
      >
        {loading ? (
          <div className="center">
            <Spinner large />
          </div>
        ) : error ? (
          <Alert tone="error">{error}</Alert>
        ) : links.length === 0 ? (
          <EmptyState icon="link" title="No traceability links" body="Links are proposed during ingestion by the linker and refined by generation." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr>
                  <th>From</th>
                  <th></th>
                  <th>To</th>
                  <th>Link type</th>
                  <th>Source</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((link, index) => (
                  <tr key={`${link.from}-${link.to}-${index}`}>
                    <td className="mono" style={{ color: "var(--accent)", fontWeight: 600, whiteSpace: "nowrap" }}>
                      {link.from}
                    </td>
                    <td style={{ color: "var(--text-faint)" }}>⟶</td>
                    <td className="mono" style={{ fontWeight: 600, whiteSpace: "nowrap" }}>
                      {link.to}
                    </td>
                    <td>
                      <Chip tone={LINK_TONES[link.link_type] || "neutral"}>{link.link_type}</Chip>
                    </td>
                    <td className="faint">{link.source}</td>
                    <td className="tnum" style={{ whiteSpace: "nowrap" }}>
                      {link.confidence != null ? `${(link.confidence * 100).toFixed(0)}%` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
