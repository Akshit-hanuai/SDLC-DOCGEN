import re

from app.services.ingest.models import MoMRecord, ParsedDocument
from app.services.ingest.requirements_extractor import find_req_ids

_ACTION_PATTERNS = [
    re.compile(r"action\s+item\s*[:#-]", re.I),
    re.compile(r"\baction\b\s*[:#-]", re.I),
    re.compile(r"to[- ]do\s*[:#-]", re.I),
    re.compile(r"responsible\s*[:#-]", re.I),
    re.compile(r"\bowner\s*[:#-]", re.I),
]

_DECISION_PATTERNS = [
    re.compile(r"^(decision|decided|agreed|resolved|consensus|conclusion)\s*[:#-]", re.I),
    re.compile(r"\bdecided that\b", re.I),
]

_CHANGE_PATTERNS = [
    re.compile(r"chang(e|es|ed)\b", re.I),
    re.compile(r"\bmodif(y|ied|ication)\b", re.I),
    re.compile(r"\badd(ed|ition)?\s+(a\s+)?(new\s+)?(requirement|req|clause)\b", re.I),
    re.compile(r"\bupdate(s|d)?\b.*\brequirement\b", re.I),
    re.compile(r"\bdelete\b.*\brequirement\b", re.I),
    re.compile(r"requirement\s+change", re.I),
]

_OWNER_RE = re.compile(r"(?:responsible|owner|actionee|assignee)\s*[:#-]\s*([A-Za-z][\w.\- ]{2,40})", re.I)
_DUE_RE = re.compile(r"(?:due|deadline|target)\s*[:#-]\s*(\w[\w/\- ]{0,20})", re.I)


def extract_mom(parsed: ParsedDocument, source: str) -> list[MoMRecord]:
    records: list[MoMRecord] = []
    lines = [l.strip() for l in parsed.text.splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        line = lines[i]
        req_ids = find_req_ids(line)
        if _ACTION_PATTERNS and any(p.search(line) for p in _ACTION_PATTERNS):
            text, j = _gather_bullets(lines, i)
            records.append(
                MoMRecord(
                    kind="action_item",
                    text=text,
                    owner=_extract(_OWNER_RE, text),
                    due=_extract(_DUE_RE, text),
                    req_ids=req_ids,
                )
            )
            i = j
            continue
        if any(p.search(line) for p in _DECISION_PATTERNS):
            text, j = _gather_bullets(lines, i)
            records.append(
                MoMRecord(kind="decision", text=text, req_ids=req_ids + find_req_ids(text))
            )
            i = j
            continue
        if req_ids and any(p.search(line) for p in _CHANGE_PATTERNS):
            text, j = _gather_bullets(lines, i)
            records.append(
                MoMRecord(kind="requirement_change", text=text, req_ids=req_ids + find_req_ids(text))
            )
            i = j
            continue
        i += 1
    return records


def _gather_bullets(lines: list[str], start: int) -> tuple[str, int]:
    text = lines[start]
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if line.startswith(("-", "*", "•", "o")) or (line and not line[0].isupper() and j > start and len(line) < 120):
            text += " " + line
            j += 1
        else:
            break
    return " ".join(text.split()), j


def _extract(pattern: re.Pattern[str], text: str) -> str | None:
    match = pattern.search(text)
    return match.group(1).strip() if match else None
