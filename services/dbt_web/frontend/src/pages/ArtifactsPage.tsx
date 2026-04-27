import { useState } from "react";
import { apiClient } from "../api/client";
import type { ArtifactEnvelope, ArtifactName } from "../api/contracts";

const NAMES: ArtifactName[] = ["manifest.json", "catalog.json", "run_results.json", "graph.js"];

export function ArtifactsPage() {
  const [runId, setRunId] = useState("");
  const [name, setName] = useState<ArtifactName>("manifest.json");
  const [envelope, setEnvelope] = useState<ArtifactEnvelope | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    if (!runId) {
      setError("run_id required");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await apiClient.getArtifact(runId, name);
      setEnvelope(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Artifacts</h2>
        <input placeholder="run_id" value={runId} onChange={(e) => setRunId(e.target.value)} />
        <select value={name} onChange={(e) => setName(e.target.value as ArtifactName)}>
          {NAMES.map((n) => (
            <option key={n} value={n}>{n}</option>
          ))}
        </select>
        <button onClick={load} disabled={loading}>Fetch</button>
        {envelope?.cached && <span style={{ fontSize: 12, color: "#2563eb" }}>cached</span>}
      </header>

      {loading && <div>Loading artifact...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      {envelope && (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          <div style={{ fontSize: 12, color: "#666" }}>
            run_id={envelope.run_id} size={envelope.size ?? "?"} content_type={envelope.content_type ?? "?"}
          </div>
          <pre
            style={{
              background: "#f3f4f6",
              padding: 12,
              fontSize: 11,
              overflow: "auto",
              maxHeight: 600,
            }}
          >
            {typeof envelope.content === "string"
              ? envelope.content
              : JSON.stringify(envelope.content ?? {}, null, 2)}
          </pre>
        </div>
      )}
    </section>
  );
}
