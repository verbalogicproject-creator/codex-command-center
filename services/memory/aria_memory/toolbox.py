from __future__ import annotations

import base64
import hashlib
import io
import json
import re
from typing import Any

from PIL import Image

from .architecture import ArchitectureBriefRequest, ArchitectureCompiler
from .context import ContextCompiler, estimate_tokens
from .db import Database
from .models import (
    Capability, CapabilityInput, CapabilityRecommendation,
    CapabilityRecommendationRequest, CapabilityRecommendations, Handoff,
    HandoffDraftRequest, HandoffLoadRequest, HandoffPacket, HandoffUpdateRequest,
    PlanningReceipt, RedesignSuggestion, ScreenshotAnalysis,
    ScreenshotAnalyzeRequest, TourScript, TourScriptRequest, TourStep,
    VisualComparisonAnalyzeRequest, VisualComparisonReceipt,
    VisualSourceAnalysis, utc_now,
)
from .store import uid


INITIAL_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "stable_id": "taste-frontend-redesign-interview",
        "name": "Taste-guided frontend redesign interview",
        "kind": "workflow",
        "description": (
            "Audit an existing interface, infer its design language, and conduct "
            "an evidence-bound redesign interview before proposing repository changes."
        ),
        "triggers": [
            "taste", "screenshot", "frontend redesign", "visual redesign",
            "design system", "design audit", "design dials", "visual hierarchy",
            "typography", "spacing", "motion", "responsive",
        ],
        "instructions": """
Purpose

Turn a screenshot and redesign request into an informed interview and bounded
implementation plan. Do not edit code merely because this workflow was loaded.
The repository evidence and approved handoff remain authoritative; screenshot
observations and aesthetic judgments are inferences.

1. Establish the evidence boundary

- State the repository identity, architecture snapshot, capability version, and
  cited evidence IDs received in the handoff.
- Summarize declared framework, styling system, component boundaries, safe edit
  points, risks, responsive rules, accessibility behavior, and interactions that
  must be preserved.
- Label every screenshot observation as an inference until repository evidence
  confirms it.
- If architecture is stale, missing, mismatched, or degraded, expose that state
  and interview before planning around the gap. Never fall back to another
  repository.
- When the handoff contains multiple visual sources, preserve their declared
  roles. Treat `current` as evidence of the existing presentation,
  `reference` as a direction rather than a specification, and `constraint` as
  a boundary. Report the comparison receipt's preserve, adopt, avoid,
  conflicts, and unresolved groups without blending their provenance.
- Raw visual-source bytes never enter the handoff or Codex. Use only the
  role-labelled hashes, dimensions, findings, and comparison receipt.

2. Read the design brief before choosing an aesthetic

Infer the surface type, audience, desired outcome, reference signals, existing
brand assets, and quiet constraints such as accessibility, regulation,
performance, or mobile use. Classify the work as targeted evolution, structural
redesign, or greenfield. For an existing application, preserve its information
architecture and operating model unless the user explicitly approves a change.

Give a concise design read, then propose initial values from 1 to 10 for:

- DESIGN_VARIANCE: predictable/symmetric to expressive/asymmetric;
- MOTION_INTENSITY: static/subtle to cinematic/physics-driven;
- VISUAL_DENSITY: gallery-airy to cockpit-dense.

These are interview proposals, not hidden defaults. Explain what repository and
screenshot evidence informed them.

3. Begin the redesign interview

Ask one focused question at a time. Cover only unresolved decisions. When an
interview contract is present, obey its question limit; the standard visual
comparison handoff allows at most three questions:

- What should users notice or accomplish first?
- Which current flows, navigation, copy, brand elements, and interactions must
  remain recognizable?
- Is the goal a careful evolution or a more structural visual overhaul?
- Which reference products or moods are desired, and which are explicitly
  unwanted?
- What variance, motion, and density levels feel correct?
- Which viewports, browsers, assistive technologies, and reduced-motion
  expectations define acceptance?
- What loading, empty, error, focus, hover, active, and offline/degraded states
  must be designed?
- What measurable acceptance criteria will determine success?

Do not dump every question at once. Use each answer to narrow the next question.
Do not proceed to implementation until the user confirms the design direction
and accepts the bounded plan.

4. Audit the existing interface before recommending changes

Inspect cited components and declarations, then assess:

- typography hierarchy, readable line length, weights, tracking, wrapping, and
  numeric alignment;
- palette consistency, contrast, accent discipline, shadows, surfaces, and
  theme behavior;
- grid, containment, spacing rhythm, optical alignment, mobile collapse, touch
  targets, and horizontal overflow;
- semantic structure, focus order, keyboard behavior, visible focus, labels,
  alternative text, and reduced motion;
- hover, pressed, loading, empty, error, disabled, and current-location states;
- copy specificity, real data boundaries, dead links, metadata, legal links,
  analytics contracts, and SEO-sensitive routes;
- animation purpose, cleanup, performance, and whether transforms/opacity can
  express it without layout thrashing.

Separate findings into preserve, improve, retire, and unresolved. Do not impose
marketing-page conventions on dashboards or dense product surfaces. When a
declared design system exists, work within it rather than mixing systems or
recreating official components.

5. Form the design contract

After the interview, produce an editable contract containing:

- the confirmed design read and three dial values;
- hierarchy and primary user journey;
- existing tokens and components to preserve;
- proposed typography, color, spacing, radius, elevation, icon, and motion
  rules;
- responsive behavior at 375, 768, 1024, and 1440 pixels;
- accessibility and reduced-motion requirements;
- component/state inventory;
- approved safe edit points and explicitly excluded areas;
- repository evidence supporting each material claim;
- screenshot-derived inferences that still require validation;
- risks, verification steps, and acceptance criteria.

Prefer targeted changes in this order: typography and hierarchy, spacing and
rhythm, color calibration, interaction states, motion, then structural
recomposition. Never silently change routes, navigation labels, form field
contracts, analytics identifiers, legal copy, brand marks, or durable data
semantics.

6. Anti-default and quality guardrails

- Do not default to purple/blue AI gradients, a centered hero, three equal
  feature cards, glassmorphism everywhere, generic placeholder copy, or motion
  without purpose.
- Use one coherent palette, accent strategy, radius system, icon family, and
  theme model unless declared evidence requires otherwise.
- Verify dependencies before proposing imports. Do not install packages or
  change the framework without explicit approval.
- Use semantic HTML and existing project conventions. Avoid fake product UI,
  invented evidence, hand-drawn replacement icons, dead controls, and
  placeholder implementation.
- Preserve contrast, keyboard access, at least 44-pixel touch targets, viewport
  stability, and reduced-motion fallbacks.
- Treat performance as part of design: protect LCP, INP, CLS, DOM cost, image
  sizing, and animation cleanup.

7. Plan and handoff

Produce the smallest coherent implementation phases. For every phase cite the
architecture evidence, list safe edit points and risks, name affected states and
viewports, and define verification. Show omitted alternatives and why the
selected direction won. End by asking the next informed interview question;
do not edit files until the user approves the plan.
""".strip(),
        "repositories": ["*"],
        "required_tools": [
            "load_handoff", "get_evidence", "walk_dependencies",
            "build_task_pack",
        ],
        "trust_status": "verified",
        "provenance": (
            "Provider-neutral adaptation of Taste Skill v2 experimental "
            "(design-taste-frontend) and redesign-existing-projects by Leonxlnx, "
            "MIT License, reviewed for Command Center's evidence and approval "
            "boundaries on 2026-07-19. Source: "
            "https://github.com/Leonxlnx/taste-skill. Source instruction SHA-256: "
            "aa194351b246b8b4799099d4ed7b033d29eab6e6e3d58d8d2172978be7b3ec89; "
            "redesign instruction SHA-256: "
            "98ad3e5b051bfb71b2795f7e8a6aa0d32b51ee095606c098a4b2822ac07926c9."
        ),
    },
    {
        "stable_id": "frontend-redesign-interview",
        "name": "Frontend redesign interview",
        "kind": "workflow",
        "description": "Turn a visual redesign request into an evidence-bound implementation interview.",
        "triggers": ["screenshot", "redesign", "layout", "visual hierarchy", "frontend"],
        "instructions": (
            "Before editing, summarize the injected visual inferences and repository evidence. "
            "Ask the user about the desired hierarchy, preserved interactions, responsive intent, "
            "and acceptance criteria. Cite evidence IDs. Inspect the declared safe edit points, "
            "then propose the smallest coherent change set."
        ),
        "repositories": ["*"],
        "required_tools": ["load_handoff", "get_evidence"],
        "trust_status": "verified",
        "provenance": "Command Center built-in capability; human reviewed.",
    },
    {
        "stable_id": "mobile-accessibility-review",
        "name": "Mobile accessibility review",
        "kind": "workflow",
        "description": "Review touch, keyboard, motion, contrast, and small-screen behavior.",
        "triggers": ["mobile", "accessibility", "a11y", "touch", "responsive", "contrast"],
        "instructions": (
            "Inspect declared responsive and accessibility boundaries. Interview for target devices "
            "and assistive technology. Verify focus order, touch targets, reduced motion, contrast, "
            "zoom, and narrow viewport behavior. Label screenshot observations as inferences."
        ),
        "repositories": ["*"],
        "required_tools": ["get_evidence", "walk_dependencies"],
        "trust_status": "verified",
        "provenance": "Command Center built-in capability; human reviewed.",
    },
    {
        "stable_id": "graph-canvas-integration",
        "name": "Graph-canvas integration",
        "kind": "skill",
        "description": "Change graph layouts without breaking evidence receipts or interaction contracts.",
        "triggers": ["graph", "canvas", "nodes", "edges", "dagre", "react flow"],
        "instructions": (
            "Load the graph architecture and dependency paths first. Preserve evidence IDs, node "
            "stages, edge semantics, keyboard navigation, viewport controls, and reduced-motion "
            "behavior. Separate visual layout changes from retrieval semantics."
        ),
        "repositories": ["Command Center"],
        "required_tools": ["get_evidence", "walk_dependencies"],
        "trust_status": "verified",
        "provenance": "Derived from declared Command Center graph documentation.",
    },
    {
        "stable_id": "evidence-bound-coding-plan",
        "name": "Evidence-bound coding plan",
        "kind": "template",
        "description": "Create an inspectable coding plan whose claims point to repository evidence.",
        "triggers": ["plan", "architecture", "risk", "implementation", "evidence"],
        "instructions": (
            "Distinguish verified repository facts from inferences. For every plan phase, cite the "
            "evidence IDs that justify it, list safe edit points and risks, and identify questions "
            "that must be answered before editing."
        ),
        "repositories": ["*"],
        "required_tools": ["recall_context", "get_evidence"],
        "trust_status": "verified",
        "provenance": "Command Center built-in planning template.",
    },
    {
        "stable_id": "safe-deployment-preparation",
        "name": "Safe deployment preparation",
        "kind": "policy",
        "description": "Prepare a deployable change without performing external deployment actions.",
        "triggers": ["deploy", "cloud run", "release", "production", "container"],
        "instructions": (
            "Inspect deployment declarations and secrets boundaries. Verify tests, production build, "
            "container startup, PORT handling, authentication, health behavior, migrations, rollback "
            "notes, and smoke-test commands. Do not deploy or modify cloud resources without separate "
            "explicit authority."
        ),
        "repositories": ["*"],
        "required_tools": ["get_evidence", "get_timeline"],
        "trust_status": "verified",
        "provenance": "Command Center deployment policy; human reviewed.",
    },
)

