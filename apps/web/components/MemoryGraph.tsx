"use client";

import {useEffect, useMemo, useRef, useState} from "react";
import dagre from "@dagrejs/dagre";
import {
  Background, Controls, Edge, Handle, Node, NodeProps, Position, ReactFlow,
  ReactFlowInstance,
} from "@xyflow/react";
import {Database, FileText, FolderGit2, ShieldCheck, Sparkles} from "lucide-react";
import type {GraphData} from "@/lib/types";
import {ContextPulseEdge, evidenceEdgeTone} from "./ContextPulseEdge";

type EvidenceStage = "declared" | "dense" | "durable" | "repository";
type MemoryNodeData = {
  label: string;
  project: string;
  status: string;
  kind: string;
  active: boolean;
  stage: EvidenceStage;
  evidenceId?: string;
};
type MemoryNode = Node<MemoryNodeData, "memory">;

export function evidenceNodeTone(stage: EvidenceStage, active: boolean) {
  if (active || stage === "dense") return "context";
  if (stage === "declared" || stage === "repository") return "declared";
  return "durable";
}

function evidenceStageLabel(stage: EvidenceStage, active: boolean) {
  if (active) return "Injected context";
  if (stage === "repository") return "Repository";
  if (stage === "declared") return "Declared document";
  if (stage === "dense") return "Dense candidate";
  return "Durable memory";
}

function MemoryNodeView({data}: NodeProps<MemoryNode>) {
  const tone = evidenceNodeTone(data.stage, data.active);
  const Icon = data.stage === "repository"
    ? FolderGit2
    : data.stage === "declared"
      ? FileText
      : data.kind === "decision"
        ? ShieldCheck
        : data.stage === "dense"
          ? Sparkles
          : Database;
  const stageLabel = evidenceStageLabel(data.stage, data.active);
  return (
    <article
      className={`graph-node evidence-node ${tone} ${data.kind} ${data.stage} ${data.status} ${data.active ? "active" : ""}`}
      aria-label={`${stageLabel}: ${data.label}`}
    >
      <Handle type="target" position={Position.Left} />
      <header>
        <span className="node-icon"><Icon /></span>
        <span className="node-heading">
          <strong>{data.label}</strong>
          <small>{data.kind}</small>
        </span>
        <i className="node-status" title={data.active ? "Included in active context" : data.status} />
      </header>
      <footer>
        <span>{stageLabel}</span>
        <small>{data.project}</small>
      </footer>
      <Handle type="source" position={Position.Right} />
    </article>
  );
}

const nodeTypes = {memory: MemoryNodeView};
const edgeTypes = {contextPulse: ContextPulseEdge};

function activeSubgraph(data: GraphData, activeIds: string[], compact: boolean): GraphData {
  if (!compact || !activeIds.length) return data;
  const active = new Set(activeIds);
  const keep = new Set(activeIds);
  data.edges.forEach((edge) => {
    if (active.has(edge.source) || active.has(edge.target)) {
      keep.add(edge.source);
      keep.add(edge.target);
    }
  });
  return {
    nodes: data.nodes.filter((node) => keep.has(node.id)),
    edges: data.edges.filter((edge) => keep.has(edge.source) && keep.has(edge.target)),
  };
}

function layout(data: GraphData, activeIds: string[], compact: boolean) {
  const visible = activeSubgraph(data, activeIds, compact);
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({rankdir: "LR", ranksep: 110, nodesep: 34});
  visible.nodes.forEach((node) => graph.setNode(node.id, {width: 214, height: 96}));
  visible.edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  const active = new Set(activeIds);
  const nodeById = new Map(visible.nodes.map((node) => [node.id, node]));
  const nodes: MemoryNode[] = visible.nodes.map((node) => {
    const point = graph.node(node.id);
    return {
      id: node.id,
      type: "memory",
      position: {x: point.x - 107, y: point.y - 48},
      ariaLabel: `${evidenceStageLabel(node.stage, active.has(node.id))}: ${node.label}, ${node.project}`,
      data: {
        label: node.label, project: node.project, status: node.status,
        kind: node.type, stage: node.stage, active: active.has(node.id),
        evidenceId: node.evidence_id,
      },
    };
  });
  const edges: Edge[] = visible.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    type: "contextPulse",
    ariaLabel: `${edge.type} from ${nodeById.get(edge.source)?.label ?? edge.source} to ${nodeById.get(edge.target)?.label ?? edge.target}`,
    data: {
      relation: edge.type,
      tone: evidenceEdgeTone({
        active: active.has(edge.source) || active.has(edge.target),
        targetStage: nodeById.get(edge.target)?.stage,
      }),
    },
  }));
  return {nodes, edges};
}

export function MemoryGraph({
  data, activeIds, onEvidence,
}: {
  data: GraphData;
  activeIds: string[];
  onEvidence: (id: string) => void;
}) {
  const [compact, setCompact] = useState(false);
  const flowRef = useRef<ReactFlowInstance<MemoryNode, Edge> | null>(null);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 860px)");
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const elements = useMemo(() => layout(data, activeIds, compact), [data, activeIds, compact]);
  useEffect(() => {
    const graphCommand = (event: Event) => {
      const detail = (event as CustomEvent<{
        action: "focus" | "fit-active" | "fit-all"; id?: string;
      }>).detail;
      if (!detail) return;
      if (detail.action === "fit-active" || detail.action === "fit-all") {
        setCompact(detail.action === "fit-active");
        window.setTimeout(() => void flowRef.current?.fitView({padding: .22, duration: 450}), 0);
        return;
      }
      const node = elements.nodes.find((candidate) =>
        candidate.id === detail.id || candidate.data.evidenceId === detail.id,
      );
      if (node) {
        const width = node.measured?.width ?? 214;
        const height = node.measured?.height ?? 96;
        void flowRef.current?.setCenter(
          node.position.x + width / 2,
          node.position.y + height / 2,
          {zoom: 1.05, duration: 500},
        );
      }
    };
    window.addEventListener("aria:graph-command", graphCommand);
    return () => window.removeEventListener("aria:graph-command", graphCommand);
  }, [elements.nodes]);
  return (
    <div className="graph-stage" data-aria-target="content">
      <div className="graph-legend" aria-label="Graph stage legend">
        <span className="declared">Declared structure</span>
        <span className="dense">Active context</span>
        <span className="durable">Durable memory</span>
      </div>
      <ReactFlow
        onInit={(instance) => { flowRef.current = instance; }}
        nodes={elements.nodes}
        edges={elements.edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{padding: 0.22}}
        minZoom={0.25}
        maxZoom={1.6}
        onNodeClick={(_, node) => {
          const evidenceId = (node.data as MemoryNodeData).evidenceId;
          if (evidenceId) onEvidence(evidenceId);
        }}
      >
        <Background color="#333a42" gap={28} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
