let lineageDebounceT = null;
const lineageSims = [];
let layoutCache = null;
let lastRaw = null;
const NODE_W = 160;
const NODE_H = 24;
const PAD = 28;
const COMP_GAP = 72;
const MAX_ROW = 2000;
const LAYER_ORDER = [
  "source", "seed", "model.staging", "model.vault", "model.bdv", "model.marts", "model.serving",
  "snapshot", "test", "exposure",
];

function bucketFor(node) {
  if (node.resource_type === "model") {
    const s = (node.schema || "");
    if (s.includes("staging")) return "model.staging";
    if (s.includes("vault")) return "model.vault";
    if (s.includes("bdv")) return "model.bdv";
    if (s.includes("marts")) return "model.marts";
    if (s.includes("serving")) return "model.serving";
    return "model.staging";
  }
  return node.resource_type;
}

function buildQuery() {
  const s = new URLSearchParams();
  const resourceType = (document.getElementById("f-resource") || {}).value || "";
  const schema = (document.getElementById("f-schema") || {}).value || "";
  const tag = (document.getElementById("f-tag") || {}).value || "";
  if (resourceType) s.set("resource_type", resourceType);
  if (schema) s.set("schema", schema);
  if (tag) s.set("tag", tag);
  const q = s.toString();
  return q ? "?" + q : "";
}

function applyHideTests(g, hide) {
  if (!hide) {
    return {
      nodes: g.nodes.map((n) => Object.assign({}, n)),
      edges: (g.edges || []).map((e) => Object.assign({}, e)),
    };
  }
  const nodes = (g.nodes || []).filter((n) => n.resource_type !== "test");
  const ids = new Set(nodes.map((n) => n.id));
  const edges = (g.edges || []).filter((e) => ids.has(e.source) && ids.has(e.target));
  return { nodes, edges };
}

function neighborUndirectedMap(nodeIds, edges) {
  const m = new Map();
  for (const id of nodeIds) m.set(id, new Set());
  for (const e of edges) {
    if (m.has(e.source) && m.has(e.target)) {
      m.get(e.source).add(e.target);
      m.get(e.target).add(e.source);
    }
  }
  return m;
}

function connectedComponents(nodeIds, edges) {
  const list = nodeIds;
  const adj = new Map();
  for (const id of list) adj.set(id, []);
  for (const e of edges) {
    if (!adj.has(e.source) || !adj.has(e.target)) continue;
    adj.get(e.source).push(e.target);
    adj.get(e.target).push(e.source);
  }
  const seen = new Set();
  const comps = [];
  for (const id of list) {
    if (seen.has(id)) continue;
    const st = [id];
    const comp = [];
    while (st.length) {
      const u = st.pop();
      if (seen.has(u)) continue;
      seen.add(u);
      comp.push(u);
      for (const v of adj.get(u) || [])
        if (!seen.has(v)) st.push(v);
    }
    comps.push(comp);
  }
  return comps;
}

function runForceInBox(nodes, linkObjs) {
  if (nodes.length === 0) {
    return { w: 40, h: 40, nodes: [] };
  }
  if (nodes.length === 1) {
    const n = nodes[0];
    n.x = PAD;
    n.y = PAD;
    return { w: NODE_W + 2 * PAD, h: NODE_H + 2 * PAD, nodes: [n] };
  }
  for (const n of nodes) {
    n.x = 0;
    n.y = 0;
  }
  const sim = d3
    .forceSimulation(nodes)
    .force(
      "link",
      d3
        .forceLink(linkObjs)
        .id((d) => d.id)
        .distance(52)
        .strength(0.4),
    )
    .force("charge", d3.forceManyBody().strength(-130))
    .force("collide", d3.forceCollide(20))
    .force("center", d3.forceCenter(0, 0));
  lineageSims.push(sim);
  for (let i = 0; i < 420; i++) sim.tick();
  sim.stop();
  for (const n of nodes) {
    n.x = n.x - NODE_W / 2;
    n.y = n.y - NODE_H / 2;
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of nodes) {
    const x0 = n.x;
    const y0 = n.y;
    const x1 = n.x + NODE_W;
    const y1 = n.y + NODE_H;
    if (x0 < minX) minX = x0;
    if (y0 < minY) minY = y0;
    if (x1 > maxX) maxX = x1;
    if (y1 > maxY) maxY = y1;
  }
  minX -= 12;
  minY -= 12;
  maxX += 12;
  maxY += 12;
  for (const n of nodes) {
    n._fx = n.x - minX + PAD;
    n._fy = n.y - minY + PAD;
  }
  const w = maxX - minX + 2 * PAD;
  const h = maxY - minY + 2 * PAD;
  return { w, h, nodes };
}

