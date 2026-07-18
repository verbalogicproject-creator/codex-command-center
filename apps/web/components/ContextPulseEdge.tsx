"use client";

import {BaseEdge, EdgeProps, getBezierPath} from "@xyflow/react";

export type EvidenceEdgeTone = "context" | "declared" | "durable" | "structural";

const EDGE_COLORS: Record<EvidenceEdgeTone, {stroke: string; pulse: string}> = {
  context: {stroke: "rgba(82, 214, 232, .72)", pulse: "#b9f6ff"},
  declared: {stroke: "rgba(167, 139, 250, .42)", pulse: "#a78bfa"},
  durable: {stroke: "rgba(243, 168, 59, .42)", pulse: "#f3a83b"},
  structural: {stroke: "rgba(78, 89, 99, .72)", pulse: "#8f989f"},
};

export function evidenceEdgeTone({
  active,
  targetStage,
}: {
  active: boolean;
  targetStage?: string;
}): EvidenceEdgeTone {
  if (active) return "context";
  if (targetStage === "declared" || targetStage === "repository") return "declared";
  if (targetStage === "durable") return "durable";
  return "structural";
}

export function ContextPulseEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  style,
  data,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const tone = (data?.tone as EvidenceEdgeTone | undefined) ?? "structural";
  const colors = EDGE_COLORS[tone];
  const active = tone === "context";

  return (
    <g className={`context-pulse-edge ${tone}`}>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{...style, stroke: colors.stroke, strokeWidth: active ? 2.2 : 1.35}}
      />
      {active && (
        <>
          <path className="context-pulse-edge-glow" d={edgePath} />
          <circle className="context-pulse-edge-particle" r="4" fill={colors.pulse}>
            <animateMotion dur="1.8s" repeatCount="indefinite" path={edgePath} />
          </circle>
        </>
      )}
    </g>
  );
}
