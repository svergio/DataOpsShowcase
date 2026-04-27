import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";

type ManifestNode = {
  unique_id?: string;
  name?: string;
  resource_type?: string;
  schema?: string;
  package_name?: string;
  description?: string;
  tags?: string[];
  depends_on?: { nodes?: string[] };
  columns?: Record<string, { name?: string; description?: string; data_type?: string }>;
  raw_code?: string;
  compiled_code?: string;
};

export function DocsPage() {
  const [manifest, setManifest] = useState<{ nodes?: Record<string, ManifestNode>; sources?: Record<string, ManifestNode> } | null>(null);
  const [filter, setFilter] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    apiClient
      .getDocsManifest()
      .then((data) => !cancelled && setManifest(data as never))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const all = useMemo(() => {
    if (!manifest) return [] as ManifestNode[];
    const nodes = Object.values(manifest.nodes ?? {});
    const sources = Object.values(manifest.sources ?? {});
    return [...nodes, ...sources];
  }, [manifest]);

  const filtered = useMemo(() => {
    return all.filter((n) => {
      if (resourceType && n.resource_type !== resourceType) return false;
      if (filter && !(n.name ?? "").toLowerCase().includes(filter.toLowerCase())) return false;
      return true;
    });
  }, [all, filter, resourceType]);

  const selectedNode = useMemo(() => {
    if (!selected) return null;
    return all.find((n) => n.unique_id === selected) ?? null;
  }, [all, selected]);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12, height: "100%" }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Docs Viewer</h2>
        <input placeholder="search" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <input placeholder="resource_type" value={resourceType} onChange={(e) => setResourceType(e.target.value)} />
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>{filtered.length} items</span>
      </header>

      {loading && <div>Loading docs manifest...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 16, minHeight: 540 }}>
        <div style={{ border: "1px solid #e5e7eb", overflow: "auto", maxHeight: 640 }}>
          {filtered.map((n) => (
            <div
              key={n.unique_id}
              onClick={() => setSelected(n.unique_id ?? null)}
              style={{
                padding: 8,
                cursor: "pointer",
                background: selected === n.unique_id ? "#dbeafe" : "transparent",
                borderBottom: "1px solid #f3f4f6",
                fontSize: 13,
              }}
            >
              <div style={{ fontFamily: "monospace", fontSize: 11, color: "#666" }}>{n.resource_type}</div>
              <div>{n.name}</div>
            </div>
          ))}
        </div>
        <div style={{ border: "1px solid #e5e7eb", padding: 16, overflow: "auto", maxHeight: 640 }}>
          {!selectedNode && <div style={{ color: "#666" }}>Select an item from the list.</div>}
          {selectedNode && (
            <div>
              <h3 style={{ marginTop: 0 }}>{selectedNode.name}</h3>
              <div style={{ fontSize: 12, color: "#666" }}>
                {selectedNode.resource_type} / {selectedNode.schema} / {selectedNode.package_name}
              </div>
              <p>{selectedNode.description ?? "No description."}</p>
              {selectedNode.tags?.length ? <div>tags: {selectedNode.tags.join(", ")}</div> : null}
              {selectedNode.columns && (
                <div>
                  <h4>Columns</h4>
                  <table style={{ borderCollapse: "collapse", width: "100%" }}>
                    <thead>
                      <tr style={{ background: "#f3f4f6" }}>
                        <th style={th}>Name</th>
                        <th style={th}>Type</th>
                        <th style={th}>Description</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.values(selectedNode.columns).map((col, idx) => (
                        <tr key={idx}>
                          <td style={tdMono}>{col.name ?? "—"}</td>
                          <td style={td}>{col.data_type ?? "—"}</td>
                          <td style={td}>{col.description ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {selectedNode.raw_code && (
                <details>
                  <summary>raw_code</summary>
                  <pre style={{ background: "#f3f4f6", padding: 12, fontSize: 11, overflow: "auto" }}>
                    {selectedNode.raw_code}
                  </pre>
                </details>
              )}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

const th: React.CSSProperties = { padding: 6, textAlign: "left", borderBottom: "1px solid #d1d5db" };
const td: React.CSSProperties = { padding: 4, borderBottom: "1px solid #e5e7eb", fontSize: 12 };
const tdMono: React.CSSProperties = { ...td, fontFamily: "monospace" };
