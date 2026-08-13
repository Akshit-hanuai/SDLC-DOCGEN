"""
Route: POST /analyze/generate-from-analysis/{doc_type}

Accepts the full 17-section project analysis JSON and generates a formal SDLC
document (SRS, SDD, ICD, STP, STR) grounded in that analysis — no RAG pipeline needed.
"""
import asyncio
import time
import uuid
from functools import partial

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.document import Project
from app.services.generate.generator import generate_document, get_or_create_document
from app.services.llm.client import get_llm_client
from app.services.analyzer import ProjectAnalyzerService

router = APIRouter(prefix="/analyze", tags=["analyze"])

VALID_DOC_TYPES = {"SRS", "SDD", "ICD", "STP", "STR"}

_DOC_SYSTEM = {
    "SRS": (
        "You are a senior technical writer producing a formal Software Requirements Specification (SRS). "
        "Extract all functional and non-functional requirements from the provided codebase analysis. "
        "Write in 'the system shall…' style with numbered requirement IDs (REQ-0001, REQ-0002…). "
        "Include: Purpose & Scope, System Overview, Functional Requirements, Non-Functional Requirements, "
        "Interface Requirements, Constraints & Assumptions, and Traceability Notes."
    ),
    "SDD": (
        "You are a senior architect producing a formal Software Design Description (SDD). "
        "Use the codebase analysis to describe the full design. "
        "Include: Design Overview, Architectural Style, Module Decomposition, "
        "Component Interfaces, Data Structures, Design Decisions & Rationale, and Deployment View."
    ),
    "ICD": (
        "You are a systems engineer producing a formal Interface Control Document (ICD). "
        "From the codebase analysis, identify all external interfaces, APIs, protocols, and data boundaries. "
        "Include: Interface Summary Table, each Interface Definition (name, type, protocol, data format, "
        "validation rules, error codes), and Configuration Notes."
    ),
    "STP": (
        "You are a test architect producing a formal Software Test Plan (STP). "
        "From the codebase analysis, derive a complete test plan. "
        "Include: Test Scope, Test Strategy, Test Types (unit/integration/system/acceptance), "
        "Test Cases Table (ID, description, inputs, expected outputs, pass criteria), "
        "Coverage Targets, and Test Environment Requirements."
    ),
    "STR": (
        "You are a QA engineer producing a formal Software Test Report (STR). "
        "Based on the codebase analysis and test coverage information, produce a test execution report. "
        "Include: Executive Summary, Test Results Table (Test Case ID, status, notes), "
        "Coverage Summary, Defect Log, Known Issues, and Compliance Verdict."
    ),
}

_DOC_PROMPTS = {
    "SRS": lambda ctx: f"""Generate a complete, formal Software Requirements Specification (SRS) document.

Use ONLY the following project analysis as your source of truth. Every requirement must be traceable to a specific component, function, or behavior observed in the code.

{ctx}

Format as a full professional technical document with numbered sections and proper SRS structure.""",

    "SDD": lambda ctx: f"""Generate a complete, formal Software Design Description (SDD) document.

Use the following project analysis as your engineering reference. Ground every design decision in observed architecture and code patterns.

{ctx}

Format as a full professional technical document with numbered sections and proper SDD structure.""",

    "ICD": lambda ctx: f"""Generate a complete, formal Interface Control Document (ICD).

From the project analysis below, identify and document all APIs, external interfaces, data schemas, and communication protocols.

{ctx}

Format as a full professional technical document with interface tables and precise data format specifications.""",

    "STP": lambda ctx: f"""Generate a complete, formal Software Test Plan (STP).

From the project analysis below, derive comprehensive test cases covering all modules, endpoints, and code paths.

{ctx}

Format as a full professional technical document with a structured test case table (Test ID, Description, Input, Expected Output, Pass Criteria).""",

    "STR": lambda ctx: f"""Generate a complete, formal Software Test Report (STR).

From the project analysis (specifically test coverage and module graph sections), produce a test execution report.

{ctx}

Format as a full professional technical document with test result tables, coverage metrics, and a compliance verdict.""",
}


class GenerateFromAnalysisRequest(BaseModel):
    project_id: str
    doc_type: str
    # The full 17-section analysis object from ProjectAnalyzerService
    analysis: dict


