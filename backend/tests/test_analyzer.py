import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_analyze_project_endpoint(tmp_path):
    import zipfile

    # Create dummy test zip file
    zip_file = tmp_path / "test_project.zip"
    with zipfile.ZipFile(zip_file, "w") as zf:
        zf.writestr("main.py", "def main():\n    print('Hello World')\n")
        zf.writestr("utils.py", "def add(a, b):\n    return a + b\n")

    with open(zip_file, "rb") as f:
        response = client.post(
            "/api/v1/analyze/project",
            files={"file": ("test_project.zip", f, "application/zip")},
        )

    print("RESPONSE JSON:", response.json())
    assert response.status_code == 200
    data = response.json()
    assert "structure" in data
    assert "working_purpose" in data
    assert "functioning" in data
    assert "improvements_and_corrections" in data
    assert "readme_markdown" in data
    assert data["total_files"] >= 2
