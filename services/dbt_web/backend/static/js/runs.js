function buildQs(o) {
  const p = new URLSearchParams();
  if (o.target) p.set("target", o.target);
  if (o.status) p.set("status", o.status);
  p.set("limit", "100");
  const s = p.toString();
  return s ? "?" + s : "";
}

function loadRuns() {
  const err = document.getElementById("runs-error");
  const body = document.getElementById("runs-body");
  const load = document.getElementById("runs-loading");
  const totals = document.getElementById("runs-totals");
  const target = (document.getElementById("runs-target") || {}).value || "";
  const status = (document.getElementById("runs-status") || {}).value || "";
  if (err) err.textContent = "";
  if (load) load.style.display = "block";
  dbt
    .dbtFetchJson("/runs" + buildQs({ target, status }))
    .then((data) => {
      if (load) load.style.display = "none";
      let t = 0, p = 0, f = 0;
      (data.items || []).forEach((r) => {
        t += r.results_total || 0;
        p += r.results_passed || 0;
        f += r.results_failed || 0;
      });
      if (totals) totals.textContent = "total=" + t + " passed=" + p + " failed=" + f;
      if (body) {
        body.innerHTML = "";
        (data.items || []).forEach((r) => {
          const tr = document.createElement("tr");
          const st = (r.status || "");
          tr.innerHTML =
            "<td>" + (r.target || "") + "</td>" +
            "<td class=mono>" + (r.run_id || "—") + "</td>" +
            "<td class=st-" + st + ">" + st + "</td>" +
            "<td>" + (r.generated_at || "—") + "</td>" +
            "<td>" + (r.dbt_version || "—") + "</td>" +
            "<td>" + (r.elapsed_time != null ? Number(r.elapsed_time).toFixed(2) : "—") + "</td>" +
            "<td>" + (r.results_total ?? "") + "</td>" +
            "<td>" + (r.results_passed ?? "") + "</td>" +
            "<td>" + (r.results_failed ?? "") + "</td>";
          body.appendChild(tr);
        });
        if (data.items && data.items.length === 0) {
          const tr = document.createElement("tr");
          tr.innerHTML = "<td colspan=9 class=muted>No runs available.</td>";
          body.appendChild(tr);
        }
      }
    })
    .catch((e) => {
      if (load) load.style.display = "none";
      if (err) err.textContent = e && e.message ? e.message : String(e);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const f = document.getElementById("runs-filters");
  if (f) {
    f.addEventListener("change", loadRuns);
  }
  loadRuns();
});
