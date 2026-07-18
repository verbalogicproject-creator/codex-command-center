from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from pydantic import ValidationError

from aria_memory.architecture import (
    ArchitectureManifest,
    scan_architecture_repository,
)

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "fixtures" / "demo" / "architecture"


def sync_payload(*names: str) -> dict:
    return {
        "repository": {
            "id": "synthetic-architecture",
            "name": "Synthetic Architecture",
            "aliases": ["synthetic-checkout"],
        },
        "source_revision": "revision-one",
        "manifest_hash": "a" * 64,
        "documents": [
            {
                "source_uri": f"fixtures/demo/architecture/{name}",
                "content": (FIXTURES / name).read_text(encoding="utf-8"),
            }
            for name in names
        ],
    }


def test_authenticated_sync_and_health_share_snapshot_receipt(client):
    payload = sync_payload(
        "frontmatter-component.md",
        "fenced-component.md",
    )
    response = client.post("/api/v1/architecture/sync", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["status"] == "active"
    assert body["health"]["snapshot_id"] == body["snapshot"]["id"]
    assert body["health"]["snapshot_status"] == "active"
    assert body["health"]["valid_cards"] == 2
    assert body["health"]["coverage"] == 1
    assert "unresolved_architecture_edges" in body["health"]["degraded_reasons"]
    assert "content" not in body

    by_alias = client.get(
        "/api/v1/architecture/health",
        params={"repository": "synthetic-checkout"},
    )
    assert by_alias.status_code == 200
    assert by_alias.json()["snapshot_id"] == body["snapshot"]["id"]


def test_lint_is_stateless_and_reports_coverage(client):
    payload = sync_payload("frontmatter-component.md")
    lint = client.post("/api/v1/architecture/lint", json={
        "repository": payload["repository"],
        "documents": payload["documents"],
    })
    assert lint.status_code == 200
    assert lint.json()["valid"] is True
    assert lint.json()["coverage"] == 1
    assert len(lint.json()["corpus_hash"]) == 64
    health = client.get(
        "/api/v1/architecture/health",
        params={"repository": "synthetic-architecture"},
    )
    assert health.json()["degraded_reasons"] == ["repository_unregistered"]


def test_hash_only_check_reports_drift_without_document_bodies(client):
    payload = sync_payload("frontmatter-component.md")
    synced = client.post("/api/v1/architecture/sync", json=payload).json()
    document = payload["documents"][0]
    content_hash = hashlib.sha256(document["content"].encode("utf-8")).hexdigest()
    exact = client.post("/api/v1/architecture/check", json={
        "repository": "synthetic-architecture",
        "source_revision": "revision-one",
        "manifest_hash": "a" * 64,
        "documents": [{
            "source_uri": document["source_uri"],
            "content_hash": content_hash,
        }],
    })
    assert exact.status_code == 200
    assert exact.json()["snapshot_id"] == synced["snapshot"]["id"]
    assert exact.json()["stale_sources"] == []
    assert "local_snapshot_drift" not in exact.json()["degraded_reasons"]

    drift = client.post("/api/v1/architecture/check", json={
        "repository": "synthetic-architecture",
        "source_revision": "revision-two",
        "manifest_hash": "b" * 64,
        "documents": [{
            "source_uri": document["source_uri"],
            "content_hash": "c" * 64,
        }],
    })
    assert drift.status_code == 200
    reasons = drift.json()["degraded_reasons"]
    assert "local_snapshot_drift" in reasons
    assert "source_revision_mismatch" in reasons
    assert "manifest_hash_mismatch" in reasons
    assert drift.json()["stale_sources"][0]["reason"] == "content_hash_changed"


def test_sync_activates_visible_missing_card_gap(client):
    payload = sync_payload("frontmatter-component.md")
    payload["documents"].append({
        "source_uri": "docs/undocumented.md",
        "content": "# Undocumented helper\n",
    })
    response = client.post("/api/v1/architecture/sync", json=payload)
    assert response.status_code == 200
    health = response.json()["health"]
    assert health["snapshot_status"] == "active"
    assert health["coverage"] == 0.5
    assert health["missing_cards"] == ["docs/undocumented.md"]
    assert "architecture_card_gaps" in health["degraded_reasons"]


def test_sync_rejects_repository_mismatch_without_active_snapshot(client):
    payload = sync_payload("frontmatter-component.md")
    payload["repository"] = {
        "id": "other-repository",
        "name": "Other Repository",
        "aliases": [],
    }
    response = client.post("/api/v1/architecture/sync", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot"]["status"] == "rejected"
    assert body["health"]["snapshot_status"] == "rejected"
    assert "architecture_conflicts" in body["health"]["degraded_reasons"]

    health = client.get(
        "/api/v1/architecture/health",
        params={"repository": "other-repository"},
    ).json()
    assert health["snapshot_id"] is None
    assert health["degraded_reasons"] == ["architecture_snapshot_missing"]


def test_architecture_sync_requires_workspace_authentication(client):
    client.cookies.clear()
    response = client.post(
        "/api/v1/architecture/sync",
        json=sync_payload("frontmatter-component.md"),
    )
    assert response.status_code == 401


def write_manifest(root: Path, body: str) -> None:
    manifest = root / ".command-center" / "architecture.yaml"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(body, encoding="utf-8")


def manifest_text(*, root: str = "docs", extra: str = "") -> str:
    return f"""\
schema_version: 1
repository:
  id: test-repository
  name: Test Repository
  aliases: [test-checkout]
documents:
  roots: [{root}]
  patterns: ["**/*.md"]
  exclude: ["docs/excluded/**"]
dialects: [frontmatter, fenced-ai-card]
{extra}"""


def test_manifest_scan_from_nested_directory_is_bounded_and_deterministic(tmp_path):
    write_manifest(tmp_path, manifest_text())
    docs = tmp_path / "docs"
    (docs / "nested").mkdir(parents=True)
    (docs / "nested" / "component.md").write_text(
        "# Component\n", encoding="utf-8",
    )
    (docs / "excluded").mkdir()
    (docs / "excluded" / "private.md").write_text(
        "# Excluded\n", encoding="utf-8",
    )
    (docs / "ignored.html").write_text("<h1>Ignored</h1>", encoding="utf-8")

    inventory = scan_architecture_repository(docs / "nested")
    assert inventory.repository_root == tmp_path.resolve()
    assert inventory.manifest.repository.id == "test-repository"
    assert [item.source_uri for item in inventory.documents] == [
        "docs/nested/component.md"
    ]
    assert len(inventory.manifest_hash) == 64
    assert set(inventory.content_hashes) == {"docs/nested/component.md"}


def test_manifest_rejects_traversal_and_unknown_secret_fields(tmp_path):
    write_manifest(tmp_path, manifest_text(root="../outside"))
    with pytest.raises(ValueError, match="traverse"):
        scan_architecture_repository(tmp_path)

    with pytest.raises(ValidationError, match="token"):
        ArchitectureManifest.model_validate({
            "schema_version": 1,
            "repository": {
                "id": "test-repository",
                "name": "Test Repository",
                "aliases": [],
                "token": "must-not-be-accepted",
            },
            "documents": {"roots": ["docs"]},
            "dialects": ["frontmatter"],
        })


def test_manifest_rejects_symlink_escape(tmp_path):
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    write_manifest(tmp_path, manifest_text())
    docs = tmp_path / "docs"
    docs.mkdir()
    try:
        (docs / "escape.md").symlink_to(outside)
    except OSError:
        pytest.skip("symlinks unavailable")
    with pytest.raises(ValueError, match="symlink escapes"):
        scan_architecture_repository(tmp_path)


def test_command_center_manifest_selects_markdown_not_opus_html():
    inventory = scan_architecture_repository(ROOT)
    selected = {item.source_uri for item in inventory.documents}
    assert "docs/command-center-atlas.html" not in selected
    assert "docs/plans/full-architecture-awareness.md" in selected
