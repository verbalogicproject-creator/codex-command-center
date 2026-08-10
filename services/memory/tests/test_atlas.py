from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "build_atlas.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_atlas", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_atlas_snapshot_is_deterministic_and_source_backed():
    builder = load_builder()
    first = builder.build_data()
    second = builder.build_data()
    assert first == second
    assert first["schema_version"] == "nlke-gca-grounding-receipt-v1"
    assert first["climax_claim_id"] == "immutable-handoff"
    assert first["migration"] == 8
    assert first["counts"]["claims"] == len(first["claims"])
    assert first["counts"]["routes"] >= 60
    assert first["counts"]["tests"] >= 100
    sources = {item["id"]: item for item in first["sources"]}
    for claim in first["claims"]:
        resolved = [sources[source_id] for source_id in claim["source_ids"]]
        assert resolved
        assert all(claim["id"] in item["claim_ids"] for item in resolved)
        assert any(
            item["kind"] == "test" or ".test." in item["path"]
            for item in resolved
        )
        assert all(item["url"].startswith(first["repository_url"]) for item in resolved)
        assert claim["receipt"]["snapshot_hash"] == first["snapshot_hash"]
        assert claim["receipt"]["grounding_path"] == claim["grounding_path"]
    assert "self-grounding-atlas" in {claim["id"] for claim in first["claims"]}


def test_atlas_extracts_sqlite_postgres_aria_schema_parity():
    data = load_builder().build_data()
    tables = {item["name"]: item for item in data["tables"]}
    for name in {
        "aria_command_definitions",
        "aria_command_aliases",
        "aria_profiles",
        "aria_voice_sessions",
        "aria_command_executions",
    }:
        engines = {location["engine"] for location in tables[name]["locations"]}
        assert engines == {"SQLite", "PostgreSQL"}


def test_generated_atlas_is_current_and_contains_no_runtime_payloads():
    builder = load_builder()
    output = builder.render(builder.build_data())
    assert (ROOT / "apps/web/public/atlas/index.html").read_text() == output
    assert "<title>Take a step back" in output
    assert "NLKE Grounded Continuity Architecture" in output
    assert '"schema_version":"nlke-gca-grounding-receipt-v1"' in output
    assert '"migration":8' in output
    lowered = output.lower()
    for forbidden in (
        '"api_key":',
        '"authorization":',
        '"audio":',
        '"sdp":',
        "/data/data/com.termux",
    ):
        assert forbidden not in lowered
    payload = output.split(
        '<script id="atlas-data" type="application/json">', 1
    )[1].split("</script>", 1)[0]
    parsed = json.loads(payload)
    assert parsed["snapshot_hash"]
