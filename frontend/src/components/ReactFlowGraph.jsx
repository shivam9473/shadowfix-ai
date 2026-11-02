import { Background, Controls, ReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const ORDER = [
  ["breaker", "Breaker"],
  ["sre", "SRE"],
  ["detective", "Detective"],
  ["coder", "Coder"],
  ["reviewer", "Reviewer"],
  ["deploy", "Approve"],
];

function tone(status) {
  if (status === "done") return "#5eead4";
  if (status === "running") return "#f4f2ff";
  if (status === "failed" || status === "halted") return "#ff4d2e";
  return "#2b2550";
}

export default function ReactFlowGraph({ events = [], status = "queued" }) {
  const byStage = Object.fromEntries(events.map((event) => [event.stage, event.status]));
  if (status === "awaiting_approval") byStage.deploy = "running";
  if (status === "deployed") byStage.deploy = "done";

  const nodes = ORDER.map(([id, label], index) => ({
    id,
    position: { x: index * 170, y: 40 },
    data: { label: `${label}\n${byStage[id] || "waiting"}` },
    style: {
      background: "#130f26",
      color: "#f4f2ff",
      border: `1px solid ${tone(byStage[id])}`,
      width: 140,
      fontSize: 12,
      fontFamily: "IBM Plex Mono, monospace",
      whiteSpace: "pre-line",
    },
  }));

  const edges = ORDER.slice(0, -1).map(([id], index) => ({
    id: `${id}-${ORDER[index + 1][0]}`,
    source: id,
    target: ORDER[index + 1][0],
    animated: byStage[id] === "done" && byStage[ORDER[index + 1][0]] !== "done",
    style: { stroke: "#9f9abd" },
  }));

  return (
    <div className="h-64 rounded-2xl border border-line bg-ink-2">
      <ReactFlow nodes={nodes} edges={edges} fitView proOptions={{ hideAttribution: true }}>
        <Background color="#2b2550" gap={18} />
        <Controls />
      </ReactFlow>
    </div>
  );
}
