import { useEffect, useMemo, useState } from "react";
import { apiClient } from "../api/client";
import type { RunSummary } from "../api/contracts";

const TARGETS = ["", "staging", "vault", "marts"] as const;
const STATUSES = ["", "success", "failed", "unknown"] as const;

export function RunsPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [target, setTarget] = useState<string>("");
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    apiClient
      .listRuns({ target: target || undefined, status: status || undefined, limit: 100 })
      .then((data) => {
        if (!cancelled) setRuns(data.items);
      })
      .catch((err) => !cancelled && setError(err.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [target, status]);

  const totals = useMemo(() => {
    return runs.reduce(
      (acc, r) => {
        acc.total += r.results_total;
        acc.passed += r.results_passed;
        acc.failed += r.results_failed;
        return acc;
      },
      { total: 0, passed: 0, failed: 0 },
    );
  }, [runs]);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <header style={{ display: "flex", gap: 16, alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Runs History</h2>
        <label>
          Target:
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {TARGETS.map((t) => (
              <option key={t} value={t}>{t || "all"}</option>
            ))}
          </select>
        </label>
        <label>
          Status:
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {STATUSES.map((s) => (
              <option key={s} value={s}>{s || "all"}</option>
            ))}
          </select>
        </label>
        <span style={{ marginLeft: "auto", fontSize: 12, color: "#666" }}>
          total={totals.total} passed={totals.passed} failed={totals.failed}
        </span>
      </header>

      {loading && <div>Loading runs...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}

      <table style={{ borderCollapse: "collapse", width: "100%" }}>
        <thead>
          <tr style={{ background: "#f3f4f6" }}>
            <th style={th}>Target</th>
            <th style={th}>Run ID</th>
            <th style={th}>Status</th>
            <th style={th}>Generated At</th>
            <th style={th}>dbt Version</th>
            <th style={th}>Elapsed (s)</th>
            <th style={th}>Total</th>
            <th style={th}>Passed</th>
            <th style={th}>Failed</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={`${r.target}-${r.run_id ?? "n/a"}`}>
              <td style={td}>{r.target}</td>
              <td style={tdMono}>{r.run_id ?? "—"}</td>
              <td style={{ ...td, color: r.status === "success" ? "green" : r.status === "failed" ? "red" : "#666" }}>
                {r.status}
              </td>
              <td style={td}>{r.generated_at ?? "—"}</td>
              <td style={td}>{r.dbt_version ?? "—"}</td>
              <td style={td}>{r.elapsed_time?.toFixed(2) ?? "—"}</td>
              <td style={td}>{r.results_total}</td>
              <td style={td}>{r.results_passed}</td>
              <td style={td}>{r.results_failed}</td>
            </tr>
          ))}
          {!loading && runs.length === 0 && (
            <tr>
              <td style={td} colSpan={9}>No runs available.</td>
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