function layoutDisjointForce(nodeList, edgeList) {
  const byId = new Map(nodeList.map((n) => [n.id, { ...n, x: 0, y: 0 }]));
  const ids = new Set(nodeList.map((n) => n.id));
  const localEdges = edgeList
    .filter((e) => ids.has(e.source) && ids.has(e.target))
    .map((e) => ({ source: byId.get(e.source), target: byId.get(e.target) }));
  const comps = connectedComponents(Array.from(ids), localEdges);
  const boxes = [];
  for (const comp of comps) {
    const cNodes = comp.map((id) => byId.get(id));
    const cset = new Set(comp);
    const cLinks = localEdges.filter((l) => cset.has(l.source.id) && cset.has(l.target.id));
    const r = runForceInBox(cNodes, cLinks);
    boxes.push({ w: r.w, h: r.h, nodes: r.nodes });
  }
  boxes.sort((a, b) => b.w * b.h - a.w * a.h);
  let x = 0;
  let y = 0;
  let rowH = 0;
  for (const b of boxes) {
    if (x + b.w > MAX_ROW && x > 0) {
      y += rowH + COMP_GAP;
      x = 0;
      rowH = 0;
    }
    for (const n of b.nodes) {
      n.x = n._fx + x;
      n.y = n._fy + y;
    }
    x += b.w + COMP_GAP;
    rowH = Math.max(rowH, b.h);
  }
  const placed = Array.from(byId.values());
  const maxR = placed.length ? d3.max(placed, (d) => d.x + NODE_W) + 40 : 800;
  const maxB = placed.length ? d3.max(placed, (d) => d.y + NODE_H) + 40 : 400;
  return { width: Math.max(800, maxR), height: Math.max(400, maxB), nodes: placed, edgeList, mode: "force" };
}

function sortLayer(a, b) {
  const la = LAYER_ORDER.indexOf(bucketFor(a));
  const lb = LAYER_ORDER.indexOf(bucketFor(b));
  const oa = la >= 0 ? la : 500;
  const ob = lb >= 0 ? lb : 500;
  if (oa !== ob) return oa - ob;
  return (a.name || a.id).localeCompare(b.name || b.id, undefined, { sensitivity: "base" });
}

function layoutArc(nodeList, edgeList) {
  const byLayer = new Map();
  for (const n of nodeList) {
    const k = bucketFor(n);
    if (!byLayer.has(k)) byLayer.set(k, []);
    byLayer.get(k).push(n);
  }
  const orderKeys = LAYER_ORDER.filter((k) => byLayer.get(k) && byLayer.get(k).length);
  for (const k of byLayer.keys()) {
    if (!orderKeys.includes(k)) orderKeys.push(k);
  }
  let y = 20;
  const rowH = 44;
  const colW = 200;
  const placed = new Map();
  for (const k of orderKeys) {
    const row = (byLayer.get(k) || []).slice().sort(sortLayer);
    let x = 20;
    for (const n of row) {
      n.x = x;
      n.y = y;
      placed.set(n.id, n);
      x += colW;
    }
    y += rowH;
  }
  for (const n of nodeList) {
    if (placed.get(n.id)) {
      n.x = placed.get(n.id).x;
      n.y = placed.get(n.id).y;
    }
  }
  const maxX = d3.max(nodeList, (d) => d.x + NODE_W) + 40;
  const maxY = d3.max(nodeList, (d) => d.y + NODE_H) + 40;
  return {
    width: Math.max(800, maxX),
    height: Math.max(400, maxY),
    nodes: nodeList,
    edgeList,
    mode: "arc",
  };
}

