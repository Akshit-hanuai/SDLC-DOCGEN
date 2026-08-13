from app.services.template_store import template_store


def test_store_has_srs_template():
    schema = template_store.get("srs")
    assert schema is not None
    assert schema.doc_type == "SRS"
    assert schema.name == "Software Requirements Specification"
    assert len(schema.sections) >= 6


def test_all_templates_validate():
    errors = template_store.validate_all()
    assert errors == []


def test_srs_section_structure():
    schema = template_store.get("srs")
    assert schema is not None
    functional = next(s for s in schema.sections if s.id == "3")
    assert functional.type == "requirements"
    assert functional.requirement_filter is not None
    assert functional.requirement_filter.req_type == "functional"
    assert "sysrs" in functional.data_sources
    matrix = next(s for s in schema.sections if s.id == "6")
    assert matrix.type == "traceability_matrix"


def test_template_not_found():
    assert template_store.get("does-not-exist") is None
