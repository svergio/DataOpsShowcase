(function () {
  const DEBUG = false;

  const VB_WIDTH = 1200;
  const VB_HEIGHT = 800;
  const MARGIN = 52;
  const CHARGE_STRENGTH = -420;
  const SIM_TICKS = 420;
  const COLLIDE_PADDING = 18;
  const COLLIDE_ITERS = 6;

  let savedZoom = null;
  let zoomK = 1;
  let pointerInVizWrap = false;
  let programmaticZoom = false;

  const GRAPH_STATE_KEY = "portal-c4-graph-v1";

  function loadPersistedGraphState() {
    try {
      const raw = localStorage.getItem(GRAPH_STATE_KEY);
      if (!raw) return null;
      const o = JSON.parse(raw);
      if (o.v !== 1 || !o.zoom || !o.positions) return null;
      return o;
    } catch {
      return null;
    }
  }

  function persistedGraphMatches(nodesRaw, st) {
    if (!st?.positions || st.zoom == null) return false;
    const z = st.zoom;
    if (typeof z.k !== "number" || typeof z.x !== "number" || typeof z.y !== "number") return false;
    const ids = new Set(nodesRaw.map((d) => String(d.id)));
    const pk = Object.keys(st.positions);
    if (ids.size !== pk.length) return false;
    for (const id of ids) {
      const p = st.positions[id];
      if (!p || typeof p.x !== "number" || typeof p.y !== "number") return false;
    }
    return true;
  }

  function persistGraphSnapshot(nodesRaw, transform) {
    if (!transform || typeof transform.k !== "number") return;
    const positions = {};
    nodesRaw.forEach((d) => {
      positions[String(d.id)] = { x: d.x, y: d.y };
    });
    try {
      localStorage.setItem(
        GRAPH_STATE_KEY,
        JSON.stringify({
          v: 1,
          zoom: { k: transform.k, x: transform.x, y: transform.y },
          positions,
        }),
      );
    } catch {
      /* ignore quota */
    }
  }

  function readPayload() {
    const el = document.getElementById("portal-data");
    if (!el) {
      return { services_web: [], services_api: [], graph: { nodes: [], links: [] }, docker_error: null };
    }
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return { services_web: [], services_api: [], graph: { nodes: [], links: [] }, docker_error: String(e) };
    }
  }

  function dotClassForDockerState(state, rollup) {
    if (rollup === "completed") return "done";
    const s = (state || "").toLowerCase();
    if (s === "running") return "ok";
    if (s === "restarting") return "warn";
    if (s === "missing" || s === "exited" || s === "dead") return "bad";
    if (s === "none") return "unknown";
    return "unknown";
  }

  function dotClassForHealth(hc) {
    const h = (hc || "").toLowerCase();
    if (h === "healthy") return "ok";
    if (h === "none") return "unknown";
    if (h === "starting") return "warn";
    if (h === "unhealthy") return "bad";
    return "unknown";
  }

  function dotClassForProbe(ok) {
    if (ok === true) return "ok";
    if (ok === false) return "bad";
    return "unknown";
  }

  function rollupFill(rollup) {
    return (
      {
        healthy: "#dcfce7",
        running: "#dbeafe",
        degraded: "#fef9c3",
        down: "#fee2e2",
        completed: "#e2e8f0",
      }[rollup] || "#f1f5f9"
    );
  }

  function rollupLabel(rollup) {
    const m = {
      healthy: "норма",
      running: "работа",
      degraded: "риск",
      down: "нет",
      completed: "готов",
    };
    return m[rollup] || rollup;
  }

  function bodyRadius(shapeKind) {
    const map = {
      db: 40,
      broker: 42,
      object_store: 42,
      cache: 36,
      gateway: 44,
      orchestrator: 34,
      compute: 40,
      observability: 44,
      batch: 34,
      web_app: 34,
    };
    return map[shapeKind] || 36;
  }

  function clampMarginForNode(d) {
    return bodyRadius(d.shape_kind) + 34;
  }

  function collisionRadius(d) {
    const base = bodyRadius(d.shape_kind) + COLLIDE_PADDING;
    const k = Math.max(0.35, Math.min(2.5, zoomK || 1));
    return base / k;
  }

  function isHeavyShape(kind) {
    return ["db", "broker", "object_store", "gateway", "orchestrator", "compute", "observability"].indexOf(kind) !== -1;
  }

  function linkDistance(l) {
    const ha = isHeavyShape(l.source.shape_kind);
    const hb = isHeavyShape(l.target.shape_kind);
    if (ha && hb) return 220;
    if (!ha && !hb) return 140;
    return 180;
  }

  function placeInitialByGroup(nodes) {
    const d3 = window.d3;
    const innerW = VB_WIDTH - 2 * MARGIN;
    const innerH = VB_HEIGHT - 2 * MARGIN;
    const byG = d3.group(nodes, (d) => Number(d.group));
    const gKeys = [...byG.keys()].sort((a, b) => a - b);
    const bands = Math.max(gKeys.length, 1);
    gKeys.forEach((gk, bi) => {
      const arr = byG.get(gk);
      const m = arr.length;
      const cols = Math.max(1, Math.ceil(Math.sqrt(m * (innerW / innerH))));
      const rows = Math.ceil(m / cols);
      const cellW = innerW / bands;
      const x0 = MARGIN + bi * cellW + cellW * 0.07;
      const x1 = MARGIN + (bi + 1) * cellW - cellW * 0.07;
      const usableW = Math.max(40, x1 - x0);
      const stepX = cols > 1 ? usableW / (cols - 1) : 0;
      const stepY = rows > 1 ? innerH / (rows + 0.85) : innerH / 2;
      arr.forEach((d, j) => {
        const col = j % cols;
        const row = Math.floor(j / cols);
        const jitterX = ((j * 17) % 10) - 5;
        const jitterY = ((j * 31) % 10) - 5;
        d.x = cols === 1 ? x0 + usableW / 2 : x0 + col * stepX + (row % 2) * (stepX * 0.05) + jitterX;
        d.y = MARGIN + (row + 0.85) * stepY + jitterY;
      });
    });
  }

  function drawShape(shapeKind, g, fill, stroke) {
    const st = stroke || "#94a3b8";
    switch (shapeKind) {
      case "db":
        g.append("ellipse").attr("rx", 30).attr("ry", 9).attr("cy", -20).attr("fill", "#f1f5f9").attr("stroke", st);
        g.append("rect").attr("x", -30).attr("y", -20).attr("width", 60).attr("height", 30).attr("fill", fill).attr("stroke", st);
        g.append("ellipse").attr("rx", 30).attr("ry", 9).attr("cy", 10).attr("fill", fill).attr("stroke", st);
        break;
      case "broker":
        g.append("path")
          .attr(
            "d",
            "M-32,-18 L28,-18 L36,0 L28,18 L-32,18 L-40,0 Z",
          )
          .attr("fill", fill)
          .attr("stroke", st);
        break;
      case "object_store":
        g.append("path")
          .attr("d", "M-34,-14 L34,-14 L30,20 L-30,20 Z")
          .attr("fill", fill)
          .attr("stroke", st);
        g.append("path").attr("d", "M-34,-14 L0,-24 L34,-14").attr("fill", "none").attr("stroke", st);
        break;
      case "cache":
        g.append("rect").attr("x", -28).attr("y", -18).attr("width", 56).attr("height", 36).attr("rx", 6).attr("fill", fill).attr("stroke", st);
        g.append("path").attr("d", "M-12,-6 L12,-6 M-12,0 L12,0 M-12,6 L12,6").attr("stroke", st).attr("fill", "none");
        break;
      case "gateway":
        g.append("path")
          .attr(
            "d",
            "M-36,-20 L36,-20 L32,22 L-32,22 Z",
          )
          .attr("fill", fill)
          .attr("stroke", st);
        break;
      case "orchestrator":
        g.append("circle").attr("r", 26).attr("fill", fill).attr("stroke", st);
        g.append("circle").attr("r", 8).attr("fill", "none").attr("stroke", st);
        break;
      case "compute":
        g.append("rect")
          .attr("x", -30)
          .attr("y", -20)
          .attr("width", 60)
          .attr("height", 40)
          .attr("rx", 4)
          .attr("fill", fill)
          .attr("stroke", st);
        g.append("rect").attr("x", -22).attr("y", -12).attr("width", 16).attr("height", 10).attr("fill", "#f8fafc").attr("stroke", st);
        g.append("rect").attr("x", 6).attr("y", -12).attr("width", 16).attr("height", 10).attr("fill", "#f8fafc").attr("stroke", st);
        g.append("rect").attr("x", -22).attr("y", 2).attr("width", 16).attr("height", 10).attr("fill", "#f8fafc").attr("stroke", st);
        g.append("rect").attr("x", 6).attr("y", 2).attr("width", 16).attr("height", 10).attr("fill", "#f8fafc").attr("stroke", st);
        break;
      case "observability":
        g.append("polygon")
          .attr("points", "0,-26 23,-10 23,14 0,26 -23,14 -23,-10")
          .attr("fill", fill)
          .attr("stroke", st);
        break;
      case "batch":
        g.append("rect").attr("x", -32).attr("y", -16).attr("width", 64).attr("height", 32).attr("rx", 4).attr("fill", fill).attr("stroke", st).attr("stroke-dasharray", "4 3");
        break;
      case "web_app":
      default:
        g.append("rect").attr("x", -32).attr("y", -18).attr("width", 64).attr("height", 36).attr("rx", 8).attr("fill", fill).attr("stroke", st);
    }
  }

  function renderGraph(svgSel, graph, options) {
    const opts = options || {};
    if (!svgSel || !window.d3 || !graph) return;
    const d3 = window.d3;
    if (opts.resetLayout) {
      try {
        localStorage.removeItem(GRAPH_STATE_KEY);
      } catch {
        /* ignore */
      }
      savedZoom = null;
    }

    const persisted = !opts.resetLayout ? loadPersistedGraphState() : null;
    const nodesRaw = (graph.nodes || []).map((d) => ({ ...d }));
    const linksRaw = (graph.links || []).map((d) => ({ ...d }));
    const nodeById = new Map(nodesRaw.map((d) => [d.id, d]));
    const links = [];
    for (const l of linksRaw) {
      const s = nodeById.get(l.source);
      const t = nodeById.get(l.target);
      if (s && t) links.push({ source: s, target: t });
    }

    nodesRaw.sort((a, b) => Number(a.group) - Number(b.group) || String(a.id).localeCompare(String(b.id)));

    const usePersist = persisted && persistedGraphMatches(nodesRaw, persisted);

    placeInitialByGroup(nodesRaw);

    if (usePersist) {
      nodesRaw.forEach((d) => {
        const p = persisted.positions[String(d.id)];
        if (p) {
          d.x = p.x;
          d.y = p.y;
        }
      });
      savedZoom = persisted.zoom;
      zoomK = typeof savedZoom.k === "number" ? savedZoom.k : 1;
    } else if (savedZoom && typeof savedZoom.k === "number") {
      zoomK = savedZoom.k;
    } else {
      zoomK = 1;
    }

    const svg = d3.select(svgSel);
    const layer = svg.select(".zoom-layer");
    layer.selectAll("*").remove();

    const zoomBg = layer
      .append("rect")
      .attr("class", "zoom-catch")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", VB_WIDTH)
      .attr("height", VB_HEIGHT)
      .attr("fill", "transparent")
      .attr("pointer-events", "all");

    const linkG = layer.append("g").attr("class", "links");
    const nodeG = layer.append("g").attr("class", "nodes");

    const linkSel = linkG
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("class", "c4-link")
      .attr("stroke", "#cbd5e1")
      .attr("stroke-width", 1.5)
      .style("pointer-events", "none");

    const nodeSel = nodeG
      .selectAll("g.node")
      .data(nodesRaw)
      .join("g")
      .attr("class", "node")
      .style("cursor", "grab");

    nodeSel.each(function (d) {
      const g = d3.select(this);
      const fill = rollupFill(d.rollup);
      drawShape(d.shape_kind, g, fill);
      g.append("text")
        .attr("class", "c4-label")
        .attr("y", 36)
        .attr("text-anchor", "middle")
        .text(d.label_ru.length > 18 ? d.label_ru.slice(0, 16) + "\u2026" : d.label_ru);
      g.append("text")
        .attr("class", "c4-sub")
        .attr("y", 50)
        .attr("text-anchor", "middle")
        .text(rollupLabel(d.rollup));

      const ind = d.indicators || {};
      const triple = [
        { k: ind.docker, t: "Процесс / Docker" },
        { k: ind.health, t: "Healthcheck" },
        { k: ind.reach, t: "Доступность" },
      ];
      const fillMap = { ok: "#16a34a", warn: "#ca8a04", bad: "#dc2626" };
      const step = 14;
      const startX = -((triple.length - 1) * step) / 2;
      triple.forEach((item, i) => {
        const dot = g
          .append("circle")
          .attr("cx", startX + i * step)
          .attr("cy", 62)
          .attr("r", 3.2)
          .attr("fill", fillMap[item.k] || "#94a3b8");
        dot.append("title").text(item.t + ": " + item.k);
      });
    });

    const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

    function clampNode(d) {
      const r = clampMarginForNode(d);
      d.x = clamp(d.x, r, VB_WIDTH - r);
      d.y = clamp(d.y, r, VB_HEIGHT - r);
    }

    function refreshGraphGeometry() {
      linkSel
        .attr("x1", (d) => d.source.x)
        .attr("y1", (d) => d.source.y)
        .attr("x2", (d) => d.target.x)
        .attr("y2", (d) => d.target.y);
      nodeSel.attr("transform", (d) => `translate(${d.x},${d.y})`);
    }

    const collideForce = d3
      .forceCollide()
      .radius((d) => collisionRadius(d))
      .strength(1)
      .iterations(COLLIDE_ITERS);

    const sim = d3
      .forceSimulation(nodesRaw)
      .force(
        "link",
        d3.forceLink(links).id((d) => d.id).distance(linkDistance).strength(0.038),
      )
      .force("charge", d3.forceManyBody().strength(CHARGE_STRENGTH))
      .force("collide", collideForce)
      .force("x", d3.forceX(VB_WIDTH / 2).strength(0.05))
      .force("y", d3.forceY(VB_HEIGHT / 2).strength(0.05))
      .alphaDecay(0.022)
      .velocityDecay(0.3);

    const prevXY = nodesRaw.map((d) => [d.x, d.y]);
    let maxDeltaTick = 0;

    sim.on("tick", () => {
      nodesRaw.forEach((d, i) => {
        maxDeltaTick = Math.max(maxDeltaTick, Math.hypot(d.x - prevXY[i][0], d.y - prevXY[i][1]));
        prevXY[i][0] = d.x;
        prevXY[i][1] = d.y;
      });
      nodesRaw.forEach(clampNode);
      refreshGraphGeometry();
    });

    sim.alpha(usePersist ? 0.22 : 1);
    const layoutTicks = usePersist ? 96 : SIM_TICKS;
    for (let i = 0; i < layoutTicks; i += 1) {
      sim.tick();
    }
    sim.alphaTarget(0);
    sim.stop();
    nodesRaw.forEach(clampNode);
    refreshGraphGeometry();

    if (DEBUG) {
      console.table([
        { force: "charge", value: CHARGE_STRENGTH },
        { force: "link.distance", value: "140-220 by type" },
        { force: "collide.padding", value: COLLIDE_PADDING },
        { force: "collide.iterations", value: COLLIDE_ITERS },
        { force: "velocityDecay", value: 0.3 },
        { force: "ticks", value: usePersist ? 96 : SIM_TICKS },
        { metric: "maxDelta", value: maxDeltaTick.toFixed(4) },
      ]);
      console.table(
        nodesRaw.map((d) => ({
          id: d.id,
          shape: d.shape_kind,
          bodyR: bodyRadius(d.shape_kind),
          collideR: collisionRadius(d).toFixed(1),
          x: d?.x?.toFixed(1),
          y: d?.y?.toFixed(1),
        })),
      );
      const dbg = layer.append("g").attr("class", "debug-overlay");
      dbg
        .append("rect")
        .attr("x", MARGIN)
        .attr("y", MARGIN)
        .attr("width", VB_WIDTH - 2 * MARGIN)
        .attr("height", VB_HEIGHT - 2 * MARGIN)
        .attr("fill", "none")
        .attr("stroke", "#ec4899")
        .attr("stroke-width", 1)
        .attr("stroke-dasharray", "6 4");
      nodesRaw.forEach((d) => {
        dbg
          .append("circle")
          .attr("cx", d.x)
          .attr("cy", d.y)
          .attr("r", collisionRadius(d))
          .attr("fill", "none")
          .attr("stroke", "rgba(236,72,153,0.55)")
          .attr("stroke-width", 1);
      });
    }

    const dragBehavior = d3
      .drag()
      .on("start", function (event, d) {
        event.sourceEvent?.stopPropagation?.();
        d3.select(this).style("cursor", "grabbing");
        sim.alphaTarget(0.35).restart();
        d.fx = d.x;
        d.fy = d.y;
      })
      .on("drag", function (event, d) {
        const [px, py] = d3.pointer(event, layer.node());
        const r = clampMarginForNode(d);
        d.fx = clamp(px, r, VB_WIDTH - r);
        d.fy = clamp(py, r, VB_HEIGHT - r);
      })
      .on("end", function (event, d) {
        d3.select(this).style("cursor", "grab");
        d.fx = null;
        d.fy = null;
        sim.alphaTarget(0);
        refreshGraphGeometry();
        persistGraphSnapshot(nodesRaw, d3.zoomTransform(svg.node()));
      });

    nodeSel.call(dragBehavior);

    const zoom = d3
      .zoom()
      .scaleExtent([0.25, 2.5])
      .filter((event) => {
        if (event.target && event.target.closest && event.target.closest("g.node")) return false;
        return (!event.ctrlKey || event.type === "wheel") && !event.button;
      })
      .on("zoom", (ev) => {
        zoomK = ev.transform.k;
        layer.attr("transform", ev.transform);
      })
      .on("end", (ev) => {
        savedZoom = ev.transform;
        zoomK = ev.transform.k;
        if (!programmaticZoom) {
          collideForce.radius((d) => collisionRadius(d));
          sim.alpha(0.26);
          for (let j = 0; j < 64; j += 1) {
            sim.tick();
            nodesRaw.forEach(clampNode);
          }
          sim.alphaTarget(0);
          sim.stop();
          if (ev.sourceEvent) persistGraphSnapshot(nodesRaw, ev.transform);
        }
        refreshGraphGeometry();
      });

    svg.call(zoom);
    if (savedZoom && typeof savedZoom.k === "number" && typeof savedZoom.x === "number") {
      programmaticZoom = true;
      svg.call(zoom.transform, savedZoom);
      zoomK = savedZoom.k;
      programmaticZoom = false;
    }
  }

  function renderCards(root, services, isApi) {
    if (!root) return;
    root.innerHTML = "";
    for (const s of services) {
      const route = (s.route || "").trim();
      const useLink = Boolean(route);
      const el = useLink ? document.createElement("a") : document.createElement("div");
      el.className = "card" + (isApi ? " card-api" : "");
      if (useLink) {
        el.setAttribute("href", route);
      }

      const main = document.createElement("div");
      main.className = "card-main";

      const h = document.createElement("h3");
      h.className = "card-name";
      h.textContent = s.name;
      main.appendChild(h);

      const path = document.createElement("p");
      path.className = route ? "card-path" : "card-path card-path-empty";
      path.textContent = route || (isApi ? "внутри Docker / см. описание" : "");
      main.appendChild(path);

      const p = document.createElement("p");
      p.className = "card-purpose";
      p.textContent = s.purpose;
      main.appendChild(p);

      const aside = document.createElement("aside");
      aside.className = "card-aside";
      const ind = s.indicators || {};
      const d1 = document.createElement("span");
      d1.className = "dot " + dotClassForDockerState(ind.docker_state, s.rollup);
      d1.title = "Процесс: " + ind.docker_state;
      const d2 = document.createElement("span");
      d2.className = "dot " + dotClassForHealth(ind.healthcheck);
      d2.title = "Healthcheck: " + ind.healthcheck;
      const d3 = document.createElement("span");
      d3.className = "dot " + dotClassForProbe(ind.probe_ok);
      d3.title = ind.probe_ok === null ? "HTTP-проба: не задана" : "HTTP-проба: " + (ind.probe_ok ? "да" : "нет");
      aside.appendChild(d1);
      aside.appendChild(d2);
      aside.appendChild(d3);

      el.appendChild(main);
      el.appendChild(aside);
      root.appendChild(el);
    }
  }

  function paint() {
    const data = readPayload();
    const svgEl = document.querySelector("#c4");
    if (window.d3 && svgEl) renderGraph(svgEl, data.graph);
    renderCards(document.getElementById("cards-web"), data.services_web || [], false);
    renderCards(document.getElementById("cards-api"), data.services_api || [], true);
  }

  paint();

  const vizWrap = document.querySelector(".map-legend-panel .viz-wrap");
  if (vizWrap) {
    vizWrap.addEventListener("pointerenter", () => {
      pointerInVizWrap = true;
    });
    vizWrap.addEventListener("pointerleave", () => {
      pointerInVizWrap = false;
    });
  }

  document.getElementById("btn-graph-reset")?.addEventListener("click", () => {
    const svgEl = document.querySelector("#c4");
    const data = readPayload();
    if (window.d3 && svgEl) renderGraph(svgEl, data.graph, { resetLayout: true });
  });

  async function refresh() {
    try {
      const r = await fetch("/api/status", { headers: { Accept: "application/json" } });
      if (!r.ok) return;
      const data = await r.json();
      const el = document.getElementById("portal-data");
      if (el) el.textContent = JSON.stringify(data);
      const svgEl = document.querySelector("#c4");
      if (window.d3 && svgEl && pointerInVizWrap) renderGraph(svgEl, data.graph);
      renderCards(document.getElementById("cards-web"), data.services_web || [], false);
      renderCards(document.getElementById("cards-api"), data.services_api || [], true);
    } catch (e) {
      /* ignore */
    }
  }

  setInterval(refresh, 15000);
})();