function edgeD(edge, byId, mode) {
  const a = byId.get(edge.source);
  const b = byId.get(edge.target);
  if (!a || !b) return null;
  const x1 = a.x + NODE_W;
  const y1 = a.y + NODE_H / 2;
  const x2 = b.x;
  const y2 = b.y + NODE_H / 2;
  if (mode === "force") {
    return "M" + x1 + "," + y1 + " L" + x2 + "," + y2;
  }
  const cx = (x1 + x2) / 2;
  const hLift = 36 + Math.min(100, 0.08 * Math.abs(x2 - x1));
  const yTop = Math.min(y1, y2) - hLift;
  return "M" + x1 + "," + y1 + " Q" + cx + "," + yTop + " " + x2 + "," + y2;
}

function stopAllSims() {
  while (lineageSims.length) {
    const s = lineageSims.pop();
    s.stop();
  }
}

function highlightSet(selectedId, neigh, nodeIds) {
  if (!selectedId) return null;
  const s = new Set([selectedId]);
  const n = neigh.get(selectedId);
  if (n) n.forEach((u) => s.add(u));
  return s;
}

function paint(svg, byId, neigh, selectedId) {
  const hilite = highlightSet(selectedId, neigh, null);
  const z = d3.select(svg.node().querySelector("g.lineage-z"));
  if (z.empty()) return;
  const edgeG = z.select("g.lineage-edges");
  const nodeG = z.select("g.lineage-nodes");
  edgeG.selectAll("path").attr("class", (d) => {
    if (!hilite) return "edge-path";
    const hit = hilite.has(d.source) && hilite.has(d.target);
    return "edge-path" + (hit ? "" : " lineage-dim");
  });
  nodeG.selectAll("g.node").attr("class", (d) => {
    if (!hilite) return "node" + (d.id === selectedId ? " selected" : "");
    if (d.id === selectedId) return "node selected";
    if (hilite.has(d.id)) return "node neigh";
    return "node lineage-dim-weak";
  });
  nodeG.selectAll("g.node rect").attr("fill", (d) => (d.id === selectedId ? "#dbeafe" : "#fff"));
  nodeG.selectAll("g.node rect").attr("stroke", (d) => (d.id === selectedId ? "#2563eb" : "#cbd5e1"));
}

function buildViz(svg, layout, byId, neigh, selectedId) {
  const w = layout.width;
  const h = layout.height;
  const hilite = highlightSet(selectedId, neigh, null);
  svg.selectAll("*").remove();
  svg.attr("viewBox", [0, 0, w, h].join(" ")).attr("width", w).attr("height", h);
  const defs = svg.append("defs");
  defs
    .append("marker")
    .attr("id", "lineage-arrow")
    .attr("viewBox", "0 0 10 10")
    .attr("refX", 10)
    .attr("refY", 5)
    .attr("markerWidth", 6)
    .attr("markerHeight", 6)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,0 L10,5 L0,10 z")
    .attr("fill", "#6b7280");
  const root = svg.append("g").attr("class", "lineage-z");
  const edgeG = root.append("g").attr("class", "lineage-edges");
  const es = (layout.edgeList || []).map((e) => ({
    source: e.source,
    target: e.target,
  }));
  edgeG
    .selectAll("path")
    .data(es, (d) => d.source + "->" + d.target)
    .enter()
    .append("path")
    .attr("d", (d) => edgeD(d, byId, layout.mode) || "M0,0")
    .attr("class", (d) => {
      if (!hilite) return "edge-path";
      const hit = hilite.has(d.source) && hilite.has(d.target);
      return "edge-path" + (hit ? "" : " lineage-dim");
    })
    .attr("stroke", "#9ca3af")
    .attr("stroke-width", 1)
    .attr("marker-end", "url(#lineage-arrow)");
  const nodeG = root.append("g").attr("class", "lineage-nodes");
  const nodeJoin = nodeG
    .selectAll("g.node")
    .data(layout.nodes, (d) => d.id)
    .enter()
    .append("g")
    .attr("class", (d) => {
      if (!hilite) return "node";
      if (d.id === selectedId) return "node selected";
      if (hilite.has(d.id)) return "node neigh";
      return "node lineage-dim-weak";
    })
    .attr("transform", (d) => "translate(" + d.x + "," + d.y + ")")
    .style("cursor", "pointer");
  nodeJoin
    .append("rect")
    .attr("width", NODE_W)
    .attr("height", NODE_H)
    .attr("rx", 4)
    .attr("fill", (d) => (d.id === selectedId ? "#dbeafe" : "#fff"))
    .attr("stroke", (d) => (d.id === selectedId ? "#2563eb" : "#cbd5e1"));
  nodeJoin
    .append("text")
    .attr("x", 8)
    .attr("y", 16)
    .attr("font-size", 11)
    .attr("font-family", "ui-monospace, monospace")
    .text((d) => {
      const n = d.name && d.name.length > 24 ? d.name.slice(0, 22) + "…" : d.name || d.id;
      return n;
    });
  nodeJoin.on("click", (e, d) => {
    e.stopPropagation();
    setSelected(d.id, false);
  });
  layoutCache = { ...layout, byId, neigh, selectedId, mode: layout.mode };
  return root;
}

