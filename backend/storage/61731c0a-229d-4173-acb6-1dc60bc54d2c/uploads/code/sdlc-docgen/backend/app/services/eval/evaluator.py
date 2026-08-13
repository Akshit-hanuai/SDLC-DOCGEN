import csv
import re
from pathlib import Path

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentVersion
from app.models.requirement import Requirement, TraceabilityLink
from app.services.rag.embeddings import get_embedder
from app.services.template_store import template_store

_STOPWORDS = set("a an the and or of to in on for with as at by from".split())


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOPWORDS]


def _ngrams(tokens: list[str], n: int) -> set[tuple[str, ...]]:
    return {tuple(tokens[i : i + n]) for i in range(max(0, len(tokens) - n + 1))}


def rouge_n(reference: str, candidate: str, n: int) -> float:
    ref_tokens, cand_tokens = _tokens(reference), _tokens(candidate)
    if not ref_tokens or not cand_tokens:
        return 0.0
    ref_ngrams, cand_ngrams = _ngrams(ref_tokens, n), _ngrams(cand_tokens, n)
    if not cand_ngrams:
        return 0.0
    matches = len(ref_ngrams & cand_ngrams)
    recall = matches / len(ref_ngrams)
    precision = matches / len(cand_ngrams)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def rouge_l(reference: str, candidate: str) -> float:
    ref_tokens, cand_tokens = _tokens(reference), _tokens(candidate)
    if not ref_tokens or not cand_tokens:
        return 0.0
    table = [[0] * (len(cand_tokens) + 1) for _ in range(len(ref_tokens) + 1)]
    for i in range(1, len(ref_tokens) + 1):
        for j in range(1, len(cand_tokens) + 1):
            if ref_tokens[i - 1] == cand_tokens[j - 1]:
                table[i][j] = table[i - 1][j - 1] + 1
            else:
                table[i][j] = max(table[i - 1][j], table[i][j - 1])
    lcs = table[-1][-1]
    recall = lcs / len(ref_tokens)
    precision = lcs / len(cand_tokens)
    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def bertscore_like(reference: str, candidate: str) -> float:
    embedder = get_embedder()
    ref_sents = [s for s in re.split(r"[.;\n]", reference) if len(s) > 10]
    cand_sents = [s for s in re.split(r"[.;\n]", candidate) if len(s) > 10]
    if not ref_sents or not cand_sents:
        return 0.0
    ref_vecs = embedder.embed(ref_sents)
    cand_vecs = embedder.embed(cand_sents)
    sims = cand_vecs @ ref_vecs.T
    recall = np.max(sims, axis=0).mean()
    precision = np.max(sims, axis=1).mean()
    if precision + recall == 0:
        return 0.0
    return float(2 * precision * recall / (precision + recall))


async def run_evaluation(session: AsyncSession, project_id) -> dict:
    requirements = list((await session.execute(select(Requirement).where(Requirement.project_id == project_id))).scalars().all())
    links = list((await session.execute(select(TraceabilityLink).where(TraceabilityLink.project_id == project_id))).scalars().all())
    documents = list((await session.execute(select(Document).where(Document.project_id == project_id))).scalars().all())

    registry = {r.req_id: r for r in requirements}
    registry_real = {rid: r for rid, r in registry.items() if r.req_type not in ("code_artifact", "test_case")}

    dangling = [
        {"from": l.from_req_id, "to": l.to_req_id}
        for l in links
        if l.from_req_id not in registry or l.to_req_id not in registry
    ]
    traceability_completeness = round(1 - len(dangling) / max(len(links), 1), 3)

    doc_metrics: dict[str, dict] = {}
    per_doc_text: dict[str, str] = {}
    for document in documents:
        version = await _latest_version(session, document.id)
        if version is None:
            continue
        text = _content_text(version.content)
        per_doc_text[document.doc_type] = text
        referenced = set(re.findall(r"\b(?:REQ|SR|IR)-\d{3,4}(?:\.\d+)*\b", text))
        coverage = round(len(referenced & set(registry_real)) / max(len(registry_real), 1), 3)
        schema = template_store.get(document.doc_type.lower())
        section_ids = [s.id for s in schema.sections] if schema else []
        present = [sid for sid in section_ids if _has_section(version.content, sid)]
        conformance = round(len(present) / max(len(section_ids), 1), 3)
        compliance = (version.content.get("_compliance") or {}).get("status", "unknown")
        doc_metrics[document.doc_type] = {
            "version": version.version,
            "requirement_coverage": coverage,
            "covered": len(referenced & set(registry_real)),
            "total_requirements": len(registry_real),
            "template_conformance": conformance,
            "sections_present": len(present),
            "sections_expected": len(section_ids),
            "compliance_status": compliance,
        }

    similarity = _similarity_matrix(per_doc_text)
    consistency = _cross_document_consistency(per_doc_text)

    return {
        "project_id": str(project_id),
        "requirements": {"total": len(registry), "real": len(registry_real)},
        "traceability": {
            "links": len(links),
            "dangling": len(dangling),
            "completeness": traceability_completeness,
        },
        "documents": doc_metrics,
        "cross_document_consistency": consistency,
        "similarity": similarity,
    }


