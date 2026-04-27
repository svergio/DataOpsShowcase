import { useEffect, useMemo, useRef, useState } from "react";
import { apiClient } from "../api/client";
import type { LineageEdge, LineageGraphResponse, LineageNode } from "../api/contracts";

type Positioned = LineageNode & { x: number; y: number };

const LAYER_ORDER = [
  "source",
  "seed",
  "model.staging",
  "model.vault",
  "model.bdv",
  "model.marts",
  "model.serving",
  "snapshot",
  "test",
  "exposure",
];

function bucketFor(node: LineageNode): string {
  if (node.resource_type === "model") {
    if (node.schema?.includes("staging")) return "model.staging";
    if (node.schema?.includes("vault")) return "model.vault";
    if (node.schema?.includes("bdv")) return "model.bdv";
    if (node.schema?.includes("marts")) return "model.marts";
    if (node.schema?.includes("serving")) return "model.serving";
    return "model.staging";
  }
  return node.resource_type;
}

export function LineagePage() {
  const [graph, setGraph] = useState<LineageGraphResponse>({ nodes: [], edges: [], total_nodes: 0, total_edges: 0 });
  const [resourceType, setResourceType] = useState("");
  const [schema, setSchema] = useState("");
  const [tag, setTag] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient
      .getLineageGraph({
        resource_type: resourceType || undefined,
        schema: schema || undefined,
        tag: tag || undefined,
      })
      .then((data) => {
        if (!cancelled) setGraph(data);
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [resourceType, schema, tag]);

  const positioned = useMemo<Positioned[]>(() => {
    const buckets: Record<string, LineageNode[]> = {};
    graph.nodes.forEach((n) => {
      const key = bucketFor(n);
      buckets[key] = buckets[key] ?? [];
      buckets[key].push(n);
    });
    const orderedKeys = LAYER_ORDER.filter((k) => buckets[k]?.length).concat(
      Object.keys(buckets).filter((k) => !LAYER_ORDER.includes(k)),
    );
    const colW = 220;
    const rowH = 28;
    const layout: Positioned[] = [];
    orderedKeys.forEach((key, colIdx) => {
      buckets[key].forEach((n, rowIdx) => {
        layout.push({ ...n, x: colIdx * colW + 80, y: rowIdx * rowH + 40 });
      });
    });
    return layout;
  }, [graph.nodes]);

  const positionMap = useMemo(() => {
    const m = new Map<string, Positioned>();
    positioned.forEach((p) => m.set(p.id, p));
    return m;
  }, [positioned]);

  const visibleEdges = useMemo<LineageEdge[]>(() => {
    if (!selected) return graph.edges;
    return graph.edges.filter((e) => e.source === selected || e.target === selected);
  }, [graph.edges, selected]);

  const width = Math.max(800, (positioned.reduce((acc, p) => Math.max(acc, p.x), 0) || 0) + 240);
  const height = Math.max(400, (positioned.reduce((acc, p) => Math.max(acc, p.y), 0) || 0) + 80);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Lineage Graph</h2>
        <input placeholder="resource_type" value={resourceType} onChange={(e) => setResourceType(e.target.value)} />
        <input placeholder="schema" value={schema} onChange={(e) => setSchema(e.target.value)} />
        <input placeholder="tag" value={tag} onChange={(e) => setTag(e.target.value)} />
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>
          nodes={graph.total_nodes} edges={graph.total_edges}
        </span>
      </header>

      {loading && <div>Loading lineage...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      <div ref={wrapperRef} style={{ overflow: "auto", border: "1px solid #e5e7eb", maxHeight: 640 }}>
        <svg width={width} height={height} style={{ background: "#fafafa" }}>
          {visibleEdges.map((e, idx) => {
            const a = positionMap.get(e.source);
            const b = positionMap.get(e.target);
            if (!a || !b) return null;
            return (
              <line
                key={`${e.source}->${e.target}-${idx}`}
                x1={a.x + 160}
                y1={a.y + 12}
                x2={b.x}
                y2={b.y + 12}
                stroke="#9ca3af"
                strokeWidth={1}
                markerEnd="url(#arrow)"
              />
            );
          })}
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#6b7280" />
            </marker>
          </defs>
          {positioned.map((n) => {
            const isSelected = selected === n.id;
            return (
              <g
                key={n.id}
                transform={`translate(${n.x}, ${n.y})`}
                style={{ cursor: "pointer" }}
                onClick={() => setSelected(isSelected ? null : n.id)}
              >
                <rect
                  width={160}
                  height={24}
                  rx={4}
                  fill={isSelected ? "#dbeafe" : "#fff"}
                  stroke={isSelected ? "#2563eb" : "#cbd5e1"}
                />
                <text x={8} y={16} fontSize={11} fontFamily="monospace">
                  {n.name.length > 24 ? `${n.name.slice(0, 22)}...` : n.name}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {selected && (
        <pre style={{ background: "#f3f4f6", padding: 12, fontSize: 12 }}>
          {JSON.stringify(positionMap.get(selected) ?? {}, null, 2)}
        </pre>
      )}
    </section>
  );
}