AVAILABLE_MCP_TOOLS = [
    "search_capabilities", "recommend_capabilities", "get_capability",
    "load_handoff", "build_task_pack", "recall_context", "get_evidence",
    "walk_dependencies", "get_timeline", "propose_memory_write",
]

REDESIGN_TERMS = {
    "redesign", "design", "frontend", "interface", "layout", "visual",
    "ui", "ux", "typography", "responsive", "screenshot",
}
MAX_OPEN_PLAN_STEPS = 12
MAX_OPEN_PLAN_STEP_LENGTH = 500


class Toolbox:
    def __init__(
        self, db: Database, context: ContextCompiler, deep_model: str,
        architecture: ArchitectureCompiler | None = None,
        tour_model: str = "gpt-5.6-luna",
    ):
        self.db = db
        self.context = context
        self.deep_model = deep_model
        self.architecture = architecture
        self.tour_model = tour_model
        self.seed()

    @staticmethod
    def _hash(item: CapabilityInput) -> str:
        payload = item.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def seed(self) -> None:
        for item in INITIAL_CAPABILITIES:
            capability = CapabilityInput(**item)
            content_hash = self._hash(capability)

            def already_seeded() -> bool:
                with self.db.connect() as conn:
                    return bool(conn.execute(
                        """SELECT 1 FROM capabilities
                        WHERE stable_id=? AND content_hash=? LIMIT 1""",
                        (capability.stable_id, content_hash),
                    ).fetchone())

            if already_seeded():
                continue
            try:
                self.create_capability(capability, allow_verified=True)
            except Exception:
                # Concurrent cold starts can both observe a missing built-in.
                # The primary key serializes the insert; the losing process may
                # continue only when the exact reviewed content now exists.
                if not already_seeded():
                    raise

    @staticmethod
    def _capability(row: Any) -> Capability:
        return Capability(
            stable_id=row["stable_id"], version=row["version"], name=row["name"],
            kind=row["kind"], description=row["description"],
            triggers=json.loads(row["triggers_json"]), instructions=row["instructions"],
            repositories=json.loads(row["repositories_json"]),
            required_tools=json.loads(row["required_tools_json"]),
            trust_status=row["trust_status"], provenance=row["provenance"],
            content_hash=row["content_hash"], verified_at=row["verified_at"],
            created_at=row["created_at"], activation_count=row["activation_count"],
        )

    def create_capability(
        self, item: CapabilityInput, allow_verified: bool = False,
    ) -> Capability:
        if item.trust_status == "verified" and not allow_verified:
            item = item.model_copy(update={"trust_status": "workspace"})
        now = utc_now()
        with self.db.transaction() as conn:
            version = int(conn.execute(
                "SELECT COALESCE(MAX(version),0)+1 FROM capabilities WHERE stable_id=?",
                (item.stable_id,),
            ).fetchone()[0])
            conn.execute(
                """INSERT INTO capabilities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    item.stable_id, version, item.name, item.kind, item.description,
                    json.dumps(item.triggers), item.instructions,
                    json.dumps(item.repositories), json.dumps(item.required_tools),
                    item.trust_status, item.provenance, self._hash(item), now, now,
                ),
            )
        return self.get_capability(item.stable_id, version)  # type: ignore[return-value]

    def list_capabilities(
        self, query: str = "", kind: str | None = None, repository: str | None = None,
        trusted_only: bool = True,
    ) -> list[Capability]:
        clauses = [
            """c.version=(SELECT MAX(c2.version) FROM capabilities c2
               WHERE c2.stable_id=c.stable_id)"""
        ]
        args: list[Any] = []
        if trusted_only:
            clauses.append("c.trust_status IN ('verified','workspace')")
        if kind:
            clauses.append("c.kind=?")
            args.append(kind)
        with self.db.connect() as conn:
            rows = conn.execute(
                f"""SELECT c.*,
                (SELECT COUNT(*) FROM handoff_activations a
                 JOIN handoffs h ON h.id=a.handoff_id
                 WHERE h.capability_refs_json LIKE '%' || c.stable_id || '@' ||
                       c.version || '%') activation_count
                FROM capabilities c WHERE {' AND '.join(clauses)}
                ORDER BY c.name""",
                args,
            ).fetchall()
        items = [self._capability(row) for row in rows]
        if repository:
            items = [
                item for item in items
                if "*" in item.repositories or repository.casefold() in {
                    value.casefold() for value in item.repositories
                }
            ]
        terms = set(re.findall(r"[a-z0-9]+", query.casefold()))
        if terms:
            items = [
                item for item in items
                if terms & set(re.findall(
                    r"[a-z0-9]+",
                    " ".join((item.name, item.description, *item.triggers)).casefold(),
                ))
            ]
        return items

    def get_capability(self, stable_id: str, version: int | None = None) -> Capability | None:
        with self.db.connect() as conn:
            if version is None:
                row = conn.execute(
                    """SELECT c.*,
                    (SELECT COUNT(*) FROM handoff_activations a
                     JOIN handoffs h ON h.id=a.handoff_id
                     WHERE h.capability_refs_json LIKE '%' || c.stable_id || '@' ||
                           c.version || '%') activation_count
                    FROM capabilities c WHERE stable_id=?
                    ORDER BY version DESC LIMIT 1""", (stable_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """SELECT c.*,
                    (SELECT COUNT(*) FROM handoff_activations a
                     JOIN handoffs h ON h.id=a.handoff_id
                     WHERE h.capability_refs_json LIKE '%' || c.stable_id || '@' ||
                           c.version || '%') activation_count
                    FROM capabilities c WHERE stable_id=? AND version=?""",
                    (stable_id, version),
                ).fetchone()
        return self._capability(row) if row else None

    def recommend(
        self, request: CapabilityRecommendationRequest,
    ) -> CapabilityRecommendations:
        terms = set(re.findall(
            r"[a-z0-9]+",
            " ".join((request.request, *request.screenshot_findings)).casefold(),
        ))
        ranked: list[CapabilityRecommendation] = []
        for item in self.list_capabilities(repository=request.repository):
            haystack = set(re.findall(
                r"[a-z0-9]+",
                " ".join((item.name, item.description, *item.triggers)).casefold(),
            ))
            overlap = sorted(terms & haystack)
            score = len(overlap) / max(len(terms), 1)
            if (
                item.stable_id == "taste-frontend-redesign-interview"
                and self.is_redesign_request(request.request)
            ):
                score += 1
            if item.stable_id == "evidence-bound-coding-plan":
                score += 0.03
            ranked.append(CapabilityRecommendation(
                capability=item, score=round(score, 4),
                selection_reasons=(
                    [f"matched: {', '.join(overlap[:6])}"] if overlap
                    else ["provider-neutral planning fallback"]
                ),
            ))
        ranked.sort(key=lambda item: item.score, reverse=True)
        return CapabilityRecommendations(items=ranked[:request.limit])

    @staticmethod
    def is_redesign_request(text: str) -> bool:
        terms = set(re.findall(r"[a-z0-9]+", text.casefold()))
        return "redesign" in terms or (
            bool(terms & {"frontend", "interface", "ui", "ux", "layout", "visual"})
            and bool(terms & {"change", "improve", "design", "update", "refresh"})
        )

    def redesign_suggestion(
        self, intent: str, repository: str,
    ) -> RedesignSuggestion | None:
        if not self.is_redesign_request(intent):
            return None
        recommendations = self.recommend(CapabilityRecommendationRequest(
            request=intent,
            repository=repository,
            screenshot_findings=[],
            limit=3,
        ))
        if not recommendations.items:
            return None
        primary = recommendations.items[0]
        architecture = (
            self.architecture.build(ArchitectureBriefRequest(
                repository=repository,
                mode="task",
                prompt=intent,
                token_budget=1_200,
                document_limit=6,
                section_limit=5,
            ))
            if self.architecture else None
        )
        identity = (
            architecture.repository_identity
            if architecture else {"repository": repository, "requested": repository}
        )
        snapshot = (
            architecture.snapshot_receipt if architecture else {}
        )
        evidence_ids = (
            [source.id for source in architecture.sources] if architecture else []
        )
        degraded_reasons = (
            list(architecture.degraded_reasons) if architecture else [
                "architecture_compiler_unavailable"
            ]
        )
        return RedesignSuggestion(
            repository_identity=identity,
            primary_capability={
                "stable_id": primary.capability.stable_id,
                "version": primary.capability.version,
                "content_hash": primary.capability.content_hash,
                "name": primary.capability.name,
                "trust_status": primary.capability.trust_status,
                "provenance": primary.capability.provenance,
            },
            alternatives=[{
                "stable_id": item.capability.stable_id,
                "version": item.capability.version,
                "content_hash": item.capability.content_hash,
                "name": item.capability.name,
                "selection_reasons": item.selection_reasons,
            } for item in recommendations.items[1:]],
            selection_reasons=primary.selection_reasons,
            architecture_snapshot=snapshot,
            evidence_ids=evidence_ids,
            degraded=bool(architecture.degraded if architecture else True),
            degraded_reasons=degraded_reasons,
            original_intent=intent,
        )

    def analyze_screenshot(
        self, request: ScreenshotAnalyzeRequest, api_key: str | None = None,
    ) -> ScreenshotAnalysis:
        try:
            raw = base64.b64decode(request.image_base64, validate=True)
        except ValueError as exc:
            raise ValueError("screenshot is not valid base64") from exc
        if len(raw) > 10_000_000:
            raise ValueError("screenshot exceeds the 10 MB limit")
        digest = hashlib.sha256(raw).hexdigest()
        try:
            with Image.open(io.BytesIO(raw)) as image:
                detected = Image.MIME.get(image.format, "")
                if detected != request.mime_type:
                    raise ValueError("declared screenshot MIME type does not match its bytes")
                width, height = image.size
                if width < 32 or height < 32 or width * height > 40_000_000:
                    raise ValueError("screenshot dimensions are outside the supported range")
                analyzed = image.convert("RGB")
                analyzed.thumbnail((1600, 1600))
                analyzed_width, analyzed_height = analyzed.size
        except (OSError, Image.DecompressionBombError) as exc:
            raise ValueError("screenshot is corrupt or unsupported") from exc
        findings = [
            "The screenshot appears to show a software interface; confirm which visual hierarchy should change.",
            "Spacing, typography, color, and responsive behavior are visual inferences until verified in the repository.",
            f"The requested outcome is: {request.user_request[:400]}",
        ]
        degraded = True
        if api_key:
            try:
                from openai import OpenAI

                output = io.BytesIO()
                analyzed.save(output, format="JPEG", quality=84, optimize=True)
                image_url = "data:image/jpeg;base64," + base64.b64encode(
                    output.getvalue()
                ).decode()
                response = OpenAI(api_key=api_key).responses.create(
                    model=self.deep_model,
                    input=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "Analyze this interface screenshot for a coding handoff. "
                                    "Return 3-6 concise observations about hierarchy, layout, "
                                    "components, responsive risks, and the requested change. "
                                    "Every observation must be phrased as an inference, not a "
                                    f"verified repository fact. Repository: {request.repository}. "
                                    f"User request: {request.user_request}"
                                ),
                            },
                            {"type": "input_image", "image_url": image_url},
                        ],
                    }],
                    max_output_tokens=700,
                )
                parsed = [
                    line.strip().lstrip("-•0123456789. ").strip()
                    for line in response.output_text.splitlines()
                    if line.strip()
                ]
                if parsed:
                    findings = parsed[:6]
                    degraded = False
            except Exception:
                # A handoff remains useful and visibly degraded when optional
                # multimodal analysis is temporarily unavailable.
                degraded = True
        return ScreenshotAnalysis(
            image_hash=digest, width=width, height=height,
            analyzed_width=analyzed_width, analyzed_height=analyzed_height,
            mime_type=request.mime_type, findings=findings, retained=False,
            model=self.deep_model, degraded=degraded,
        )

    def compare_screenshots(
        self,
        request: VisualComparisonAnalyzeRequest,
        api_key: str | None = None,
    ) -> VisualComparisonReceipt:
        roles = {source.role for source in request.sources}
        if not {"current", "reference"} <= roles:
            raise ValueError(
                "visual comparison requires current and reference sources"
            )
        labels = [source.label.casefold() for source in request.sources]
        if len(labels) != len(set(labels)):
            raise ValueError("visual source labels must be unique")

        analyses = [
            VisualSourceAnalysis(
                **self.analyze_screenshot(
                    ScreenshotAnalyzeRequest(
                        repository=request.repository,
                        user_request=request.user_request,
                        image_base64=source.image_base64,
                        mime_type=source.mime_type,
                        retain=False,
                    ),
                    None,
                ).model_dump(mode="json"),
                role=source.role,
                label=source.label,
            )
            for source in request.sources
        ]
        preserve = [
            "Preserve the current surface's verified information architecture, "
            "semantics, and accessibility behavior until repository evidence "
            "and the user approve a change."
        ]
        adopt = [
            "Treat the reference as a visual direction; select individual "
            "qualities only after they are visible in the comparison contract."
        ]
        avoid = [
            "Do not copy reference behavior that conflicts with repository "
            "contracts, evidence provenance, responsive rules, or reduced motion."
        ]
        conflicts = [
            "Current and reference visual grammars may imply different node, "
            "layout, color, or interaction systems."
        ]
        unresolved = [
            "Confirm which reference qualities to adopt and which current "
            "interactions must remain recognizable."
        ]
        degraded_reasons = ["visual_comparison_requires_byok"]
        model = "deterministic-visual-comparison-v1"

        if api_key:
            try:
                from openai import OpenAI

                content: list[dict[str, Any]] = [{
                    "type": "input_text",
                    "text": (
                        "Compare these role-labelled interface screenshots for "
                        "an evidence-bound coding handoff. Return one JSON object "
                        "with source_findings (role, label, findings), preserve, "
                        "adopt, avoid, conflicts, and unresolved. Each value is a "
                        "list of concise strings; use 1-6 items per comparison "
                        "group and 2-5 findings per source. Treat screenshots as "
                        "inferences, current as existing presentation, reference "
                        "as direction, and constraint as a boundary. Do not claim "
                        "repository facts. Repository: "
                        f"{request.repository}. Target surface: "
                        f"{request.target_surface}. User request: "
                        f"{request.user_request}"
                    ),
                }]
                for source in request.sources:
                    raw = base64.b64decode(source.image_base64, validate=True)
                    with Image.open(io.BytesIO(raw)) as image:
                        rendered = image.convert("RGB")
                        rendered.thumbnail((1600, 1600))
                        output = io.BytesIO()
                        rendered.save(output, format="JPEG", quality=84, optimize=True)
                    content.extend([
                        {
                            "type": "input_text",
                            "text": (
                                f"Visual source role={source.role}; "
                                f"label={source.label}."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": (
                                "data:image/jpeg;base64,"
                                + base64.b64encode(output.getvalue()).decode()
                            ),
                        },
                    ])
                response = OpenAI(api_key=api_key).responses.create(
                    model=self.deep_model,
                    input=[{"role": "user", "content": content}],
                    max_output_tokens=1_200,
                    store=False,
                )
                text = response.output_text.strip()
                if text.startswith("```"):
                    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
                parsed = json.loads(text)

                def bounded(name: str, minimum: int = 1) -> list[str]:
                    values = [
                        str(value).strip()
                        for value in parsed.get(name, [])
                        if str(value).strip()
                    ][:6]
                    if len(values) < minimum or any(
                        len(value) > MAX_OPEN_PLAN_STEP_LENGTH for value in values
                    ):
                        raise ValueError(f"invalid comparison group: {name}")
                    return values

                source_findings = {
                    (
                        str(item.get("role", "")),
                        str(item.get("label", "")).casefold(),
                    ): [
                        str(value).strip()
                        for value in item.get("findings", [])
                        if str(value).strip()
                    ][:5]
                    for item in parsed.get("source_findings", [])
                    if isinstance(item, dict)
                }
                updated = []
                for analysis in analyses:
                    findings = source_findings.get(
                        (analysis.role, analysis.label.casefold()),
                    )
                    if not findings or any(
                        len(value) > MAX_OPEN_PLAN_STEP_LENGTH
                        for value in findings
                    ):
                        raise ValueError(
                            f"missing source findings: {analysis.label}"
                        )
                    updated.append(analysis.model_copy(update={
                        "findings": findings,
                        "model": self.deep_model,
                        "degraded": False,
                    }))
                analyses = updated
                preserve = bounded("preserve")
                adopt = bounded("adopt")
                avoid = bounded("avoid")
                conflicts = bounded("conflicts")
                unresolved = bounded("unresolved")
                degraded_reasons = []
                model = self.deep_model
            except Exception as exc:
                degraded_reasons = [
                    f"visual_comparison_unavailable:{type(exc).__name__}"
                ]

        return VisualComparisonReceipt(
            target_surface=request.target_surface,
            sources=analyses,
            preserve=preserve,
            adopt=adopt,
            avoid=avoid,
            conflicts=conflicts,
            unresolved=unresolved,
            model=model,
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
            retained=False,
        )

    @staticmethod
    def _handoff(row: Any) -> Handoff:
        handoff_id = row["id"]
        raw_planning_receipt = (
            row["planning_receipt_json"]
            if "planning_receipt_json" in row.keys() else "{}"
        )
        planning_payload = json.loads(raw_planning_receipt or "{}")
        if not planning_payload:
            planning_payload = {
                "model": "deterministic-taste-plan-v1",
                "capability_reference": {},
                "architecture_snapshot": {},
                "evidence_ids": [],
                "generated_at": row["created_at"],
                "degraded": True,
                "degraded_reasons": ["planning_receipt_missing_on_legacy_handoff"],
            }
        return Handoff(
            id=handoff_id, lineage_id=row["lineage_id"], version=row["version"],
            repository=row["repository"], original_request=row["original_request"],
            screenshot=(
                ScreenshotAnalysis(**json.loads(row["screenshot_json"]))
                if row["screenshot_json"] else None
            ),
            visual_brief=(
                VisualComparisonReceipt(**json.loads(row["visual_brief_json"]))
                if (
                    "visual_brief_json" in row.keys()
                    and row["visual_brief_json"]
                    and json.loads(row["visual_brief_json"])
                )
                else None
            ),
            capability_refs=json.loads(row["capability_refs_json"]),
            open_plan=json.loads(row["open_plan_json"]),
            planning_receipt=PlanningReceipt(**planning_payload),
            architecture=json.loads(row["architecture_json"]),
            evidence_sources=json.loads(row["evidence_sources_json"]),
            safe_edit_points=json.loads(row["safe_edit_points_json"]),
            risks=json.loads(row["risks_json"]),
            tool_references=json.loads(row["tool_references_json"]),
            token_estimate=row["token_estimate"],
            omitted_candidates=row["omitted_candidates"], degraded=bool(row["degraded"]),
            status=row["status"], creator=row["creator"], created_at=row["created_at"],
            published_at=row["published_at"], revoked_at=row["revoked_at"],
            codex_command=(
                f"/plan Load Command Center handoff {handoff_id} "
                "and interview me before editing."
            ),
        )

    def _resolve_refs(self, refs: list[str]) -> list[Capability]:
        result: list[Capability] = []
        for ref in refs:
            stable_id, marker, raw_version = ref.partition("@")
            version = int(raw_version) if marker and raw_version.isdigit() else None
            item = self.get_capability(stable_id, version)
            if not item or item.trust_status not in {"verified", "workspace"}:
                raise ValueError(f"capability is unavailable or untrusted: {ref}")
            result.append(item)
        return result

    @staticmethod
    def _validate_plan(plan: list[str]) -> list[str]:
        bounded = [str(step).strip() for step in plan if str(step).strip()]
        if not 1 <= len(bounded) <= MAX_OPEN_PLAN_STEPS:
            raise ValueError(
                f"Open Plan must contain between 1 and {MAX_OPEN_PLAN_STEPS} steps"
            )
        if any(len(step) > MAX_OPEN_PLAN_STEP_LENGTH for step in bounded):
            raise ValueError(
                f"Open Plan steps cannot exceed {MAX_OPEN_PLAN_STEP_LENGTH} characters"
            )
        return bounded

    @staticmethod
    def _deterministic_taste_plan(
        screenshot: ScreenshotAnalysis | None,
        visual_brief: VisualComparisonReceipt | None = None,
    ) -> list[str]:
        screenshot_step = (
            "Review the role-labelled visual comparison receipt. Report its "
            "preserve, adopt, avoid, conflicts, and unresolved groups, then "
            "validate them against cited repository evidence."
            if visual_brief else
            "Review the labelled screenshot inferences and validate them against "
            "the cited repository evidence."
            if screenshot else
            "Pause for a screenshot upload, then label visual observations as "
            "inferences before planning."
        )
        return [
            "Report the activation ID, exact Taste capability version/hash, "
            "architecture snapshot, evidence IDs, safe edit points, risks, "
            "omissions, and degradation state.",
            screenshot_step,
            "Interview the user one focused question at a time about unresolved "
            "visual decisions, preserve boundaries, and acceptance criteria; "
            "for a comparison handoff ask no more than three questions.",
            "Propose DESIGN_VARIANCE, MOTION_INTENSITY, and VISUAL_DENSITY values "
            "as explicit design dials for user confirmation.",
            "Inventory preserve, improve, retire, and unresolved items without "
            "changing routes, API contracts, memory boundaries, or dependencies.",
            "Present an evidence-cited implementation plan covering 375, 768, "
            "1024, and 1440 pixel layouts, states, keyboard access, 44-pixel "
            "targets, and reduced motion.",
            "Do not edit repository files until the user confirms the design "
            "direction and explicitly approves the implementation plan.",
        ]

    def _generate_open_plan(
        self,
        request: HandoffDraftRequest,
        capability: Capability,
        architecture: dict[str, Any],
        evidence_ids: list[str],
        safe_edit_points: list[str],
        risks: list[str],
        api_key: str | None,
    ) -> tuple[list[str], PlanningReceipt]:
        degraded_reasons: list[str] = []
        model = self.deep_model
        plan: list[str] | None = None
        if api_key:
            try:
                from openai import OpenAI

                screenshot = request.screenshot
                visual_brief = request.visual_brief
                bounded_input = {
                    "original_intent": request.original_request,
                    "screenshot": ({
                        "image_hash": screenshot.image_hash,
                        "width": screenshot.width,
                        "height": screenshot.height,
                        "findings": screenshot.findings,
                        "findings_are_inferences": True,
                        "retained": False,
                    } if screenshot else None),
                    "visual_comparison": (
                        visual_brief.model_dump(mode="json")
                        if visual_brief else None
                    ),
                    "capability": {
                        "stable_id": capability.stable_id,
                        "version": capability.version,
                        "content_hash": capability.content_hash,
                        "instructions": capability.instructions,
                    },
                    "architecture": architecture,
                    "evidence_ids": evidence_ids,
                    "safe_edit_points": safe_edit_points,
                    "risks": risks,
                }
                response = OpenAI(api_key=api_key).responses.create(
                    model=model,
                    instructions=(
                        "You are Sol preparing a bounded Open Plan. Return only "
                        "2-12 concise plan steps, one per line. The first step must "
                        "report receipts; interview before edits; do not invent "
                        "evidence or capability references."
                    ),
                    input=json.dumps(bounded_input, separators=(",", ":")),
                    max_output_tokens=1_000,
                    store=False,
                )
                parsed = [
                    line.strip().lstrip("-•0123456789.) ").strip()
                    for line in response.output_text.splitlines()
                    if line.strip()
                ]
                plan = self._validate_plan(parsed)
            except Exception as exc:
                degraded_reasons.append(
                    f"sol_planning_unavailable:{type(exc).__name__}"
                )
        else:
            degraded_reasons.append("sol_planning_requires_byok")
        if plan is None:
            model = "deterministic-taste-plan-v1"
            plan = self._deterministic_taste_plan(
                request.screenshot, request.visual_brief,
            )
        if request.screenshot and request.screenshot.degraded:
            degraded_reasons.append("screenshot_analysis_degraded")
        if request.visual_brief and request.visual_brief.degraded:
            degraded_reasons.extend(request.visual_brief.degraded_reasons)
        if architecture.get("degraded"):
            degraded_reasons.extend(
                f"architecture:{reason}"
                for reason in architecture.get("degraded_reasons", [])
            )
            if not architecture.get("degraded_reasons"):
                degraded_reasons.append("architecture:degraded")
        degraded_reasons = list(dict.fromkeys(degraded_reasons))
        receipt = PlanningReceipt(
            model=model,
            capability_reference={
                "stable_id": capability.stable_id,
                "version": capability.version,
                "content_hash": capability.content_hash,
                "provenance": capability.provenance,
            },
            architecture_snapshot=(
                architecture.get("snapshot_receipt", {})
                if isinstance(architecture, dict) else {}
            ),
            evidence_ids=evidence_ids,
            generated_at=utc_now(),
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
        )
        return plan, receipt

    def create_handoff(
        self, request: HandoffDraftRequest, creator: str,
        api_key: str | None = None,
    ) -> Handoff:
        recommendations = self.recommend(CapabilityRecommendationRequest(
            request=request.original_request, repository=request.repository,
            screenshot_findings=(
                [
                    finding
                    for source in request.visual_brief.sources
                    for finding in source.findings
                ]
                if request.visual_brief else
                request.screenshot.findings if request.screenshot else []
            ),
        ))
        refs = request.capability_refs or [
            f"{recommendations.items[0].capability.stable_id}@"
            f"{recommendations.items[0].capability.version}"
        ]
        capabilities = self._resolve_refs(refs)
        exact_refs = [f"{item.stable_id}@{item.version}" for item in capabilities]
        pack = self.context.build(__import__(
            "aria_memory.models", fromlist=["ContextPackRequest"]
        ).ContextPackRequest(
            prompt=request.original_request, repository=request.repository,
            token_budget=request.token_budget,
        ))
        architecture_brief = (
            self.architecture.build(ArchitectureBriefRequest(
                repository=request.repository,
                mode="task",
                prompt=request.original_request,
                token_budget=min(1_600, max(512, request.token_budget // 2)),
            ))
            if self.architecture else None
        )
        lineage_id, handoff_id, now = uid("handoff"), uid("hoff"), utc_now()
        tools = list(dict.fromkeys([
            *AVAILABLE_MCP_TOOLS,
            *(tool for item in capabilities for tool in item.required_tools),
        ]))
        architecture = (
            architecture_brief.model_dump(mode="json")
            if architecture_brief else {
                "repository_identity": pack.repository_identity,
                "declared_capabilities": pack.declared_capabilities,
                "dependency_paths": pack.dependency_paths,
            }
        )
        evidence = (
            [
                source.model_dump(mode="json")
                for source in architecture_brief.sources
            ]
            if architecture_brief else []
        )
        evidence.extend(
            source.model_dump(mode="json")
            for source in pack.sources if source.entity_type == "memory"
        )
        safe_edit_points = list(
            architecture_brief.safe_edit_points
            if architecture_brief and architecture_brief.safe_edit_points
            else pack.safe_edit_points
        )
        risks = list(
            architecture_brief.risk_areas
            if architecture_brief and architecture_brief.risk_areas
            else pack.risk_areas
        )
        if request.open_plan:
            plan = self._validate_plan(request.open_plan)
            planning_receipt = PlanningReceipt(
                model="user-authored-open-plan",
                capability_reference={
                    "stable_id": capabilities[0].stable_id,
                    "version": capabilities[0].version,
                    "content_hash": capabilities[0].content_hash,
                    "provenance": capabilities[0].provenance,
                },
                architecture_snapshot=architecture.get("snapshot_receipt", {}),
                evidence_ids=[
                    str(item.get("id")) for item in evidence if item.get("id")
                ],
                generated_at=now,
                degraded=False,
                degraded_reasons=[],
            )
        else:
            plan, planning_receipt = self._generate_open_plan(
                request,
                capabilities[0],
                architecture,
                [str(item.get("id")) for item in evidence if item.get("id")],
                safe_edit_points,
                risks,
                api_key,
            )

        def packet_tokens() -> int:
            return estimate_tokens(json.dumps({
                "capabilities": [item.instructions for item in capabilities],
                "plan": plan, "architecture": architecture, "evidence": evidence,
                "visual_comparison": (
                    request.visual_brief.model_dump(mode="json")
                    if request.visual_brief else None
                ),
                "safe_edit_points": safe_edit_points, "risks": risks,
            }, separators=(",", ":")))

        removed = 0
        token_estimate = packet_tokens()
        while token_estimate > request.token_budget and evidence:
            evidence.pop()
            removed += 1
            token_estimate = packet_tokens()
        while token_estimate > request.token_budget and len(safe_edit_points) > 1:
            safe_edit_points.pop()
            token_estimate = packet_tokens()
        while token_estimate > request.token_budget and len(risks) > 1:
            risks.pop()
            token_estimate = packet_tokens()
        if token_estimate > request.token_budget:
            raise ValueError(
                "token budget is too small for the selected capability and Open Plan"
            )
        with self.db.transaction() as conn:
            conn.execute(
                """INSERT INTO handoffs(
                id,lineage_id,version,repository,original_request,screenshot_json,
                visual_brief_json,capability_refs_json,open_plan_json,architecture_json,
                evidence_sources_json,safe_edit_points_json,risks_json,
                tool_references_json,token_estimate,omitted_candidates,degraded,
                status,creator,created_at,published_at,revoked_at,
                planning_receipt_json)
                VALUES(?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,NULL,NULL,?)""",
                (
                    handoff_id, lineage_id, request.repository, request.original_request,
                    request.screenshot.model_dump_json() if request.screenshot else None,
                    (
                        request.visual_brief.model_dump_json()
                        if request.visual_brief else "{}"
                    ),
                    json.dumps(exact_refs), json.dumps(plan), json.dumps(architecture),
                    json.dumps(evidence), json.dumps(safe_edit_points),
                    json.dumps(risks), json.dumps(tools), token_estimate,
                    pack.omitted_candidate_count
                    + (architecture_brief.omitted_candidate_count if architecture_brief else 0)
                    + removed,
                    int(
                        pack.degraded
                        or (architecture_brief.degraded if architecture_brief else False)
                        or planning_receipt.degraded
                        or (
                            request.visual_brief.degraded
                            if request.visual_brief else False
                        )
                        or removed > 0
                    ),
                    creator, now, planning_receipt.model_dump_json(),
                ),
            )
        return self.get_handoff(handoff_id)  # type: ignore[return-value]

    def get_handoff(self, handoff_id: str) -> Handoff | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM handoffs WHERE id=?", (handoff_id,)).fetchone()
        return self._handoff(row) if row else None

    def list_handoffs(self) -> list[Handoff]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM handoffs ORDER BY created_at DESC").fetchall()
        return [self._handoff(row) for row in rows]

    def update_handoff(self, handoff_id: str, patch: HandoffUpdateRequest) -> Handoff:
        current = self.get_handoff(handoff_id)
        if not current:
            raise KeyError("handoff not found")
        if current.status != "draft":
            raise ValueError("published handoffs are immutable; create a new version")
        original_request = patch.original_request or current.original_request
        capability_refs = patch.capability_refs or current.capability_refs
        capabilities = self._resolve_refs(capability_refs)
        capability_refs = [
            f"{item.stable_id}@{item.version}" for item in capabilities
        ]
        open_plan = (
            self._validate_plan(patch.open_plan)
            if patch.open_plan is not None else current.open_plan
        )
        token_estimate = estimate_tokens(json.dumps({
            "capabilities": [item.instructions for item in capabilities],
            "plan": open_plan, "architecture": current.architecture,
            "evidence": current.evidence_sources,
            "safe_edit_points": current.safe_edit_points, "risks": current.risks,
        }, separators=(",", ":")))
        with self.db.transaction() as conn:
            conn.execute(
                """UPDATE handoffs SET original_request=?,capability_refs_json=?,
                open_plan_json=?,tool_references_json=?,token_estimate=?
                WHERE id=?""",
                (
                    original_request, json.dumps(capability_refs), json.dumps(open_plan),
                    json.dumps(list(dict.fromkeys([
                        *AVAILABLE_MCP_TOOLS,
                        *(tool for item in capabilities for tool in item.required_tools),
                    ]))),
                    token_estimate, handoff_id,
                ),
            )
        return self.get_handoff(handoff_id)  # type: ignore[return-value]

    def publish_handoff(self, handoff_id: str) -> Handoff:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT status FROM handoffs WHERE id=?", (handoff_id,)).fetchone()
            if not row:
                raise KeyError("handoff not found")
            if row["status"] == "revoked":
                raise ValueError("revoked handoffs cannot be published")
            if row["status"] == "draft":
                conn.execute(
                    "UPDATE handoffs SET status='published',published_at=? WHERE id=?",
                    (utc_now(), handoff_id),
                )
        return self.get_handoff(handoff_id)  # type: ignore[return-value]

    def new_handoff_version(
        self, handoff_id: str, patch: HandoffUpdateRequest, creator: str,
    ) -> Handoff:
        current = self.get_handoff(handoff_id)
        if not current:
            raise KeyError("handoff not found")
        if current.status == "draft":
            return self.update_handoff(handoff_id, patch)
        request = HandoffDraftRequest(
            repository=current.repository,
            original_request=patch.original_request or current.original_request,
            screenshot=current.screenshot,
            visual_brief=current.visual_brief,
            capability_refs=patch.capability_refs or current.capability_refs,
            open_plan=patch.open_plan or current.open_plan,
        )
        result = self.create_handoff(request, creator)
        with self.db.transaction() as conn:
            version = int(conn.execute(
                "SELECT MAX(version)+1 FROM handoffs WHERE lineage_id=?",
                (current.lineage_id,),
            ).fetchone()[0])
            conn.execute(
                "UPDATE handoffs SET lineage_id=?,version=? WHERE id=?",
                (current.lineage_id, version, result.id),
            )
        return self.get_handoff(result.id)  # type: ignore[return-value]

    @staticmethod
    def _overview_tour_steps() -> list[TourStep]:
        return [
            TourStep(
                id="overview-aria", surface="aria", target="heading",
                narration=(
                    "Aria answers from bounded evidence and shows what was injected."
                ),
                action="Open Aria.",
            ),
            TourStep(
                id="overview-recall", surface="recall", target="results",
                narration=(
                    "Recall exposes lexical, structural, and dense retrieval signals."
                ),
                action="Inspect ranked retrieval.",
            ),
            TourStep(
                id="overview-graph", surface="graph", target="content",
                narration=(
                    "The graph separates declared structure, active context, and "
                    "human-confirmed durable memory."
                ),
                action="Inspect the evidence graph.",
            ),
            TourStep(
                id="overview-audit", surface="audit", target="content",
                narration=(
                    "Models may draft proposals, but only a human action confirms "
                    "durable memory."
                ),
                action="Inspect the approval boundary.",
            ),
        ]

    def _redesign_tour_steps(self, handoff: Handoff | None) -> list[TourStep]:
        evidence_ids = [
            str(item.get("id")) for item in (handoff.evidence_sources if handoff else [])
            if item.get("id")
        ]
        capability = handoff.capability_refs[0] if handoff and handoff.capability_refs else (
            "taste-frontend-redesign-interview"
        )
        snapshot = (
            handoff.planning_receipt.architecture_snapshot.get("snapshot_id")
            if handoff else None
        )
        return [
            TourStep(
                id="redesign-problem", surface="handoff", target="heading",
                evidence_ids=evidence_ids[:3],
                narration=(
                    "Start with the real redesign intent and keep the work bounded "
                    "to the selected product surfaces."
                ),
                action="Review repository and desired change.",
            ),
            TourStep(
                id="redesign-screenshot-boundary", surface="handoff",
                target="screenshot", evidence_ids=[],
                narration=(
                    "Raw visual sources are analyzed only at the comparison "
                    "boundary. Their roles, hashes, dimensions, labelled findings, "
                    "and merge groups continue; the images are not retained."
                ),
                action="Upload or inspect current and reference receipts.",
                pause_reason=(
                    None
                    if handoff and (handoff.visual_brief or handoff.screenshot)
                    else (
                        "Current and reference screenshots must be uploaded "
                        "before this boundary can be inspected."
                    )
                ),
            ),
            TourStep(
                id="redesign-taste", surface="handoff", target="recommendation",
                evidence_ids=evidence_ids[:3],
                narration=(
                    f"Taste is the primary trusted workflow ({capability}); "
                    "alternatives and selection reasons remain visible."
                ),
                action="Inspect the recommendation and alternatives.",
                pause_reason=(
                    "Continue after the user reviews or selects a trusted visible workflow."
                ),
            ),
            TourStep(
                id="redesign-receipts", surface="handoff", target="receipts",
                evidence_ids=evidence_ids,
                narration=(
                    f"The handoff pins architecture snapshot {snapshot or 'unavailable'} "
                    "and exposes every bounded evidence receipt."
                ),
                action="Inspect architecture, evidence, safe points, and risks.",
            ),
            TourStep(
                id="redesign-open-plan", surface="handoff", target="open-plan",
                evidence_ids=evidence_ids[:5],
                narration=(
                    "The Open Plan is reversible and editable. Codex must interview "
                    "before editing and wait for explicit plan approval."
                ),
                action="Review or revise the visible plan.",
                pause_reason=(
                    "Codex interviews one question at a time; implementation waits "
                    "for design-direction and plan approval."
                ),
            ),
            TourStep(
                id="redesign-publication", surface="handoff", target="publication",
                narration=(
                    "Publication is explicit and immutable. Voice requires the exact "
                    "phrase, then the builder reveals the exact Codex command."
                ),
                action="Publish the draft when ready.",
                pause_reason=(
                    "Publication requires the user's explicit action."
                    if not handoff or handoff.status == "draft" else None
                ),
            ),
            TourStep(
                id="redesign-activation", surface="graph", target="content",
                evidence_ids=evidence_ids,
                narration=(
                    "After Codex visibly calls load_handoff, its activation receipt "
                    "appears as an edge in the evidence graph."
                ),
                action="Inspect the Codex activation edge.",
                pause_reason="Codex activation must occur in a separate Codex session.",
            ),
        ]

    def tour_script(
        self, request: TourScriptRequest, api_key: str | None = None,
    ) -> TourScript:
        handoff = self.get_handoff(request.handoff_id) if request.handoff_id else None
        if request.handoff_id and not handoff:
            raise KeyError("handoff not found")
        fallback = (
            self._redesign_tour_steps(handoff)
            if request.mode == "redesign" else self._overview_tour_steps()
        )
        steps = fallback
        model = "deterministic-evidence-tour-v1"
        degraded_reasons: list[str] = []
        if api_key:
            try:
                from openai import OpenAI

                bounded = {
                    "mode": request.mode,
                    "repository": request.repository,
                    "handoff": ({
                        "id": handoff.id,
                        "status": handoff.status,
                        "original_request": handoff.original_request,
                        "screenshot": (
                            handoff.screenshot.model_dump(mode="json")
                            if handoff.screenshot else None
                        ),
                        "visual_comparison": (
                            handoff.visual_brief.model_dump(mode="json")
                            if handoff.visual_brief else None
                        ),
                        "capability_refs": handoff.capability_refs,
                        "open_plan": handoff.open_plan,
                        "planning_receipt": handoff.planning_receipt.model_dump(
                            mode="json"
                        ),
                        "evidence_ids": [
                            item.get("id") for item in handoff.evidence_sources
                        ],
                        "safe_edit_points": handoff.safe_edit_points,
                        "risks": handoff.risks,
                    } if handoff else None),
                    "fallback_steps": [
                        step.model_dump(mode="json") for step in fallback
                    ],
                }
                response = OpenAI(api_key=api_key).responses.create(
                    model=self.tour_model,
                    instructions=(
                        "You are Luna. Return only a JSON array of 1-12 tour step "
                        "objects using the supplied stable IDs, surfaces, targets, "
                        "and evidence IDs. Narration must stay evidence-bound. Never "
                        "include or request raw screenshot bytes."
                    ),
                    input=json.dumps(bounded, separators=(",", ":")),
                    max_output_tokens=1_600,
                    store=False,
                )
                parsed = json.loads(response.output_text)
                candidate = [TourStep(**item) for item in parsed]
                allowed_ids = {step.id for step in fallback}
                allowed_evidence = {
                    evidence_id for step in fallback
                    for evidence_id in step.evidence_ids
                }
                if (
                    not candidate
                    or any(step.id not in allowed_ids for step in candidate)
                    or any(
                        evidence_id not in allowed_evidence
                        for step in candidate for evidence_id in step.evidence_ids
                    )
                ):
                    raise ValueError("tour script escaped bounded receipts")
                steps = candidate
                model = self.tour_model
            except Exception as exc:
                degraded_reasons.append(
                    f"luna_tour_unavailable:{type(exc).__name__}"
                )
        else:
            degraded_reasons.append("luna_tour_requires_byok")
        return TourScript(
            mode=request.mode,
            model=model,
            handoff_id=handoff.id if handoff else None,
            steps=steps,
            generated_at=utc_now(),
            degraded=bool(degraded_reasons),
            degraded_reasons=degraded_reasons,
        )

    def revoke_handoff(self, handoff_id: str) -> Handoff:
        with self.db.transaction() as conn:
            row = conn.execute("SELECT status FROM handoffs WHERE id=?", (handoff_id,)).fetchone()
            if not row:
                raise KeyError("handoff not found")
            conn.execute(
                "UPDATE handoffs SET status='revoked',revoked_at=? WHERE id=?",
                (utc_now(), handoff_id),
            )
        return self.get_handoff(handoff_id)  # type: ignore[return-value]

    def load_handoff(self, request: HandoffLoadRequest) -> HandoffPacket:
        handoff = self.get_handoff(request.handoff_id)
        if not handoff or handoff.status != "published":
            raise KeyError("published handoff not found")
        repository_matches = (
            handoff.repository.casefold() == request.repository.casefold()
        )
        if not repository_matches and self.architecture:
            registered = self.architecture.store.resolve_repository(request.repository)
            repository_matches = bool(
                registered
                and registered.name.casefold() == handoff.repository.casefold()
            )
        if not repository_matches:
            raise PermissionError("handoff repository does not match the active repository")
        capabilities = self._resolve_refs(handoff.capability_refs)
        activation_id, now = uid("activate"), utc_now()
        evidence_ids = [str(item.get("id")) for item in handoff.evidence_sources]
        with self.db.transaction() as conn:
            conn.execute(
                "INSERT INTO handoff_activations VALUES(?,?,?,?,?,?,?)",
                (
                    activation_id, handoff.id, handoff.repository, request.client_name,
                    request.session_id, json.dumps(evidence_ids), now,
                ),
            )
        degraded_reasons = []
        if handoff.degraded:
            degraded_reasons.append(
                "Optional dense retrieval or model analysis was unavailable; declared and lexical evidence remains."
            )
        degraded_reasons.extend(handoff.planning_receipt.degraded_reasons)
        if handoff.omitted_candidates:
            degraded_reasons.append(
                f"{handoff.omitted_candidates} lower-ranked candidates were omitted to bound the packet."
            )
        observations = [
            {"text": finding, "classification": "inference", "source": "screenshot"}
            for finding in (handoff.screenshot.findings if handoff.screenshot else [])
        ]
        if handoff.visual_brief:
            observations.extend(
                {
                    "text": finding,
                    "classification": "inference",
                    "source": f"visual:{source.role}:{source.label}",
                    "role": source.role,
                    "image_hash": source.image_hash,
                }
                for source in handoff.visual_brief.sources
                for finding in source.findings
            )
        return HandoffPacket(
            handoff_id=handoff.id,
            repository_identity=handoff.architecture.get("repository_identity", {}),
            workflow_instructions=[{
                "capability_id": item.stable_id, "version": item.version,
                "content_hash": item.content_hash, "instructions": item.instructions,
                "provenance": item.provenance,
            } for item in capabilities],
            approved_open_plan=handoff.open_plan,
            planning_receipt=handoff.planning_receipt,
            screenshot_observations=observations,
            visual_comparison=handoff.visual_brief,
            declared_architecture=handoff.architecture,
            memories_and_documents=handoff.evidence_sources,
            safe_edit_points=handoff.safe_edit_points, risks=handoff.risks,
            available_tools=handoff.tool_references,
            evidence_receipts=[{
                "evidence_id": item.get("id"),
                "selection_reasons": item.get("selection_reasons", []),
            } for item in handoff.evidence_sources],
            token_estimate=handoff.token_estimate,
            degraded=handoff.degraded or bool(handoff.omitted_candidates),
            degraded_reasons=degraded_reasons, activation_id=activation_id,
        )
