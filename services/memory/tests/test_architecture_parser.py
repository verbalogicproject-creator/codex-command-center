from __future__ import annotations

import copy
import textwrap
from datetime import date
from pathlib import Path

import pytest

from aria_memory.architecture import (
    lint_architecture_document,
    parse_architecture_document,
    scaffold_ai_card,
)

ROOT = Path(__file__).resolve().parents[3]


def card_yaml(*, nested: bool = False, audience: str = "[engineer, ai_agent]") -> str:
    content = textwrap.dedent(f"""\
        id: arch.test.component
        kind: architecture_doc
        audience: {audience}
        status: implemented
        owner_area: platform
        main_files:
          - services/component.py
        public_interfaces:
          - "component.run()"
        provides:
          - architecture awareness
        depends_on:
          - arch.test.storage
        safe_edit_points:
          - parser normalization
        risk_areas:
          - declaration drift
        graph_rag_entities:
          - ArchitectureCard
        last_verified: 2026-07-18
        repository: Test Repository
        title: Test Component
    """)
    if not nested:
        return content
    return "ai_card:\n" + textwrap.indent(content, "  ")


def frontmatter_document() -> str:
    return (
        f"---\n{card_yaml()}---\n\n"
        "# Test Component\n\n"
        "Preamble.\n\n"
        "## Contract\n\nThe contract.\n"
    )


def fenced_document() -> str:
    return (
        "# Test Component\n\n"
        f"```yaml\n{card_yaml(nested=True)}```\n\n"
        "Preamble.\n\n"
        "## Contract\n\nThe contract.\n"
    )


def issue_codes(result) -> set[str]:
    return {issue.code for issue in result.issues}


def test_both_dialects_normalize_to_the_same_card():
    front = parse_architecture_document(frontmatter_document(), "docs/front.md")
    fenced = parse_architecture_document(fenced_document(), "docs/fenced.md")

    assert front.valid is True
    assert fenced.valid is True
    assert front.dialect == "frontmatter"
    assert fenced.dialect == "fenced-ai-card"
    assert front.card == fenced.card
    assert front.sections[0].heading == fenced.sections[0].heading == "Contract"


@pytest.mark.parametrize(("name", "dialect"), [
    ("frontmatter-component.md", "frontmatter"),
    ("fenced-component.md", "fenced-ai-card"),
])
def test_synthetic_repository_fixtures_cover_both_dialects(name, dialect):
    path = ROOT / "fixtures" / "demo" / "architecture" / name
    result = parse_architecture_document(
        path.read_text(encoding="utf-8"),
        f"fixtures/demo/architecture/{name}",
    )
    assert result.valid is True
    assert result.dialect == dialect
    assert result.card is not None
    assert result.card.repository == "Synthetic Architecture"
    assert len(result.sections) == 2


def test_scalar_audience_normalizes_without_mutating_input(monkeypatch):
    raw = {
        "id": "arch.test.component",
        "kind": "architecture_doc",
        "audience": "engineer",
        "status": "implemented",
        "owner_area": "platform",
        "main_files": [],
        "public_interfaces": [],
        "provides": [],
        "depends_on": [],
        "safe_edit_points": [],
        "risk_areas": [],
        "graph_rag_entities": [],
        "last_verified": "2026-07-18",
    }
    original = copy.deepcopy(raw)
    monkeypatch.setattr(
        "aria_memory.architecture.parser.yaml.safe_load",
        lambda _value: raw,
    )

    result = parse_architecture_document("---\nignored\n---\n# Title\n", "docs/test.md")

    assert result.card is not None
    assert result.card.audience == ["engineer"]
    assert raw == original


def test_non_card_yaml_fence_is_ignored_before_ai_card():
    text = (
        "# Test\n\n"
        "```yaml\nsettings:\n  retries: 2\n```\n\n"
        f"```yaml\n{card_yaml(nested=True)}```\n"
    )
    result = parse_architecture_document(text, "docs/test.md")
    assert result.valid is True
    assert result.dialect == "fenced-ai-card"
    assert result.card is not None
    assert result.card.id == "arch.test.component"


