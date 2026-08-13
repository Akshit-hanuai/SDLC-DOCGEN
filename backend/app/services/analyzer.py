import os
import zipfile
import tempfile
import logging
import asyncio
from functools import partial
from typing import Dict, Any, List

from app.services.llm.client import get_llm_client
from app.services.ingest.code_analyzer import analyze_code

logger = logging.getLogger(__name__)

_PRIORITY_EXTS = {
    ".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".c", ".cpp", ".h",
    ".yaml", ".yml", ".toml", ".json", ".md", ".env", ".sql", ".sh", ".rs"
}
_SKIP_EXTS = {
    ".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".svg", ".zip", ".tar", ".gz", ".ttf", ".eot", ".mp4", ".mp3",
    ".pdf", ".docx", ".pptx", ".xlsx", ".DS_Store", ".lock"
}
_SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
    ".next", ".nuxt", "coverage", ".tox", ".mypy_cache"
}


def _build_context(tree_str: str, ast_str: str, snippet_summary: str) -> str:
    return (
        f"=== PROJECT FILE TREE ===\n{tree_str}\n\n"
        f"=== KEY AST SYMBOLS / ENDPOINTS ===\n{ast_str}\n\n"
        f"=== SOURCE CODE SNIPPETS ===\n{snippet_summary}"
    )


class ProjectAnalyzerService:
    def __init__(self):
        self.llm = get_llm_client()

    async def _call_llm(self, system: str, user: str) -> str:
        loop = asyncio.get_event_loop()
        fn = partial(self.llm.complete_long, system, user)
        res: str = await loop.run_in_executor(None, fn)
        res = res.strip()
        if res.startswith("```markdown"):
            res = res[11:]
        elif res.startswith("```md"):
            res = res[5:]
        elif res.startswith("```"):
            res = res[3:]
        if res.endswith("```"):
            res = res[:-3]
        return res.strip()

    # ── Section 1: Architecture & Purpose ─────────────────────────────────────

    async def _gen_structure_and_plan(self, ctx: str) -> Dict[str, str]:
        system = "You are a Principal Software Architect writing detailed, exact architectural reports."
        
        structure = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Project Structure & Architecture** report.
Cover: Directory layout, tech stack, design patterns used (MVC, layered, microservices), entry points, and module organization.

{ctx}

Write 4-5 rich, detailed paragraphs. Reference exact file and folder names.""")

        plan = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Development Plan & Engineering Strategy** report.
Cover: Engineering objectives, original system design strategy, key architectural trade-offs, and build/deployment pipeline.

{ctx}

Write 4-5 detailed paragraphs.""")

        return {"structure": structure, "plan": plan}

    async def _gen_flow_and_purpose(self, ctx: str) -> Dict[str, str]:
        system = "You are a Senior Software Engineer explaining system flow and domain purpose."

        purpose = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Working Purpose & Domain Utility** section.
Cover: Core objective, problem solved, target users, key capabilities, and business/technical value.

{ctx}

Write 4-5 clear paragraphs grounded in the actual code.""")

        flow = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Execution Flow & Data Movement** section.
Cover: Step-by-step request flow from entrypoint to output, state changes, function call chains, and data transformations.

{ctx}

Provide a numbered step-by-step sequence followed by a detailed narrative.""")

        return {"working_purpose": purpose, "flow": flow}

    # ── Section 2: Implementation & Decisions ──────────────────────────────────

    async def _gen_functioning_and_decisions(self, ctx: str) -> Dict[str, str]:
        system = "You are a Staff Engineer performing a deep technical audit."

        functioning = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Component Functioning & Code Logic** breakdown.
Cover: How key classes/functions work internally, non-obvious logic, validation rules, caching, async patterns, and runtime wiring.

{ctx}

Name specific classes, functions, and methods seen in the code.""")

        decisions = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Design Decisions & Trade-offs** report.
Cover: Why specific frameworks/libraries/patterns were chosen, trade-offs made (e.g. speed vs memory, simplicity vs flexibility), and alternative approaches considered.

{ctx}

Be specific and ground every point in observed code evidence.""")

        assumptions = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Assumptions & Constraints** section.
Cover: Implicit limits baked into the code (e.g. max payload size, single-tenant, sync execution, environment assumptions, rate limits).

{ctx}

