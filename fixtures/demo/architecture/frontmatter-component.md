---
id: synthetic.frontmatter.component
repository: Synthetic Architecture
title: Frontmatter Component
kind: architecture_doc
audience:
  - engineer
  - ai_agent
status: implemented
owner_area: synthetic platform
main_files:
  - services/synthetic/frontmatter.py
public_interfaces:
  - "frontmatter_component.run()"
provides:
  - frontmatter architecture fixture
depends_on:
  - synthetic.shared.contract
safe_edit_points:
  - fixture prose
risk_areas:
  - fixture drift
graph_rag_entities:
  - FrontmatterComponent
last_verified: 2026-07-18
---

# Frontmatter Component

## Purpose

Exercise the fleet-standard root-frontmatter architecture declaration.

## Contract

The fixture is synthetic and contains no private repository content.
