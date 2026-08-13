import { useState, useMemo, useEffect, useRef } from "react";
import { marked } from "marked";
import type { ProjectAnalysis } from "../types";
import { Button, Card, Chip, Icon, toast } from "./ui";

// ─── Clean Markdown Helper & Renderer ─────────────────────────────────────────

function cleanMarkdown(text: string): string {
  if (!text) return "";
  let str = text.trim();
  if (str.startsWith("```markdown")) {
    str = str.slice(11);
  } else if (str.startsWith("```markdown")) {
    str = str.slice(11);
  } else if (str.startsWith("```md")) {
    str = str.slice(5);
  } else if (str.startsWith("```")) {
    str = str.slice(3);
  }
  if (str.endsWith("```")) {
    str = str.slice(0, -3);
  }
  return str.trim();
}

function MermaidBlock({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function renderMermaid() {
      try {
        const mermaidModule = await import("mermaid");
        const mermaid = mermaidModule.default;
        mermaid.initialize({
          startOnLoad: false,
          theme: "dark",
          securityLevel: "loose",
          fontFamily: "Inter, system-ui, sans-serif",
        });
        const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`;
        const { svg: renderedSvg } = await mermaid.render(id, chart.trim());
        if (active) {
          setSvg(renderedSvg);
          setErr(null);
        }
      } catch (e) {
        if (active) {
          setErr(e instanceof Error ? e.message : String(e));
        }
      }
    }
    renderMermaid();
    return () => {
      active = false;
    };
  }, [chart]);

  if (err) {
    return (
      <div style={{ marginTop: 12 }}>
        <div style={{ fontSize: 11.5, color: "var(--warning)", marginBottom: 6, fontWeight: 600 }}>
          📊 Diagram Code (Mermaid):
        </div>
        <pre
          style={{
            fontFamily: "var(--mono)",
            fontSize: 12,
            background: "var(--bg-inset)",
            padding: 14,
            borderRadius: "var(--radius-sm)",
            border: "1px solid var(--border)",
            overflowX: "auto",
          }}
        >
          {chart}
        </pre>
      </div>
    );
  }

  if (!svg) {
    return (
      <div
        style={{
          padding: 20,
          textAlign: "center",
          color: "var(--text-muted)",
          fontSize: 13,
          background: "var(--bg-inset)",
          borderRadius: "var(--radius-sm)",
          border: "1px solid var(--border)",
        }}
      >
        Rendering Mermaid Diagram…
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        padding: 20,
        background: "var(--bg-inset)",
        borderRadius: "var(--radius-sm)",
        border: "1px solid var(--border)",
        overflowX: "auto",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        marginTop: 12,
        marginBottom: 16,
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

function MarkdownRenderer({ content, accent }: { content: string; accent?: string }) {
  const html = useMemo(() => {
    const raw = cleanMarkdown(content);
    try {
      return marked.parse(raw, { gfm: true, breaks: true }) as string;
    } catch {
      return raw;
    }
  }, [content]);

  // Extract mermaid codeblocks if present
  const mermaidBlocks = useMemo(() => {
    const raw = cleanMarkdown(content);
    const regex = /```mermaid([\s\S]*?)```/g;
    const matches: string[] = [];
    let match;
    while ((match = regex.exec(raw)) !== null) {
      matches.push(match[1].trim());
    }
    return matches;
  }, [content]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {mermaidBlocks.map((chart, idx) => (
        <MermaidBlock key={idx} chart={chart} />
      ))}
      <div
        className="markdown-body fade-in"
        style={{
          background: "var(--bg-inset)",
          padding: "20px 22px",
          borderRadius: "var(--radius-sm)",
          border: `1px solid ${accent || "var(--border)"}33`,
          maxHeight: 560,
          overflowY: "auto",
        }}
        dangerouslySetInnerHTML={{ __html: html }}
      />
    </div>
  );
}

// ─── 17 Sections Configuration & Categories ───────────────────────────────────

export interface SectionMeta {
  key: keyof ProjectAnalysis;
  label: string;
  category: "overview" | "engineering" | "developer" | "diagrams";
  icon: string;
  accent: string;
  description: string;
}

export const SECTIONS: SectionMeta[] = [
  // Overview & Architecture
  {
    key: "structure",
    label: "Structure & Architecture",
    category: "overview",
    icon: "layers",
    accent: "var(--accent)",
    description: "Directory tree, file organization, tech stack, and modular design patterns.",
  },
  {
    key: "working_purpose",
    label: "Working Purpose & Utility",
    category: "overview",
    icon: "target",
    accent: "var(--teal)",
    description: "Core project objective, problem solved, target users, and domain utility.",
  },
  {
    key: "plan",
    label: "Development Plan & Strategy",
    category: "overview",
    icon: "map",
    accent: "var(--violet)",
    description: "System engineering strategy, design goals, and architectural trade-offs.",
  },
  {
    key: "flow",
    label: "Execution Flow & Data Movement",
    category: "overview",
    icon: "gitBranch",
    accent: "var(--accent)",
    description: "Step-by-step request flow, data transformations, and call sequences.",
  },

  // Implementation & Security
  {
    key: "functioning",
    label: "Component Functioning & Logic",
    category: "engineering",
    icon: "cpu",
    accent: "var(--violet)",
    description: "Deep technical breakdown of internal class logic, algorithms, and endpoints.",
  },
  {
    key: "design_decisions",
    label: "Design Decisions & Trade-offs",
    category: "engineering",
    icon: "scale",
    accent: "var(--teal)",
    description: "Rationale behind framework selection, pattern choices, and trade-offs made.",
  },
  {
    key: "assumptions_and_constraints",
    label: "Assumptions & Constraints",
    category: "engineering",
    icon: "anchor",
    accent: "var(--warning)",
    description: "Implicit limits, scaling boundaries, and environmental constraints baked in.",
  },
  {
    key: "security_overview",
    label: "Security Overview & Audit",
    category: "engineering",
    icon: "shield",
    accent: "var(--danger)",
    description: "Authentication, validation rules, CORS, secrets handling, and vulnerability risks.",
  },
  {
    key: "error_handling",
    label: "Error Handling & Failure Modes",
    category: "engineering",
    icon: "alertTriangle",
    accent: "var(--warning)",
    description: "Handled vs unhandled failure modes, exceptions, logging, and edge cases.",
  },
  {
    key: "configuration_reference",
    label: "Configuration Reference",
    category: "engineering",
    icon: "sliders",
    accent: "var(--accent)",
    description: "Exhaustive table of environment variables, settings, and defaults.",
  },

  // Developer Guidance & Quality
  {
    key: "extension_guide",
    label: "Developer Extension Guide",
    category: "developer",
    icon: "code",
    accent: "var(--teal)",
    description: "Step-by-step guide for adding new features or endpoints following existing patterns.",
  },
  {
    key: "glossary_and_faq",
    label: "Glossary & Developer FAQ",
    category: "developer",
    icon: "helpCircle",
    accent: "var(--violet)",
    description: "Domain terms, internal symbol definitions, and common dev questions answered.",
  },
  {
    key: "tech_debt_and_dependencies",
    label: "Tech Debt & Dependency Report",
    category: "developer",
    icon: "package",
    accent: "var(--warning)",
    description: "Package usage, deprecated libraries, and prioritized technical debt items.",
  },
  {
    key: "module_graph_and_coverage",
    label: "Test Coverage & Module Graph",
    category: "developer",
    icon: "pieChart",
    accent: "var(--accent)",
    description: "Tested vs untested code areas and module dependency relationships.",
  },
  {
    key: "limitations_and_runbook",
    label: "Limitations & Deployment Runbook",
    category: "developer",
    icon: "terminal",
    accent: "var(--teal)",
    description: "Operational runbook, monitoring steps, troubleshooting, and known limits.",
  },

  // Visual Diagrams & Documentation
  {
    key: "sequence_diagrams",
    label: "Data Flow & Sequence Diagrams",
    category: "diagrams",
    icon: "activity",
    accent: "var(--violet)",
    description: "Interactive Mermaid.js diagrams showing sequence calls and data movement.",
  },
  {
    key: "readme_markdown",
    label: "Production README.md",
    category: "diagrams",
    icon: "fileText",
    accent: "var(--success)",
    description: "Publication-ready README file complete with installation, setup, and usage.",
  },
];

const CATEGORIES = [
  { key: "overview", label: "🏛️ Overview & Architecture" },
  { key: "engineering", label: "⚙️ Implementation & Security" },
  { key: "developer", label: "🛠️ Developer Guidance & Quality" },
  { key: "diagrams", label: "📊 Diagrams & README" },
];

// ─── Progress Step ────────────────────────────────────────────────────────────

function StepRow({
  label,
  icon,
  color,
  status,
}: {
  label: string;
  icon: string;
  color: string;
  status: "pending" | "generating" | "done" | "error";
}) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 12,
        padding: "8px 12px",
        borderRadius: "var(--radius-sm)",
        background:
          status === "generating"
            ? "rgba(99,102,241,.09)"
            : status === "done"
            ? "rgba(16,185,129,.07)"
            : "var(--bg-inset)",
        border: `1px solid ${
          status === "generating"
            ? "rgba(99,102,241,.35)"
            : status === "done"
            ? "rgba(16,185,129,.25)"
            : "var(--border)"
        }`,
        transition: "all 0.25s ease",
      }}
    >
      <Icon
        name={icon as any}
        size={16}
        style={{
          color: status === "done" ? "var(--success)" : color,
          flexShrink: 0,
        }}
      />
      <span style={{ flex: 1, fontSize: 13, fontWeight: 500 }}>{label}</span>
      {status === "pending" && <span style={{ fontSize: 11.5, color: "var(--text-faint)" }}>Waiting…</span>}
      {status === "generating" && (
        <span style={{ fontSize: 11.5, color: color, display: "flex", alignItems: "center", gap: 6 }}>
          <span
            style={{
              display: "inline-block",
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: color,
              animation: "pulse 1s ease-in-out infinite",
            }}
          />
          LLM Generating…
        </span>
      )}
      {status === "done" && <Icon name="checkCircle" size={15} style={{ color: "var(--success)" }} />}
    </div>
  );
}

// ─── Upload Card ──────────────────────────────────────────────────────────────

export function ProjectAnalyzerCard({
  onAnalyze,
}: {
  onAnalyze: (file: File, onProgress: (step: string) => void) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [currentStep, setCurrentStep] = useState<string | null>(null);
  const [completedSteps, setCompletedSteps] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);

  function getStepStatus(key: string): "pending" | "generating" | "done" | "error" {
    if (completedSteps.includes(key)) return "done";
    if (currentStep === key) return "generating";
    return "pending";
  }

  async function handleUpload() {
    if (!file) return;
    setAnalyzing(true);
    setCurrentStep(null);
    setCompletedSteps([]);

    const stepKeys = SECTIONS.map((s) => s.key);
    const MS_PER_STEP = 35_000;
    let stepIdx = 0;

    function advanceStep() {
      if (stepIdx < stepKeys.length) {
        setCurrentStep(stepKeys[stepIdx]);
        stepIdx++;
      }
    }

    advanceStep();

    const progressInterval = setInterval(() => {
      setCompletedSteps(() => stepKeys.slice(0, stepIdx - 1));
      advanceStep();
    }, MS_PER_STEP);

    try {
      await onAnalyze(file, (_step: string) => {});
      setCompletedSteps(stepKeys);
      setCurrentStep(null);
      toast(`🎉 All 17 LLM sections generated for "${file.name}"`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : String(e), "error");
    } finally {
      clearInterval(progressInterval);
      setAnalyzing(false);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith(".zip")) setFile(dropped);
    else toast("Only .zip files are supported", "error");
  }

  return (
    <Card title="⚡ Deep AI Project Analyzer & 17-Section Report Engine" icon="search">
      <p style={{ color: "var(--text-muted)", fontSize: 13.5, marginBottom: 20, lineHeight: 1.7 }}>
        Upload any project archive (<code>.zip</code>). The system inspects AST symbols, dependency graphs, and code files to generate an <strong>exhaustive 17-section software intelligence report</strong> covering architecture, design trade-offs, security, error handling, Mermaid diagrams, and a production-ready <code>README.md</code>.
      </p>

      {/* Drop zone */}
      <div
        style={{
          border: `2px dashed ${dragging ? "var(--accent)" : file ? "var(--success)" : "var(--border)"}`,
          borderRadius: "var(--radius)",
          padding: "32px 24px",
          textAlign: "center",
          background: dragging
            ? "rgba(99,102,241,.07)"
            : file
            ? "rgba(16,185,129,.06)"
            : "var(--bg-inset)",
          marginBottom: 20,
          cursor: "pointer",
          transition: "all 0.25s ease",
        }}
        onClick={() => !analyzing && document.getElementById("project-zip-input")?.click()}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          id="project-zip-input"
          type="file"
          accept=".zip"
          style={{ display: "none" }}
          onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
        />
        <Icon
          name={file ? "checkCircle" : "upload"}
          size={40}
          style={{
            color: file ? "var(--success)" : "var(--accent)",
            marginBottom: 12,
            display: "block",
            margin: "0 auto 12px",
          }}
        />
        <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 4 }}>
          {file ? `📦 ${file.name}` : "Drop or click to upload project archive (.zip)"}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--text-faint)" }}>
          {file
            ? `${(file.size / 1024).toFixed(1)} KB — ready for full 17-section analysis`
            : "Supports Python, TypeScript/JavaScript, C/C++, Java, Go, Rust, and shell projects"}
        </div>
      </div>

      {/* Progress tracker */}
      {analyzing && (
        <div style={{ marginBottom: 20 }}>
          <div
            style={{
              fontSize: 12,
              fontWeight: 600,
              color: "var(--text-muted)",
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              marginBottom: 10,
              display: "flex",
              justifyContent: "space-between",
            }}
          >
            <span>LLM Generation Progress</span>
            <span>{completedSteps.length} / 17 Sections Done</span>
          </div>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: 8,
              maxHeight: 260,
              overflowY: "auto",
              paddingRight: 4,
            }}
          >
            {SECTIONS.map((s) => (
              <StepRow
                key={s.key}
                label={s.label}
                icon={s.icon}
                color={s.accent}
                status={getStepStatus(s.key)}
              />
            ))}
          </div>
        </div>
      )}

      <Button
        variant="primary"
        icon="send"
        disabled={!file || analyzing}
        onClick={handleUpload}
        style={{ width: "100%" }}
      >
        {analyzing
          ? `Analyzing… (${completedSteps.length}/17 sections complete)`
          : "🚀 Run Complete 17-Section AI Analysis"}
      </Button>

      {!analyzing && (
        <div
          style={{
            display: "flex",
            gap: 6,
            flexWrap: "wrap",
            marginTop: 14,
            justifyContent: "center",
          }}
        >
          {SECTIONS.slice(0, 8).map((s) => (
            <Chip key={s.key} tone="neutral">
              {s.label}
            </Chip>
          ))}
          <Chip tone="cyan">+ 9 more sections</Chip>
        </div>
      )}
    </Card>
  );
}

// ─── Analysis Results View ────────────────────────────────────────────────────

export function ProjectAnalysisView({
  analysis,
  onClose,
}: {
  analysis: ProjectAnalysis;
  onClose: () => void;
}) {
  const [activeKey, setActiveKey] = useState<keyof ProjectAnalysis>("structure");
  const [activeCategory, setActiveCategory] = useState<string>("overview");
  const [search, setSearch] = useState("");
  const [readmeMode, setReadmeMode] = useState<"rendered" | "raw">("rendered");

  const filteredSections = useMemo(() => {
    if (!search.trim()) {
      return SECTIONS.filter((s) => s.category === activeCategory);
    }
    const q = search.toLowerCase();
    return SECTIONS.filter(
      (s) => s.label.toLowerCase().includes(q) || s.description.toLowerCase().includes(q)
    );
  }, [search, activeCategory]);

  const activeMeta = SECTIONS.find((s) => s.key === activeKey) || SECTIONS[0];
  const activeContent = (analysis[activeKey] as string) || "No content generated.";

  function copyText(text: string, label: string) {
    const cleaned = cleanMarkdown(text);
    navigator.clipboard.writeText(cleaned);
    toast(`${label} copied to clipboard`, "success");
  }

  function downloadReadme() {
    const cleaned = cleanMarkdown(analysis.readme_markdown);
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([cleaned], { type: "text/markdown" }));
    a.download = "README.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    toast("README.md downloaded", "success");
  }

  return (
    <div style={{ marginTop: 28 }} className="fade-in">
      {/* Top bar header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 20,
        }}
      >
        <div>
          <h2
            style={{
              fontSize: 22,
              fontWeight: 700,
              margin: 0,
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <Icon name="checkCircle" size={24} style={{ color: "var(--success)" }} />
            Project Analysis — 17-Section Intelligence Report
          </h2>
          <div style={{ display: "flex", gap: 10, marginTop: 8, flexWrap: "wrap" }}>
            <Chip tone="cyan">📁 {analysis.total_files} Files Scanned</Chip>
            <Chip tone="violet">🔣 {analysis.ast_element_count} AST Elements</Chip>
            <Chip tone="green">✨ 17 Sections LLM Generated</Chip>
          </div>
        </div>
        <Button variant="ghost" size="sm" icon="x" onClick={onClose}>
          Close Analysis
        </Button>
      </div>

      {/* Category selector & Search bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: 12,
          marginBottom: 16,
          flexWrap: "wrap",
        }}
      >
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {CATEGORIES.map((cat) => (
            <button
              key={cat.key}
              onClick={() => {
                setActiveCategory(cat.key);
                setSearch("");
                const firstInSection = SECTIONS.find((s) => s.category === cat.key);
                if (firstInSection) setActiveKey(firstInSection.key);
              }}
              style={{
                padding: "6px 14px",
                borderRadius: "var(--radius-sm)",
                border: activeCategory === cat.key ? "1.5px solid var(--accent)" : "1.5px solid transparent",
                background: activeCategory === cat.key ? "rgba(99,102,241,.14)" : "var(--bg-inset)",
                color: activeCategory === cat.key ? "var(--accent)" : "var(--text-muted)",
                fontSize: 13,
                fontWeight: activeCategory === cat.key ? 600 : 400,
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
            >
              {cat.label}
            </button>
          ))}
        </div>

        <input
          className="input"
          placeholder="🔍 Search all 17 sections…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ maxWidth: 240, fontSize: 12.5 }}
        />
      </div>

      {/* Section Sub-Tabs */}
      <div
        style={{
          display: "flex",
          gap: 6,
          borderBottom: "1px solid var(--border)",
          paddingBottom: 12,
          marginBottom: 20,
          overflowX: "auto",
        }}
      >
        {filteredSections.map((sec) => (
          <button
            key={sec.key}
            onClick={() => setActiveKey(sec.key)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 12px",
              borderRadius: "var(--radius-sm)",
              border: activeKey === sec.key ? `1.5px solid ${sec.accent}` : "1.5px solid transparent",
              background: activeKey === sec.key ? `${sec.accent}18` : "transparent",
              color: activeKey === sec.key ? sec.accent : "var(--text-muted)",
              fontSize: 12.5,
              fontWeight: activeKey === sec.key ? 600 : 400,
              cursor: "pointer",
              whiteSpace: "nowrap",
              transition: "all 0.2s ease",
            }}
          >
            <Icon name={sec.icon as any} size={14} />
            {sec.label}
          </button>
        ))}
      </div>

      {/* Main Content Area */}
      <div
        style={{
          background: "var(--bg-card)",
          border: "1px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "22px 24px",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: 16,
          }}
        >
          <div>
            <h3
              style={{
                fontSize: 16,
                fontWeight: 700,
                margin: 0,
                color: activeMeta.accent,
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <Icon name={activeMeta.icon as any} size={18} />
              {activeMeta.label}
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 500,
                  background: `${activeMeta.accent}22`,
                  color: activeMeta.accent,
                  padding: "2px 8px",
                  borderRadius: 9999,
                }}
              >
                LLM Generated
              </span>
            </h3>
            <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
              {activeMeta.description}
            </div>
          </div>

          <div style={{ display: "flex", gap: 8 }}>
            {activeKey === "readme_markdown" && (
              <div
                style={{
                  display: "flex",
                  background: "var(--bg-inset)",
                  padding: 2,
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--border)",
                }}
              >
                <button
                  onClick={() => setReadmeMode("rendered")}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "none",
                    background: readmeMode === "rendered" ? "var(--accent)" : "transparent",
                    color: readmeMode === "rendered" ? "#fff" : "var(--text-muted)",
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  Preview
                </button>
                <button
                  onClick={() => setReadmeMode("raw")}
                  style={{
                    padding: "4px 10px",
                    borderRadius: 4,
                    border: "none",
                    background: readmeMode === "raw" ? "var(--accent)" : "transparent",
                    color: readmeMode === "raw" ? "#fff" : "var(--text-muted)",
                    fontSize: 12,
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  Raw Code
                </button>
              </div>
            )}

            <Button size="sm" variant="ghost" icon="copy" onClick={() => copyText(activeContent, activeMeta.label)}>
              Copy
            </Button>
            {activeKey === "readme_markdown" && (
              <Button size="sm" variant="primary" icon="download" onClick={downloadReadme}>
                Download README.md
              </Button>
            )}
          </div>
        </div>

        {/* Content Display */}
        {activeKey === "readme_markdown" && readmeMode === "raw" ? (
          <pre
            style={{
              whiteSpace: "pre-wrap",
              fontSize: 12.5,
              lineHeight: 1.7,
              fontFamily: "var(--mono)",
              background: "var(--bg-inset)",
              padding: "18px 20px",
              borderRadius: "var(--radius-sm)",
              border: "1px solid rgba(16,185,129,.2)",
              color: "var(--text)",
              maxHeight: 560,
              overflowY: "auto",
              margin: 0,
            }}
          >
            {cleanMarkdown(activeContent)}
          </pre>
        ) : (
          <MarkdownRenderer content={activeContent} accent={activeMeta.accent} />
        )}
      </div>

      {/* File tree accordion */}
      {analysis.file_tree && analysis.file_tree.length > 0 && (
        <details
          style={{
            marginTop: 16,
            background: "var(--bg-card)",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "12px 16px",
          }}
        >
          <summary
            style={{
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13,
              color: "var(--text-muted)",
            }}
          >
            📂 Scanned File Tree ({analysis.file_tree.length} files)
          </summary>
          <pre
            style={{
              marginTop: 10,
              fontFamily: "var(--mono)",
              fontSize: 12,
              color: "var(--text-faint)",
              whiteSpace: "pre-wrap",
              maxHeight: 260,
              overflowY: "auto",
              padding: "10px 12px",
              background: "var(--bg-inset)",
              borderRadius: "var(--radius-sm)",
            }}
          >
            {analysis.file_tree.join("\n")}
          </pre>
        </details>
      )}
    </div>
  );
}
