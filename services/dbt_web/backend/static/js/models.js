let modelsT = null;

function buildQs() {
  const p = new URLSearchParams();
  const q = (document.getElementById("m-query") || {}).value || "";
  const tags = (document.getElementById("m-tags") || {}).value || "";
  const resource_type = (document.getElementById("m-rt") || {}).value || "";
  const schema = (document.getElementById("m-schema") || {}).value || "";
  const package_name = (document.getElementById("m-pkg") || {}).value || "";
  if (q) p.set("query", q);
  if (tags) p.set("tags", tags);
  if (resource_type) p.set("resource_type", resource_type);
  if (schema) p.set("schema", schema);
  if (package_name) p.set("package_name", package_name);
  const s = p.toString();
  return s ? "?" + s : "";
}

function loadModels() {
  const err = document.getElementById("models-error");
  const body = document.getElementById("models-body");
  const load = document.getElementById("models-loading");
  const count = document.getElementById("models-count");
  const rts = document.getElementById("models-rts");
  if (err) err.textContent = "";
  if (load) load.style.display = "block";
  dbt
    .dbtFetchJson("/models" + buildQs())
    .then((data) => {
      if (load) load.style.display = "none";
      const items = data.items || [];
      if (count) count.textContent = items.length + " items";
      const types = Array.from(
        new Set(items.map((i) => i.resource_type).filter(Boolean)),
      ).sort();
      if (rts) rts.textContent = "Resource types: " + (types.join(", ") || "—");
      if (body) {
        body.innerHTML = "";
        items.forEach((m) => {
          const tr = document.createElement("tr");
          const dep = (m.depends_on && m.depends_on.length) ? m.depends_on.join(", ") : "—";
          tr.innerHTML =
            "<td class=mono>" + (m.unique_id || "") + "</td>" +
            "<td>" + (m.name || "") + "</td>" +
            "<td>" + (m.resource_type || "") + "</td>" +
            "<td>" + (m.schema || "") + "</td>" +
            "<td>" + (m.package_name || "") + "</td>" +
            "<td>" + (Array.isArray(m.tags) ? m.tags.join(", ") : "—") + "</td>" +
            "<td class=\"mono col-dep\">" + dep + "</td>";
          body.appendChild(tr);
        });
      }
    })
    .catch((e) => {
      if (load) load.style.display = "none";
      if (err) err.textContent = e && e.message ? e.message : String(e);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const f = document.getElementById("models-filters");
  if (f) {
    f.addEventListener("input", () => {
      if (modelsT) clearTimeout(modelsT);
      modelsT = setTimeout(loadModels, 200);
    });
  }
  loadModels();
});
