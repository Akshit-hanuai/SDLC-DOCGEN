from collections import defaultdict
from dataclasses import dataclass

from app.services.ingest.models import CodeAnalysis, MoMRecord, RequirementExtract
from app.services.ingest.requirements_extractor import find_req_ids

LINK_TYPES = {
    ("sysrs", "sysrs"): "refines",
    ("sysrs", "irs"): "derives",
    ("irs", "sysrs"): "derives",
    ("mom", "sysrs"): "traces_to",
    ("mom", "irs"): "traces_to",
    ("code", "sysrs"): "implements",
    ("code", "irs"): "implements",
}


@dataclass
class ProposedLink:
    from_req_id: str
    to_req_id: str
    link_type: str
    source: str
    confidence: float


def link_extracts(extracts: list[RequirementExtract]) -> list[ProposedLink]:
    links: list[ProposedLink] = []
    by_source: dict[str, dict[str, RequirementExtract]] = defaultdict(dict)
    for extract in extracts:
        by_source[extract.source][extract.req_id] = extract

    ids_by_source = {source: set(extracts_) for source, extracts_ in by_source.items()}

    seen: set[tuple[str, str, str]] = set()
    for from_source, extracts_ in by_source.items():
        for extract in extracts_.values():
            for referenced in find_req_ids(extract.context):
                if referenced == extract.req_id:
                    continue
                for to_source, ids in ids_by_source.items():
                    if referenced not in ids:
                        continue
                    link_type = LINK_TYPES.get((from_source, to_source), "traces_to")
                    key = (extract.req_id, referenced, link_type)
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append(
                        ProposedLink(
                            from_req_id=extract.req_id,
                            to_req_id=referenced,
                            link_type=link_type,
                            source="linker",
                            confidence=0.7,
                        )
                    )
    return links


def link_code_artifacts(analyses: list[CodeAnalysis]) -> list[ProposedLink]:
    links: list[ProposedLink] = []
    for analysis in analyses:
        for artifact in analysis.artifacts + analysis.endpoints + analysis.messages:
            for req_id in artifact.req_ids:
                links.append(
                    ProposedLink(
                        from_req_id=artifact.artifact_id,
                        to_req_id=req_id,
                        link_type="implements",
                        source="linker",
                        confidence=0.8,
                    )
                )
    return links


def link_mom(records: list[MoMRecord], known_ids: set[str]) -> tuple[list[ProposedLink], list[RequirementExtract]]:
    links: list[ProposedLink] = []
    new_requirements: list[RequirementExtract] = []
    new_seen: set[str] = set()
    for record in records:
        ids = list(dict.fromkeys(record.req_ids))
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                links.append(
                    ProposedLink(
                        from_req_id=ids[i],
                        to_req_id=ids[j],
                        link_type="traces_to",
                        source="linker",
                        confidence=0.6,
                    )
                )
        for req_id in ids:
            if req_id not in known_ids and req_id not in new_seen:
                new_requirements.append(
                    RequirementExtract(
                        req_id=req_id,
                        text=record.text[:300],
                        context=f"MoM {record.kind}",
                        source="mom",
                    )
                )
                new_seen.add(req_id)
    return links, new_requirements