List assumptions and constraints explicitly using bullet points.""")

        return {
            "functioning": functioning,
            "design_decisions": decisions,
            "assumptions_and_constraints": assumptions,
        }

    # ── Section 3: Reliability & Security ──────────────────────────────────────

    async def _gen_reliability_and_security(self, ctx: str) -> Dict[str, str]:
        system = "You are a Chief Information Security Officer (CISO) & Site Reliability Engineer (SRE)."

        error_handling = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Error Handling & Failure Modes** report.
Cover: Exception handling patterns, handled vs unhandled failure modes, fallback mechanisms, logging strategy, and potential silent failures.

{ctx}

Provide specific examples from files where errors are caught or missed.""")

        security = await self._call_llm(system, f"""Analyze this codebase and write a detailed **Security Overview** report.
Cover: Authentication/authorization, input sanitization, sensitive data handling, secrets management, CORS/headers, and identified security risks.

{ctx}

Be thorough and highlight sensitive areas.""")

        config_ref = await self._call_llm(system, f"""Analyze this codebase and write a comprehensive **Configuration Reference**.
Cover: All environment variables, settings, flags, and default values found in the code, along with what each setting controls.

{ctx}

Provide a Markdown table: | Setting / Env Var | Default | Description | Required |""")

        return {
            "error_handling": error_handling,
            "security_overview": security,
            "configuration_reference": config_ref,
        }

    # ── Section 4: Developer Guidance ──────────────────────────────────────────

    async def _gen_developer_guidance(self, ctx: str) -> Dict[str, str]:
        system = "You are a Principal Architect authoring onboarding documentation."

        extension = await self._call_llm(system, f"""Analyze this codebase and write an **Extension Guide** for developers.
Cover: How to add a new endpoint, module, feature, or database table following existing patterns step-by-step.

{ctx}

Provide exact file paths to touch and code boilerplates to follow.""")

        glossary = await self._call_llm(system, f"""Analyze this codebase and produce a **Glossary & FAQ**.
Cover: 
1. **Glossary**: Key domain terms, abbreviations, and internal symbols defined in the code.
2. **FAQ**: 5-8 common developer questions about how the project works, answered directly from the code.

{ctx}

Format cleanly with clear headers.""")

        return {
            "extension_guide": extension,
            "glossary_and_faq": glossary,
        }

    # ── Section 5: Quality, Maintenance & Diagrams ────────────────────────────

    async def _gen_quality_and_diagrams(self, ctx: str, filename: str) -> Dict[str, str]:
        system = "You are a Lead Engineer & Systems Architect."

        tech_debt = await self._call_llm(system, f"""Analyze this codebase and produce a **Dependency Report & Technical Debt Inventory**.
Cover: 
1. **Dependency Analysis**: Packages used, outdated/deprecated dependencies, unnecessary bloat.
2. **Technical Debt Inventory**: Prioritized list of debt items (High / Medium / Low priority) with specific file locations.

{ctx}

Use Markdown tables for both dependencies and tech debt items.""")

        sequence = await self._call_llm(system, f"""Analyze this codebase and create **Data Flow & Sequence Diagrams** using Mermaid syntax.

Provide:
1. **Data Flow Diagram** (Mermaid `graph TD` or `flowchart LR`) showing data movement across components.
2. **Sequence Diagram** (Mermaid `sequenceDiagram`) showing a primary user request lifecycle.

{ctx}

Format the Mermaid diagrams inside ```mermaid ... ``` code blocks with explanatory text.""")

        module_graph = await self._call_llm(system, f"""Analyze this codebase and produce a **Module Dependency Graph & Test Coverage Summary**.
Cover:
1. **Module Graph**: Mermaid `graph TD` showing component dependencies.
2. **Test Coverage Analysis**: Tested vs untested modules based on project files, missing test suites, and recommendations.

{ctx}

Include a Mermaid diagram for the module dependencies.""")

        limitations = await self._call_llm(system, f"""Analyze this codebase and produce **Known Limitations & Deployment Runbook**.
Cover:
1. **Known Limitations**: Explicit things the system cannot or does not do.
2. **Deployment Runbook**: How to build, run, monitor, and troubleshoot in production. What to check if it breaks.

{ctx}

Be practical and operational.""")

        return {
            "tech_debt_and_dependencies": tech_debt,
            "sequence_diagrams": sequence,
            "module_graph_and_coverage": module_graph,
            "limitations_and_runbook": limitations,
        }

    async def _gen_readme(self, ctx: str, filename: str, structure: str, purpose: str) -> str:
        system = "You are a senior open-source maintainer writing a production-ready README.md."
        project_name = filename.replace(".zip", "").replace("_", "-").replace(".", "-")

        return await self._call_llm(system, f"""Write a complete, production-grade README.md for this project.

Project name: {project_name}
Structure summary: {structure[:400]}
Purpose summary: {purpose[:400]}

Full codebase context:
{ctx}

Must include: Title, Badges, Overview, Features, Tech Stack, Directory Structure, Quick Start, Configuration, Architecture, API Reference, Contributing, License.

Format in clean GitHub Markdown.""")

    # ── Main entry point ──────────────────────────────────────────────────────

    async def analyze_project_zip(self, file_bytes: bytes, filename: str) -> Dict[str, Any]:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = os.path.join(tmpdir, filename)
            with open(zip_path, "wb") as f:
                f.write(file_bytes)

            extract_dir = os.path.join(tmpdir, "extracted")
            os.makedirs(extract_dir, exist_ok=True)

            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extract_dir)

            priority_files: List[tuple] = []
            other_files: List[tuple] = []
            file_tree: List[str] = []
            total_files = 0

            for root, dirs, files in os.walk(extract_dir):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.startswith(".")]

                for fname in sorted(files):
                    if fname.startswith("."):
                        continue
                    ext = os.path.splitext(fname)[1].lower()
                    if ext in _SKIP_EXTS:
                        continue

                    full_path = os.path.join(root, fname)
                    rel_path = os.path.relpath(full_path, extract_dir)
                    file_tree.append(rel_path)
                    total_files += 1

                    size = os.path.getsize(full_path)
                    if size < 60_000:
                        try:
                            with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                                content = fh.read()
                            entry = (rel_path, size, content)
                            if ext in _PRIORITY_EXTS:
                                priority_files.append(entry)
                            else:
                                other_files.append(entry)
                        except Exception as e:
                            logger.debug("Could not read %s: %s", rel_path, e)

            priority_files.sort(key=lambda x: x[1])
            selected = priority_files[:14] + other_files[:4]

            snippet_summary = "\n\n".join(
                f"=== {path} ===\n{content[:1800]}"
                for path, _, content in selected
            )

            code_analyses = analyze_code(extract_dir)
            ast_summary: List[str] = []
            for analysis in code_analyses:
                for artifact in analysis.artifacts:
                    ast_summary.append(f"- {artifact.kind} {artifact.name} ({artifact.artifact_id})")

            tree_str = "\n".join(file_tree[:160])
            ast_str = "\n".join(ast_summary[:90])
            ctx = _build_context(tree_str, ast_str, snippet_summary)

            logger.info(
                "Starting 17-section LLM analysis for %s (%d files, %d selected, %d AST symbols)",
                filename, total_files, len(selected), len(ast_summary)
            )

            # Execute generators sequentially to avoid overloading local Ollama
            res1 = await self._gen_structure_and_plan(ctx)
            res2 = await self._gen_flow_and_purpose(ctx)
            res3 = await self._gen_functioning_and_decisions(ctx)
            res4 = await self._gen_reliability_and_security(ctx)
            res5 = await self._gen_developer_guidance(ctx)
            res6 = await self._gen_quality_and_diagrams(ctx, filename)
            readme = await self._gen_readme(ctx, filename, res1["structure"], res2["working_purpose"])

            logger.info("🎉 All 17 LLM analysis sections complete for %s", filename)

            return {
                "structure": res1["structure"],
                "plan": res1["plan"],
                "flow": res2["flow"],
                "working_purpose": res2["working_purpose"],
                "functioning": res3["functioning"],
                "design_decisions": res3["design_decisions"],
                "assumptions_and_constraints": res3["assumptions_and_constraints"],
                "error_handling": res4["error_handling"],
                "security_overview": res4["security_overview"],
                "configuration_reference": res4["configuration_reference"],
                "extension_guide": res5["extension_guide"],
                "glossary_and_faq": res5["glossary_and_faq"],
                "tech_debt_and_dependencies": res6["tech_debt_and_dependencies"],
                "sequence_diagrams": res6["sequence_diagrams"],
                "module_graph_and_coverage": res6["module_graph_and_coverage"],
                "limitations_and_runbook": res6["limitations_and_runbook"],
                "readme_markdown": readme,
                "total_files": total_files,
                "file_tree": file_tree,
                "ast_element_count": len(ast_summary),
            }
