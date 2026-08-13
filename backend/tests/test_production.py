"""Tests for production hardening: request correlation, error envelope, upload safety."""

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.routes.uploads import _safe_name
from app.main import app
from app.services.ingest.pipeline import extract_upload

client = TestClient(app)


def test_request_id_is_echoed():
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-REQUEST-ID")


def test_unknown_project_is_404_with_masked_error():
    resp = client.delete("/api/v1/projects/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert "detail" in resp.json()


def test_validation_error_returns_request_id():
    resp = client.post("/api/v1/projects", json={"name": ""})
    assert resp.status_code == 422
    body = resp.json()
    assert body["request_id"]
    assert isinstance(body["detail"], list)


def test_safe_name_strips_paths_and_control_chars():
    assert _safe_name("../../etc/passwd") == "passwd"
    assert _safe_name("a\\b\\c.txt") == "c.txt"
    assert _safe_name("evil\x00name.txt") == "evilname.txt"
    assert _safe_name("") == "file"
    assert len(_safe_name("x" * 400 + ".txt")) <= 255


def test_zip_slip_is_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../escape.txt", "nope")
    with pytest.raises(zipfile.BadZipFile):
        extract_upload("code.zip", buffer.getvalue(), "/tmp/opencode/safe-test")