def test_identical_dual_declarations_are_accepted():
    text = (
        f"---\n{card_yaml()}---\n\n"
        "# Test Component\n\n"
        f"```yaml\n{card_yaml(nested=True)}```\n"
    )
    result = parse_architecture_document(text, "docs/test.md")
    assert result.valid is True
    assert result.dialect == "dual"


def test_conflicting_dual_declarations_fail_lint():
    fenced = card_yaml(nested=True).replace(
        "status: implemented", "status: planning",
    )
    text = f"---\n{card_yaml()}---\n\n```yaml\n{fenced}```\n"
    result = parse_architecture_document(text, "docs/test.md")
    assert result.valid is False
    assert result.card is None
    assert "conflicting_declarations" in issue_codes(result)


def test_h2_chunking_uses_ast_and_disambiguates_repeated_headings():
    text = (
        f"---\n{card_yaml()}---\n\n"
        "# Test\n\n"
        "## Contract\n\n"
        "```bash\n"
        "echo '## not a heading'\n"
        "```\n\n"
        "## Contract\n\nSecond contract.\n"
    )
    result = parse_architecture_document(text, "docs/test.md")
    assert [section.heading for section in result.sections] == ["Contract", "Contract"]
    assert [section.id for section in result.sections] == [
        "arch.test.component#contract",
        "arch.test.component#contract-2",
    ]
    assert "not a heading" in result.sections[0].body


def test_partial_card_gets_degraded_id_and_typed_issues():
    text = "---\nkind: architecture_doc\n---\n\n# Partial\n"
    result = parse_architecture_document(text, "docs/partial.md")
    assert result.card is not None
    assert result.card.id.startswith("arch.unindexed.")
    assert result.valid is False
    assert {"missing_required_slots", "generated_degraded_id"} <= issue_codes(result)


def test_missing_and_malformed_cards_produce_issues():
    missing = parse_architecture_document("# No card\n", "docs/missing.md")
    malformed = parse_architecture_document(
        "---\nid: [unclosed\n---\n\n# Broken\n",
        "docs/broken.md",
    )
    assert missing.card is None
    assert "missing_ai_card" in issue_codes(missing)
    assert next(
        issue for issue in missing.issues if issue.code == "missing_ai_card"
    ).severity == "warning"
    assert malformed.card is None
    assert {"invalid_frontmatter_yaml", "missing_ai_card"} <= issue_codes(malformed)


@pytest.mark.parametrize("source_uri", [
    "/absolute/doc.md",
    "../outside.md",
    "docs/../../outside.md",
    r"docs\\windows.md",
])
def test_source_uri_must_be_repository_relative(source_uri):
    with pytest.raises(ValueError, match="source_uri"):
        parse_architecture_document(frontmatter_document(), source_uri)


def test_oversize_document_fails_closed():
    with pytest.raises(ValueError, match="exceeds"):
        parse_architecture_document(
            frontmatter_document(),
            "docs/test.md",
            max_bytes=10,
        )


def test_invalid_field_shapes_are_reported_without_crashing():
    text = frontmatter_document().replace(
        "main_files:\n  - services/component.py",
        "main_files:\n  path: services/component.py",
    )
    result = parse_architecture_document(text, "docs/test.md")
    assert result.valid is False
    assert "invalid_list_field" in issue_codes(result)


def test_scaffold_emits_a_complete_valid_card():
    text = scaffold_ai_card(
        card_id="arch.new.component",
        title="New Component",
        repository="Test Repository",
        last_verified=date(2026, 7, 18),
    )
    report = lint_architecture_document(text, "docs/new-component.md")
    assert report.valid is True
    assert report.card_id == "arch.new.component"
    assert report.section_count == 3
