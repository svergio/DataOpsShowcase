import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { ModelItem } from "../api/contracts";

export function ModelsPage() {
  const [items, setItems] = useState<ModelItem[]>([]);
  const [query, setQuery] = useState("");
  const [tags, setTags] = useState("");
  const [resourceType, setResourceType] = useState("");
  const [schema, setSchema] = useState("");
  const [packageName, setPackageName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const handle = setTimeout(() => {
      apiClient
        .searchModels({
          query: query || undefined,
          tags: tags || undefined,
          resource_type: resourceType || undefined,
          schema: schema || undefined,
          package_name: packageName || undefined,
        })
        .then((data) => {
          if (!cancelled) setItems(data.items);
        })
        .catch((err) => !cancelled && setError(err.message))
        .finally(() => !cancelled && setLoading(false));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [query, tags, resourceType, schema, packageName]);

  const resourceTypes = useMemo(() => {
    return Array.from(new Set(items.map((i) => i.resource_type))).sort();
  }, [items]);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Models Explorer</h2>
        <input placeholder="search by name" value={query} onChange={(e) => setQuery(e.target.value)} />
        <input placeholder="tags (csv)" value={tags} onChange={(e) => setTags(e.target.value)} />
        <input placeholder="resource_type" value={resourceType} onChange={(e) => setResourceType(e.target.value)} />
        <input placeholder="schema" value={schema} onChange={(e) => setSchema(e.target.value)} />
        <input placeholder="package_name" value={packageName} onChange={(e) => setPackageName(e.target.value)} />
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>{items.length} items</span>
      </header>

      {loading && <div>Loading...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      <div style={{ fontSize: 12, color: "#555" }}>
        Resource types: {resourceTypes.join(", ") || "—"}
      </div>

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr style={{ background: "#f3f4f6" }}>
            <th style={th}>Unique ID</th>
            <th style={th}>Name</th>
            <th style={th}>Type</th>
            <th style={th}>Schema</th>
            <th style={th}>Package</th>
            <th style={th}>Tags</th>
            <th style={th}>Depends On</th>
          </tr>
        </thead>
        <tbody>
          {items.map((m) => (
            <tr key={m.unique_id}>
              <td style={tdMono}>{m.unique_id}</td>
              <td style={td}>{m.name}</td>
              <td style={td}>{m.resource_type}</td>
              <td style={td}>{m.schema ?? "—"}</td>
              <td style={td}>{m.package_name ?? "—"}</td>
              <td style={td}>{(m.tags ?? []).join(", ") || "—"}</td>
              <td style={td}>{(m.depends_on ?? []).length}</td>
            </tr>
          ))}
          {!loading && items.length === 0 && (
            <tr>
              <td style={td} colSpan={7}>No models match the filters.</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

const th: React.CSSProperties = { padding: 8, textAlign: "left", borderBottom: "1px solid #d1d5db" };
const td: React.CSSProperties = { padding: 6, borderBottom: "1px solid #e5e7eb", fontSize: 13 };
const tdMono: React.CSSProperties = { ...td, fontFamily: "monospace", fontSize: 12 };