class GenerateFromAnalysisResponse(BaseModel):
    doc_type: str
    content: str
    elapsed_s: float


@router.post("/generate-from-analysis", response_model=GenerateFromAnalysisResponse)
async def generate_from_analysis(payload: GenerateFromAnalysisRequest):
    """
    Generate a formal SDLC document (SRS/SDD/ICD/STP/STR) directly from a
    17-section project analysis without needing a RAG-indexed project in the DB.
    """
    doc_type = payload.doc_type.upper()
    if doc_type not in VALID_DOC_TYPES:
        raise HTTPException(status_code=400, detail=f"doc_type must be one of {sorted(VALID_DOC_TYPES)}")

    analysis = payload.analysis

    # Build a rich context string from the 17-section analysis
    ctx_parts = []
    section_map = {
        "structure": "PROJECT STRUCTURE & ARCHITECTURE",
        "working_purpose": "WORKING PURPOSE & UTILITY",
        "flow": "EXECUTION FLOW & DATA MOVEMENT",
        "plan": "DEVELOPMENT PLAN & STRATEGY",
        "functioning": "COMPONENT FUNCTIONING & LOGIC",
        "design_decisions": "DESIGN DECISIONS & TRADE-OFFS",
        "assumptions_and_constraints": "ASSUMPTIONS & CONSTRAINTS",
        "error_handling": "ERROR HANDLING & FAILURE MODES",
        "configuration_reference": "CONFIGURATION REFERENCE",
        "security_overview": "SECURITY OVERVIEW",
        "extension_guide": "EXTENSION GUIDE",
        "glossary_and_faq": "GLOSSARY & FAQ",
        "tech_debt_and_dependencies": "DEPENDENCY REPORT & TECHNICAL DEBT",
        "sequence_diagrams": "DATA FLOW & SEQUENCE DIAGRAMS",
        "module_graph_and_coverage": "MODULE DEPENDENCY GRAPH & TEST COVERAGE",
        "limitations_and_runbook": "KNOWN LIMITATIONS & DEPLOYMENT RUNBOOK",
    }

    # Choose most relevant sections per doc type to avoid token bloat
    relevant_sections = {
        "SRS": ["structure", "working_purpose", "functioning", "assumptions_and_constraints",
                "configuration_reference", "security_overview", "design_decisions"],
        "SDD": ["structure", "plan", "functioning", "design_decisions", "module_graph_and_coverage",
                "sequence_diagrams", "flow"],
        "ICD": ["flow", "configuration_reference", "sequence_diagrams", "functioning",
                "security_overview", "error_handling"],
        "STP": ["module_graph_and_coverage", "functioning", "error_handling",
                "assumptions_and_constraints", "limitations_and_runbook"],
        "STR": ["module_graph_and_coverage", "limitations_and_runbook", "error_handling",
                "tech_debt_and_dependencies"],
    }.get(doc_type, list(section_map.keys()))

    for key in relevant_sections:
        val = analysis.get(key, "")
        if val and isinstance(val, str) and val.strip():
            label = section_map.get(key, key.upper())
            ctx_parts.append(f"=== {label} ===\n{val[:2500]}")

    # Add metadata summary
    meta = (
        f"Project has {analysis.get('total_files', '?')} files and "
        f"{analysis.get('ast_element_count', '?')} AST elements."
    )
    ctx_parts.insert(0, f"=== PROJECT METADATA ===\n{meta}")
    ctx = "\n\n".join(ctx_parts)

    system = _DOC_SYSTEM[doc_type]
    prompt = _DOC_PROMPTS[doc_type](ctx)

    llm = get_llm_client()
    started = time.time()
    loop = asyncio.get_event_loop()
    fn = partial(llm.complete_long, system, prompt)
    try:
        result: str = await loop.run_in_executor(None, fn)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

    # Strip wrapping code fences if model added them
    result = result.strip()
    for fence in ("```markdown", "```md", "```"):
        if result.startswith(fence):
            result = result[len(fence):]
            break
    if result.endswith("```"):
        result = result[:-3]
    result = result.strip()

    elapsed = round(time.time() - started, 2)
    return GenerateFromAnalysisResponse(doc_type=doc_type, content=result, elapsed_s=elapsed)
