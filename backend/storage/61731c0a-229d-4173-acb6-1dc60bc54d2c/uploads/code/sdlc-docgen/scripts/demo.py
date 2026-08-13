"""End-to-end demo of the SDLC DocGen system.

Drives the whole pipeline through the REST API:
ingest -> generate SRS/SDD/ICD/STP/STR -> review workflow -> version diff -> evaluation.

Usage:
    BASE_URL=http://localhost:8002 python scripts/demo.py
"""
import io
import json
import os
import sys
import uuid
import zipfile
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8002").rstrip("/")
API = f"{BASE_URL}/api/v1"
USERNAME = os.environ.get("DEMO_USER", "reviewer-demo")

sys.path.insert(0, str(ROOT))


def client() -> httpx.Client:
    return httpx.Client(timeout=600)


def post(path, **kwargs):
    resp = client().post(f"{API}{path}", **kwargs)
    resp.raise_for_status()
    return resp.json()


def get(path):
    resp = client().get(f"{API}{path}")
    resp.raise_for_status()
    return resp.json()


def codebase_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for path in sorted((ROOT / "sample_data" / "telemetry_acq").rglob("*")):
            if path.is_file():
                zf.writestr(str(path.relative_to(ROOT / "sample_data")), path.read_bytes())
    return buffer.getvalue()


def step(label: str) -> None:
    print(f"\n{'=' * 72}\n{label}\n{'=' * 72}")


def main() -> None:
    demo_id = uuid.uuid4().hex[:6]
    project_name = f"demo-{demo_id}"

    step(f"1. Create project {project_name}")
    project = post("/projects", json={"name": project_name, "description": "Full-pipeline demo"})
    pid = project["id"]
    print(f"project_id={pid}")

    step("2. Upload and ingest sources (SysRS, IRS, MoM, codebase zip)")
    fixtures = ROOT / "sample_data" / "fixtures"
    files = [
        ("files", (fixtures / "SysRS_v3.1.docx").open("rb")),
        ("files", (fixtures / "IRS_v2.0.docx").open("rb")),
        ("files", (fixtures / "MoM_DesignReview04.docx").open("rb")),
    ]
    with client() as http:
        resp = http.post(f"{API}/projects/{pid}/uploads", files=files)
        resp.raise_for_status()
        result = resp.json()
        print(json.dumps(result, indent=2))
        resp = http.post(
            f"{API}/projects/{pid}/uploads",
            files=[("files", ("telemetry_acq.zip", codebase_zip(), "application/zip"))],
        )
        resp.raise_for_status()
        print(json.dumps(resp.json(), indent=2))

    step("3. Requirements registry")
    requirements = get(f"/projects/{pid}/requirements")
    print(f"{requirements['total']} requirements extracted")
    for row in requirements["requirements"]:
        print(f"  {row['req_id']:14} [{row['source']:5}] {row['req_type']:14} {row['text'][:70]}")

    step("4. Traceability links")
    traceability = get(f"/projects/{pid}/traceability")
    print(f"{traceability['total']} links")
    for link in traceability["links"][:25]:
        print(f"  {link['from']}  ->  {link['to']}  ({link['link_type']}, {link['source']})")

    step("5. Generate documents SRS -> SDD -> ICD -> STP -> STR")
    reports = {}
    for doc_type in ["SRS", "SDD", "ICD", "STP", "STR"]:
        print(f"\n  --- generating {doc_type} ---")
        report = post(f"/projects/{pid}/generate/{doc_type}", json={})
        reports[doc_type] = report
        compliance = report["compliance"]
        print(
            f"  {doc_type} v{report['version']}: compliance={compliance['status']} "
            f"missing_refs={len(compliance['missing_requirement_references'])} "
            f"uncovered={len(compliance['uncovered_requirements'])} "
            f"git={report['git_commit_sha'][:10]} llm={report['model_metadata']['llm_client']}"
        )

    step("6. Review workflow on SRS (submit -> reject section -> regenerate -> approve)")
    srs = next(d for d in get(f"/projects/{pid}/documents")["documents"] if d["doc_type"] == "SRS")
    doc_id = srs["id"]
    post(f"/documents/{doc_id}/submit", json={"username": USERNAME})
    print("  submitted for review")
    review = post(
        f"/documents/{doc_id}/versions/1/sections/1/review",
        json={"username": USERNAME, "decision": "rejected", "comment": "Purpose must cite REQ-0001 explicitly."},
    )
    print(f"  section rejected: document status={review['document_status']}")
    regen = post(
        f"/documents/{doc_id}/versions/1/sections/1/regenerate",
        json={"username": USERNAME, "comment": "Purpose must cite REQ-0001 explicitly."},
    )
    print(f"  regenerated section 1 -> new version {regen['new_version']} (compliance {regen['compliance']['status']})")
    post(
        f"/documents/{doc_id}/versions/2/sections/1/review",
        json={"username": USERNAME, "decision": "approved", "comment": "Looks good."},
    )
    print("  section 1 approved")
    approval = post(f"/documents/{doc_id}/approve", json={"username": USERNAME})
    print(f"  document approved: {approval}")

    step("7. Version history and section-aware diff")
    detail = get(f"/documents/{doc_id}")
    for version in detail["versions"]:
        print(f"  v{version['version']}: {version['status']} git={version['git_commit_sha']}")
    diff = get(f"/documents/{doc_id}/versions/2/diff")
    print("  diff v1 -> v2:")
    for change in diff["changes"]:
        if change["changed"]:
            print(f"    section {change['section_id']}: {change['action']}")

    step("8. Evaluation harness")
    report = post(f"/projects/{pid}/eval/run", json={})
    print(f"  requirements: {report['requirements']}")
    print(f"  traceability: {report['traceability']}")
    print("  document metrics:")
    for doc_type, metrics in report["documents"].items():
        print(
            f"    {doc_type}: coverage {metrics['covered']}/{metrics['total_requirements']} "
            f"conformance {metrics['sections_present']}/{metrics['sections_expected']} "
            f"compliance={metrics['compliance_status']}"
        )
    print("  cross-document consistency:")
    for pair, metrics in report["cross_document_consistency"].items():
        print(f"    {pair}: {metrics}")
    print("  similarity vs source:")
    for doc_type, metrics in report["similarity"].items():
        print(f"    {doc_type}: {metrics}")

    scoring = f"{API}/projects/{pid}/eval/scoring-sheet.csv"
    print(f"\n  human-review scoring sheet: {scoring}")

    out_dir = ROOT / "backend" / "storage" / "demo-output"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"project_{pid}.json").write_text(json.dumps(report, indent=2, default=str))
    print(f"\nDemo complete. Project id: {pid}")
    print(f"Open the web UI and use project: {project_name}")
    print(f"Download DOCX at: {API}/projects/{pid}/documents/SRS/download")


if __name__ == "__main__":
    main()