function doLayoutForGraph(g, mode) {
  stopAllSims();
  const { nodes, edges } = g;
  if (!nodes.length) {
    return { width: 600, height: 320, nodes: [], edgeList: [], mode, empty: true };
  }
  const list = nodes.map((n) => Object.assign({ x: 0, y: 0 }, n));
  const ed = edges.map((e) => Object.assign({}, e));
  if (mode === "arc") {
    return layoutArc(list, ed);
  }
  return layoutDisjointForce(list, ed);
}

function getMode() {
  const g = document.getElementById("lineage-mode");
  if (!g) return "force";
  const a = g.querySelector("button.active");
  return (a && a.getAttribute("data-mode")) || "force";
}

let zoom = null;
let svgRef = null;

function attachZoom(svg) {
  const r = svg.select("g.lineage-z");
  if (r.empty()) return;
  if (!zoom) {
    zoom = d3.zoom().scaleExtent([0.15, 4]);
  }
  zoom.on("zoom", (e) => {
    d3.select("#lineage-svg").select("g.lineage-z").attr("transform", e.transform);
  });
  svg.call(zoom);
  svg.call(zoom.transform, d3.zoomIdentity);
  svgRef = svg;
}

function resetZoom() {
  if (svgRef) svgRef.transition().duration(300).call(zoom.transform, d3.zoomIdentity);
}

function focusNodeId(id) {
  if (!layoutCache || !layoutCache.byId) return;
  const n = layoutCache.byId.get(id);
  if (!n || n.x == null) return;
  if (!svgRef) return;
  const w = +svgRef.attr("width");
  const h = +svgRef.attr("height");
  const cx = n.x + NODE_W / 2;
  const cy = n.y + NODE_H / 2;
  const k = 1.35;
  const t = d3.zoomIdentity.translate(w / 2 - k * cx, h / 2 - k * cy).scale(k);
  svgRef.transition().duration(500).call(zoom.transform, t);
}

function findNodeIdQuery(q) {
  if (!layoutCache || !q) return null;
  const t = String(q).trim().toLowerCase();
  if (!t) return null;
  for (const n of layoutCache.nodes) {
    if ((n.id && n.id.toLowerCase().indexOf(t) >= 0) || (n.name && n.name.toLowerCase().indexOf(t) >= 0)) {
      return n.id;
    }
  }
  return null;
}

function setSelected(id, drawOnly) {
  if (!layoutCache) return;
  const detailEl = document.getElementById("lineage-detail");
  if (id && layoutCache.byId) {
    const o = layoutCache.byId.get(id);
    if (detailEl) detailEl.textContent = o ? JSON.stringify(o, null, 2) : "";
  } else if (detailEl) detailEl.textContent = "";
  layoutCache.selectedId = id;
  const svg = d3.select("#lineage-svg");
  if (!svg.empty() && !drawOnly) {
    paint(svg, layoutCache.byId, layoutCache.neigh, id);
  }
}

