function qs() {
  const p = new URLSearchParams();
  const target = (document.getElementById("t-target") || {}).value || "";
  const severity = (document.getElementById("t-sev") || {}).value || "";
  if (target) p.set("target", target);
  if (severity) p.set("severity", severity);
  const s = p.toString();
  return s ? "?" + s : "";
}

function loadTests() {
  const err = document.getElementById("tests-error");
  const body = document.getElementById("t-body");
  const load = document.getElementById("tests-loading");
  const panels = document.getElementById("t-panels");
  const total = document.getElementById("t-total");
  if (err) err.textContent = "";
  if (load) load.style.display = "block";
  dbt
    .dbtFetchJson("/tests/summary" + qs())
    .then((data) => {
      if (load) load.style.display = "none";
      if (total) total.textContent = "failed_total=" + (data.failed_total ?? 0);
      if (panels) {
        panels.innerHTML = "";
        const summ = data.summary || {};
        Object.keys(summ).forEach((t) => {
          const v = summ[t];
          const div = document.createElement("div");
          div.className = "panel";
          const failedN = (v && v.failed) || 0;
          div.innerHTML =
            "<div style=font-weight:600>" + t + "</div>" +
            "<div>total: " + (v && v.total) + "</div>" +
            "<div style=color:green>passed: " + (v && v.passed) + "</div>" +
            "<div style=color:" + (failedN > 0 ? "red" : "#666") + ">failed: " + failedN + "</div>";
          panels.appendChild(div);
        });
        if (Object.keys(summ).length === 0) {
          const d = document.createElement("div");
          d.className = "muted";
          d.textContent = "No test summary available.";
          panels.appendChild(d);
        }
      }
      if (body) {
        body.innerHTML = "";
        (data.failed || []).forEach((f) => {
          const tr = document.createElement("tr");
          tr.innerHTML =
            "<td>" + (f.target || "") + "</td>" +
            "<td class=mono>" + (f.unique_id || "") + "</td>" +
            "<td style=color:red>" + (f.status || "") + "</td>" +
            "<td>" + (f.severity || "") + "</td>" +
            "<td>" + (f.execution_time != null ? Number(f.execution_time).toFixed(2) : "—") + "</td>" +
            "<td>" + (f.message || "—") + "</td>";
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
  const f = document.getElementById("tests-filters");
  if (f) f.addEventListener("change", loadTests);
  loadTests();
});
