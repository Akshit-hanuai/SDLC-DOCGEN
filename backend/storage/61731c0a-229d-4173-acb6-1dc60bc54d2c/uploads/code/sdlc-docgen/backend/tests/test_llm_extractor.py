from app.services.ingest.llm_extractor import (
    llm_extract_details,
    normalize_mom_records,
    normalize_requirements,
    parse_json_block,
)
from app.services.ingest.models import ParsedDocument
from app.services.llm.client import MockLLMClient


class _FakeQwen:
    name = "vllm"

    def __init__(self, payload: str):
        self.payload = payload

    def complete(self, system: str, user: str) -> str:
        return self.payload


def test_parse_json_block_fenced():
    text = 'Sure!\n```json\n{"requirements": []}\n```'
    assert parse_json_block(text) == {"requirements": []}


def test_parse_json_block_plain():
    assert parse_json_block('{"a": 1}') == {"a": 1}


def test_parse_json_block_garbage():
    assert parse_json_block("no json here") is None
    assert parse_json_block(None) is None


def test_normalize_requirements_filters_and_coerces():
    raw = [
        {
            "req_id": "REQ-0001",
            "text": "MTBF not less than 2000 hours.",
            "type": "non_functional",
            "priority": "P1",
            "verification": "Demonstration",
            "measure": "hours",
            "target": "2000",
        },
        {"req_id": "REQ-0002", "text": "shall buffer samples."},
        {"req_id": "BAD", "text": "not a valid requirement id"},
        "not-a-dict",
    ]
    extracts = normalize_requirements(raw, "sysrs")
    assert [e.req_id for e in extracts] == ["REQ-0001", "REQ-0002"]
    assert extracts[0].req_type == "non_functional"
    assert extracts[0].extra == {
        "priority": "P1",
        "verification": "Demonstration",
        "measure": "hours",
        "target": "2000",
    }
    assert extracts[1].req_type == "functional"


def test_normalize_mom_records():
    raw = [
        {"kind": "action_item", "text": "Confirm auth mechanism.", "owner": "Rao", "due": "2026-09-15", "req_ids": ["REQ-0008"]},
        {"kind": "bogus", "text": "ignored"},
        {"kind": "decision", "text": "Version the REST API.", "req_ids": ["REQ-0005", "nope"]},
    ]
    records = normalize_mom_records(raw)
    assert len(records) == 2
    assert records[0].owner == "Rao"
    assert records[0].due == "2026-09-15"
    assert records[1].req_ids == ["REQ-0005"]


def test_llm_extract_details_parses_payload(monkeypatch):
    from app.services.ingest import llm_extractor as mod

    payload = (
        '{"requirements": [{"req_id": "REQ-0001", "text": "The system shall acquire telemetry.", '
        '"type": "functional", "priority": "P1", "verification": "HIL test"}, '
        '{"req_id": "FAKE-999", "text": "hallucinated"}]}'
    )
    monkeypatch.setattr(mod, "get_llm_client", lambda: _FakeQwen(payload))
    parsed = ParsedDocument(
        filename="sysrs.docx", doc_type="sysrs", text="REQ-0001 The system shall acquire telemetry."
    )
    result = llm_extract_details(parsed, "sysrs")
    assert result is not None
    requirements = result["requirements"]
    assert len(requirements) == 1
    assert requirements[0].req_id == "REQ-0001"
    assert requirements[0].extra["priority"] == "P1"


def test_llm_extract_details_mom(monkeypatch):
    from app.services.ingest import llm_extractor as mod

    payload = '{"mom_records": [{"kind": "action_item", "text": "Update SysRS.", "owner": "Sharma", "req_ids": ["REQ-0001"]}]}'
    monkeypatch.setattr(mod, "get_llm_client", lambda: _FakeQwen(payload))
    parsed = ParsedDocument(filename="mom.docx", doc_type="mom", text="Action item: Update SysRS REQ-0001.")
    result = llm_extract_details(parsed, "mom")
    assert result is not None
    assert result["mom_records"][0].kind == "action_item"
    assert result["mom_records"][0].owner == "Sharma"


def test_llm_extract_details_offline_returns_none(monkeypatch):
    from app.services.ingest import llm_extractor as mod

    monkeypatch.setattr(mod, "get_llm_client", lambda: MockLLMClient())
    parsed = ParsedDocument(filename="sysrs.docx", doc_type="sysrs", text="REQ-0001 text.")
    assert llm_extract_details(parsed, "sysrs") is None