function fullRedrawFromData(raw, selectedId) {
  const hide = (document.getElementById("lineage-hide-tests") || {}).checked;
  const g = applyHideTests(raw, hide);
  const mode = getMode();
  const layout = doLayoutForGraph(g, mode);
  const byId = new Map(layout.nodes.map((n) => [n.id, n]));
  const nids = new Set(g.nodes.map((n) => n.id));
  const neigh = neighborUndirectedMap(nids, g.edges);
  if (layout.empty) {
    const em = d3.select("#lineage-svg");
    em.selectAll("*").remove();
    em
      .attr("viewBox", "0 0 800 400")
      .attr("width", 800)
      .attr("height", 400)
      .append("text")
      .attr("x", 200)
      .attr("y", 200)
      .attr("class", "muted")
      .attr("fill", "#64748b")
      .text("No nodes match current filters.");
    layoutCache = { ...layout, byId, neigh, selectedId: null, nodes: [] };
    const countEl = document.getElementById("lineage-count");
    if (countEl && raw) {
      countEl.textContent = "nodes=0 edges=0";
    }
    return;
  }
  const svg = d3.select("#lineage-svg");
  buildViz(svg, layout, byId, neigh, selectedId || null);
  attachZoom(svg);
  if (selectedId) setSelected(selectedId, true);
  else setSelected(null, true);
  const countEl = document.getElementById("lineage-count");
  if (countEl && raw) {
    countEl.textContent = "nodes=" + g.nodes.length + " edges=" + g.edges.length;
  }
}

function renderLineage() {
  const el = document.getElementById("lineage-error");
  const loadEl = document.getElementById("lineage-loading");
  if (el) el.textContent = "";
  if (loadEl) loadEl.style.display = "block";
  dbt
    .dbtFetchJson("/lineage" + buildQuery())
    .then((graph) => {
      if (loadEl) loadEl.style.display = "none";
      lastRaw = graph;
      const sel = (layoutCache && layoutCache.selectedId) || null;
      fullRedrawFromData(graph, sel);
    })
    .catch((e) => {
      if (loadEl) loadEl.style.display = "none";
      if (el) el.textContent = "Error: " + (e && e.message ? e.message : String(e));
    });
}

function clientRedraw() {
  if (!lastRaw) return;
  const sel = (layoutCache && layoutCache.selectedId) || null;
  fullRedrawFromData(lastRaw, sel);
}

document.addEventListener("DOMContentLoaded", () => {
  const f = document.getElementById("lineage-filters");
  if (f) {
    f.addEventListener("input", (ev) => {
      const t = ev.target;
      if (t && (t.id || "").indexOf("f-") === 0) {
        if (lineageDebounceT) clearTimeout(lineageDebounceT);
        lineageDebounceT = setTimeout(renderLineage, 300);
      }
    });
  }
  const modeG = document.getElementById("lineage-mode");
  if (modeG) {
    modeG.addEventListener("click", (ev) => {
      const b = ev.target.closest("button[data-mode]");
      if (!b) return;
      modeG.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
      b.classList.add("active");
      clientRedraw();
    });
  }
  const htc = document.getElementById("lineage-hide-tests");
  if (htc) htc.addEventListener("change", clientRedraw);
  const resetB = document.getElementById("lineage-reset");
  if (resetB) {
    resetB.addEventListener("click", () => {
      resetZoom();
    });
  }
  const goB = document.getElementById("lineage-go");
  const searchI = document.getElementById("lineage-search");
  function runFocus() {
    const q = (searchI && searchI.value) || "";
    const id = findNodeIdQuery(q);
    if (!id) return;
    setSelected(id, false);
    focusNodeId(id);
  }
  if (goB) goB.addEventListener("click", runFocus);
  if (searchI) {
    searchI.addEventListener("keydown", (e) => {
      if (e.key === "Enter") runFocus();
    });
  }
  const tip = d3.select("#tooltip");
  d3.select("#lineage-svg").on("click", (ev) => {
    if (ev.target && ev.target.closest && ev.target.closest("g.node")) return;
    setSelected(null, false);
  });
  document
    .getElementById("lineage-svg")
    .addEventListener("mousemove", (e) => {
      const n = e.target && e.target.closest("g.node");
      if (tip.empty()) return;
      if (!n) {
        tip.style("display", "none");
        return;
      }
      const d = d3.select(n).datum();
      if (!d) return;
      tip
        .html(
          "<strong>" + (d.name || "") + "</strong><br><span class=mut>" + (d.id || "") + "</span><br>type: " + (d.resource_type || "") + " " + (d.schema || "") + "",
        )
        .style("left", e.clientX + 14 + "px")
        .style("top", e.clientY + 14 + "px")
        .style("display", "block");
    });
  document.getElementById("lineage-svg").addEventListener("mouseleave", () => {
    if (!tip.empty()) tip.style("display", "none");
  });
  renderLineage();
});
