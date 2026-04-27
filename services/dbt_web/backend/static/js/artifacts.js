function loadArt() {
  const runId = (document.getElementById("a-run") || {}).value || "";
  const name = (document.getElementById("a-name") || {}).value || "manifest.json";
  const out = document.getElementById("a-out");
  const err = document.getElementById("a-error");
  const load = document.getElementById("a-loading");
  const meta = document.getElementById("a-meta");
  if (err) err.textContent = "";
  if (!runId) {
    if (err) err.textContent = "run_id required";
    return;
  }
  if (load) load.style.display = "block";
  if (out) out.textContent = "";
  dbt
    .dbtFetchJson("/runs/" + encodeURIComponent(runId) + "/artifacts/" + encodeURIComponent(name))
    .then((env) => {
      if (load) load.style.display = "none";
      if (meta) {
        meta.textContent = "run_id=" + (env.run_id || "") + " size=" + (env.size != null ? env.size : "?") + " " + (env.cached ? " cached" : "");
      }
      if (out) {
        if (typeof env.content === "string") {
          out.textContent = env.content;
        } else {
          out.textContent = JSON.stringify(env.content != null ? env.content : env, null, 2);
        }
      }
    })
    .catch((e) => {
      if (load) load.style.display = "none";
      if (err) err.textContent = e && e.message ? e.message : String(e);
    });
}

document.addEventListener("DOMContentLoaded", () => {
  const b = document.getElementById("a-go");
  if (b) b.addEventListener("click", loadArt);
});
