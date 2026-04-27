import { useEffect, useState } from "react";
import { apiClient } from "../api/client";
import type { TestsSummaryResponse } from "../api/contracts";

const TARGETS = ["", "staging", "vault", "marts"] as const;
const SEVERITY = ["", "error", "warn"] as const;

export function TestsPage() {
  const [data, setData] = useState<TestsSummaryResponse>({ summary: {}, failed: [], failed_total: 0 });
  const [target, setTarget] = useState("");
  const [severity, setSeverity] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient
      .getTestsSummary({ target: target || undefined, severity: severity || undefined })
      .then((d) => !cancelled && setData(d))
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [target, severity]);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap" }}>
        <h2 style={{ margin: 0 }}>Tests Dashboard</h2>
        <label>
          Target:
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {TARGETS.map((t) => (
              <option key={t} value={t}>{t || "all"}</option>
            ))}
          </select>
        </label>
        <label>
          Severity:
          <select value={severity} onChange={(e) => setSeverity(e.target.value)}>
            {SEVERITY.map((s) => (
              <option key={s} value={s}>{s || "all"}</option>
            ))}
          </select>
        </label>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>
          failed_total={data.failed_total}
        </span>
      </header>

      {loading && <div>Loading...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {Object.entries(data.summary).map(([t, v]) => (
          <div key={t} style={{ border: "1px solid #e5e7eb", padding: 12, borderRadius: 6, minWidth: 160 }}>
            <div style={{ fontWeight: 600 }}>{t}</div>
            <div style={{ fontSize: 13 }}>total: {v.total}</div>
            <div style={{ color: "green" }}>passed: {v.passed}</div>
            <div style={{ color: v.failed > 0 ? "red" : "#666" }}>failed: {v.failed}</div>
          </div>
        ))}
        {Object.keys(data.summary).length === 0 && !loading && <div>No test summary available.</div>}
      </div>

      <h3>Failed tests</h3>
      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr style={{ background: "#f3f4f6" }}>
            <th style={th}>Target</th>
            <th style={th}>Test</th>
            <th style={th}>Status</th>
            <th style={th}>Severity</th>
            <th style={th}>Exec time (s)</th>
            <th style={th}>Message</th>
          </tr>
        </thead>
        <tbody>
          {data.failed.map((f) => (
            <tr key={`${f.target}-${f.unique_id}`}>
              <td style={td}>{f.target}</td>
              <td style={tdMono}>{f.unique_id}</td>
              <td style={{ ...td, color: "red" }}>{f.status}</td>
              <td style={td}>{f.severity}</td>
              <td style={td}>{f.execution_time?.toFixed(2) ?? "—"}</td>
              <td style={td}>{f.message ?? "—"}</td>
            </tr>
          ))}
          {data.failed.length === 0 && !loading && (
            <tr>
              <td style={td} colSpan={6}>No failures.</td>
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
