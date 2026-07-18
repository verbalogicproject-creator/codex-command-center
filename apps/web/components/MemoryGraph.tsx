"use client";

import {useMemo} from "react";
import dagre from "@dagrejs/dagre";
import {
  Background, Controls, Edge, Handle, Node, NodeProps, Position, ReactFlow,
} from "@xyflow/react";
import type {GraphData} from "@/lib/types";

type MemoryNodeData = {
  label: string;
  project: string;
  status: string;
  kind: string;
  active: boolean;
  evidenceId?: string;
};
type MemoryNode = Node<MemoryNodeData, "memory">;

function MemoryNodeView({data}: NodeProps<MemoryNode>) {
  return (
    <button className={`graph-node ${data.kind} ${data.status} ${data.active ? "active" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <span className="node-type">{data.kind}</span>
      <strong>{data.label}</strong>
      <small>{data.project}</small>
      <Handle type="source" position={Position.Right} />
    </button>
  );
}

const nodeTypes = {memory: MemoryNodeView};

function layout(data: GraphData, activeIds: string[]) {
  const graph = new dagre.graphlib.Graph().setDefaultEdgeLabel(() => ({}));
  graph.setGraph({rankdir: "LR", ranksep: 95, nodesep: 28});
  data.nodes.forEach((node) => graph.setNode(node.id, {width: 190, height: 76}));
  data.edges.forEach((edge) => graph.setEdge(edge.source, edge.target));
  dagre.layout(graph);
  const nodes: MemoryNode[] = data.nodes.map((node) => {
    const point = graph.node(node.id);
    return {
      id: node.id,
      type: "memory",
      position: {x: point.x - 95, y: point.y - 38},
      data: {
        label: node.label, project: node.project, status: node.status,
        kind: node.type, active: activeIds.includes(node.id),
        evidenceId: node.evidence_id,
      },
    };
  });
  const edges: Edge[] = data.edges.map((edge) => ({
    ...edge,
    animated: activeIds.includes(edge.target),
    className: activeIds.includes(edge.target) ? "trace-edge" : "",
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
  const elements = useMemo(() => layout(data, activeIds), [data, activeIds]);
  return (
    <div className="graph-stage">
      <ReactFlow
        nodes={elements.nodes}
        edges={elements.edges}
        nodeTypes={nodeTypes}
        fitView
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