async def _latest_version(session, document_id) -> DocumentVersion | None:
    result = await session.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _content_text(content: dict) -> str:
    parts = []
    for section in (content.get("sections") or {}).values():
        if isinstance(section, dict):
            for value in section.values():
                if isinstance(value, str):
                    parts.append(value)
                elif isinstance(value, list):
                    for item in value:
                        parts.append(" ".join(str(v) for v in item.values()) if isinstance(item, dict) else str(item))
        elif isinstance(section, str):
            parts.append(section)
    return "\n".join(parts)


def _has_section(content: dict, sid: str) -> bool:
    section = (content.get("sections") or {}).get(sid)
    if not section:
        return False
    if isinstance(section, str):
        return bool(section.strip())
    return any(
        (isinstance(v, str) and v.strip()) or (isinstance(v, list) and v)
        for v in section.values()
    )


def _similarity_matrix(per_doc_text: dict[str, str]) -> dict[str, dict]:
    result = {}
    source_pool = {"SRS": "sysrs", "SDD": "srs", "ICD": "irs", "STP": "srs", "STR": "stp"}
    for doc_type, text in per_doc_text.items():
        reference_key = source_pool.get(doc_type)
        if reference_key and reference_key.upper() in per_doc_text:
            reference = per_doc_text[reference_key.upper()]
            result[doc_type] = {
                "rouge1": round(rouge_n(reference, text, 1), 3),
                "rouge2": round(rouge_n(reference, text, 2), 3),
                "rougeL": round(rouge_l(reference, text), 3),
                "bertscore_like_f1": round(bertscore_like(reference, text), 3),
            }
    return result


def _cross_document_consistency(per_doc_text: dict[str, str]) -> dict:
    referenced = {
        doc_type: set(re.findall(r"\b(?:REQ|SR|IR)-\d{3,4}(?:\.\d+)*\b", text))
        for doc_type, text in per_doc_text.items()
    }
    result = {}
    doc_types = sorted(referenced)
    for i in range(len(doc_types)):
        for j in range(i + 1, len(doc_types)):
            a, b = doc_types[i], doc_types[j]
            set_a, set_b = referenced[a], referenced[b]
            overlap = len(set_a & set_b)
            union = len(set_a | set_b) or 1
            result[f"{a}_vs_{b}"] = {"overlap": overlap, "jaccard": round(overlap / union, 3)}
    return result


def write_scoring_sheet(report: dict, path: str | Path) -> str:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for doc_type, metrics in report.get("documents", {}).items():
        rows.append(
            {
                "doc_type": doc_type,
                "version": metrics["version"],
                "requirement_coverage": metrics["requirement_coverage"],
                "template_conformance": metrics["template_conformance"],
                "compliance_status": metrics["compliance_status"],
                "human_review_score": "",
                "human_comments": "",
            }
        )
    for pair, metrics in report.get("similarity", {}).items():
        rows.append(
            {
                "doc_type": pair,
                "version": "",
                "requirement_coverage": "",
                "template_conformance": "",
                "compliance_status": f"rouge1={metrics['rouge1']} rougeL={metrics['rougeL']}",
                "human_review_score": "",
                "human_comments": "",
            }
        )
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return str(path)
