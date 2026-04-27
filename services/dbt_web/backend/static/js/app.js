function apiBase() {
  return window.DBT_API_BASE || "/api/v1";
}

async function dbtFetchJson(path, init) {
  const url = path.startsWith("http") ? path : apiBase() + path;
  const r = await fetch(url, init);
  if (!r.ok) {
    const t = await r.text();
    throw new Error("API " + r.status + ": " + t.slice(0, 400));
  }
  if (r.status === 204) return null;
  return r.json();
}

window.dbt = { apiBase, dbtFetchJson };
