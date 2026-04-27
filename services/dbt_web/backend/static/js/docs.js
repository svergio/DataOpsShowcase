let manifest = null;
let selectedId = null;

function mergeList(m) {
  return Object.values(m.nodes || {}).concat(Object.values(m.sources || {}));
}

function renderDetail(node) {
  const detail = document.getElementById("d-detail");
  if (!detail) return;
  if (!node) {
    detail.innerHTML = "<p class=muted>Select a resource from the list.</p>";
    return;
  }
  let html =
    "<h3 style=margin-top:0>" + (node.name || "") + "</h3>" +
    "<div class=muted style=font-size:12px>" +
    (node.resource_type || "") + " / " + (node.schema || "") + " / " + (node.package_name || "") +
    "</div>" +
    "<p>" + (node.description || "No description.") + "</p>";
  if (Array.isArray(node.tags) && node.tags.length) {
    html += "<div>tags: " + node.tags.join(", ") + "</div>";
  }
  if (node.columns && Object.keys(node.columns).length) {
    html += "<h4>Columns</h4><table><thead><tr><th>Name</th><th>Type</th><th>Description</th></tr></thead><tbody>";
    Object.values(node.columns).forEach((c) => {
      html += "<tr><td class=mono>" + (c.name || "—") + "</td><td>" + (c.data_type || "—") + "</td><td>" + (c.description || "—") + "</td></tr>";
    });
    html += "</tbody></table>";
  }
  detail.innerHTML = html;
}

function render() {
  const f = (document.getElementById("d-filter") || {}).value || "";
  const rt = (document.getElementById("d-rt") || {}).value || "";
  const list = document.getElementById("d-list");
  const cnt = document.getElementById("d-count");
  if (!manifest) return;
  const q = f.toLowerCase();
  const rows = mergeList(manifest).filter((n) => {
    if (rt && n.resource_type !== rt) return false;
    if (q && !String(n.name || "").toLowerCase().includes(q)) return false;
    return true;
  });
  if (cnt) cnt.textContent = rows.length + " items";
  if (list) {
    list.innerHTML = "";
    rows.forEach((n) => {
      const uid = n.unique_id || "";
      const row = document.createElement("div");
      row.className = "row" + (selectedId === uid ? " sel" : "");
      row.innerHTML =
        "<div class=muted style=font-size:11px>" + (n.resource_type || "") + "</div><div>" + (n.name || uid) + "</div>";
      row.addEventListener("click", () => {
        selectedId = uid;
        render();
        const node = rows.find((x) => (x.unique_id || "") === uid) || n;
        renderDetail(node);
      });
      list.appendChild(row);
    });
  }
  if (selectedId) {
    const node = mergeList(manifest).find((n) => (n.unique_id || "") === selectedId);
    if (node) renderDetail(node);
  } else {
    renderDetail(null);
  }
}

function load() {
  const err = document.getElementById("docs-error");
  const load = document.getElementById("docs-loading");
  if (err) err.textContent = "";
  if (load) load.style.display = "block";
  dbt
    .dbtFetchJson("/docs/manifest")
    .then((data) => {
      manifest = data;
      if (load) load.style.display = "none";
      render();
    })
    .catch((e) => {
      if (load) load.style.display = "none";
      if (err) err.textContent = e && e.message ? e.message : String(e);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const f = document.getElementById("docs-filters");
  if (f) f.addEventListener("input", () => (manifest ? render() : null));
  load();
});
