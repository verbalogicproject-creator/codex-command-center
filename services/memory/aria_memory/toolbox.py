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
    ScreenshotAnalysis, ScreenshotAnalyzeRequest, utc_now,
)
from .store import uid


INITIAL_CAPABILITIES: tuple[dict[str, Any], ...] = (
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


class Toolbox:
    def __init__(
        self, db: Database, context: ContextCompiler, deep_model: str,
        openai_api_key: str | None = None,
        architecture: ArchitectureCompiler | None = None,
    ):
        self.db = db
        self.context = context
        self.deep_model = deep_model
        self.openai_api_key = openai_api_key
        self.architecture = architecture
        self.seed()

    @staticmethod
    def _hash(item: CapabilityInput) -> str:
        payload = item.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def seed(self) -> None:
        with self.db.connect() as conn:
            if conn.execute("SELECT 1 FROM capabilities LIMIT 1").fetchone():
                return
        for item in INITIAL_CAPABILITIES:
            self.create_capability(CapabilityInput(**item), allow_verified=True)

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

    def analyze_screenshot(self, request: ScreenshotAnalyzeRequest) -> ScreenshotAnalysis:
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
        if self.openai_api_key:
            try:
                from openai import OpenAI

                output = io.BytesIO()
                analyzed.save(output, format="JPEG", quality=84, optimize=True)
                image_url = "data:image/jpeg;base64," + base64.b64encode(
                    output.getvalue()
                ).decode()
                response = OpenAI(api_key=self.openai_api_key).responses.create(
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

    @staticmethod
    def _handoff(row: Any) -> Handoff:
        handoff_id = row["id"]
        return Handoff(
            id=handoff_id, lineage_id=row["lineage_id"], version=row["version"],
            repository=row["repository"], original_request=row["original_request"],
            screenshot=(
                ScreenshotAnalysis(**json.loads(row["screenshot_json"]))
                if row["screenshot_json"] else None
            ),
            capability_refs=json.loads(row["capability_refs_json"]),
            open_plan=json.loads(row["open_plan_json"]),
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

    def create_handoff(self, request: HandoffDraftRequest, creator: str) -> Handoff:
        recommendations = self.recommend(CapabilityRecommendationRequest(
            request=request.original_request, repository=request.repository,
            screenshot_findings=request.screenshot.findings if request.screenshot else [],
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
        plan = request.open_plan or [
            "Confirm the redesign goal and acceptance criteria.",
            "Inspect the cited architecture, safe edit points, and risks.",
            "Interview the user before editing repository files.",
            "Implement the smallest coherent change and verify responsive behavior.",
        ]
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

        def packet_tokens() -> int:
            return estimate_tokens(json.dumps({
                "capabilities": [item.instructions for item in capabilities],
                "plan": plan, "architecture": architecture, "evidence": evidence,
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
                """INSERT INTO handoffs VALUES(
                ?,?,1,?,?,?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,NULL,NULL)""",
                (
                    handoff_id, lineage_id, request.repository, request.original_request,
                    request.screenshot.model_dump_json() if request.screenshot else None,
                    json.dumps(exact_refs), json.dumps(plan), json.dumps(architecture),
                    json.dumps(evidence), json.dumps(safe_edit_points),
                    json.dumps(risks), json.dumps(tools), token_estimate,
                    pack.omitted_candidate_count
                    + (architecture_brief.omitted_candidate_count if architecture_brief else 0)
                    + removed,
                    int(
                        pack.degraded
                        or (architecture_brief.degraded if architecture_brief else False)
                        or removed > 0
                    ),
                    creator, now,
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
        open_plan = patch.open_plan or current.open_plan
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
        if handoff.omitted_candidates:
            degraded_reasons.append(
                f"{handoff.omitted_candidates} lower-ranked candidates were omitted to bound the packet."
            )
        observations = [
            {"text": finding, "classification": "inference", "source": "screenshot"}
            for finding in (handoff.screenshot.findings if handoff.screenshot else [])
        ]
        return HandoffPacket(
            handoff_id=handoff.id,
            repository_identity=handoff.architecture.get("repository_identity", {}),
            workflow_instructions=[{
                "capability_id": item.stable_id, "version": item.version,
                "content_hash": item.content_hash, "instructions": item.instructions,
                "provenance": item.provenance,
            } for item in capabilities],
            approved_open_plan=handoff.open_plan,
            screenshot_observations=observations,
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
