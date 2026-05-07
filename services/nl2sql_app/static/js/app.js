const form = document.getElementById("query-form");
const input = document.getElementById("question");
const submitButton = form.querySelector('button[type="submit"]');
const messages = document.getElementById("messages");
const sqlOutput = document.getElementById("sql-output");
const chartRoot = document.getElementById("chart-root");
const taskMeta = document.getElementById("task-meta");
const taskFlow = document.getElementById("task-flow");
const taskStages = document.getElementById("task-stages");
const queueStatus = document.getElementById("queue-status");
const queueList = document.getElementById("queue-list");

const stateLabels = {
  queued: "В очереди",
  processing: "Выполняется",
  done: "Готово",
  error: "Ошибка",
};

const stageLabels = {
  queued: "В очереди",
  processing: "Выполняется",
  model_load: "Загрузка модели",
  rag_retrieval: "RAG по схеме",
  sql_generation: "Генерация SQL",
  sql_validation: "Валидация SQL",
  sql_execution: "Выполнение SQL",
  done: "Выполнено",
  error: "Ошибка",
};

const stageSequence = [
  "queued",
  "processing",
  "model_load",
  "rag_retrieval",
  "sql_generation",
  "sql_validation",
  "sql_execution",
  "done",
  "error",
];

const requestQueue = [];
let isProcessing = false;
let activeJobId = null;
let currentTaskStage = "queued";
let currentTaskStatus = "queued";

function formatTaskMeta(jobId, stage, queuePosition, elapsedMs) {
  const parts = [`job_id: ${jobId}`];
  if (Number.isFinite(queuePosition) && queuePosition > 0) {
    parts.push(`очередь: #${queuePosition}`);
  }
  if (Number.isFinite(elapsedMs) && elapsedMs > 0) {
    parts.push(`ожидание: ${Math.round(elapsedMs / 1000)}с`);
  }
  if (stage) {
    parts.push(`этап: ${stageLabels[stage] || stage}`);
  }
  return parts.join(" · ");
}

function clearMessagesPlaceholder() {
  const ph = messages.querySelector(".messages-placeholder");
  if (ph) {
    ph.remove();
  }
}

function addMessage(role, text) {
  clearMessagesPlaceholder();
  const node = document.createElement("div");
  node.className = `message ${role}`;
  node.textContent = text;
  messages.appendChild(node);
  messages.scrollTop = messages.scrollHeight;
}

function shorten(text, maxLength = 90) {
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function queueMetrics() {
  const waiting = requestQueue.filter((item) => item.state === "queued").length;
  const processing = requestQueue.filter((item) => item.state === "processing").length;
  return { waiting, processing };
}

function updateQueueStatus() {
  const { waiting, processing } = queueMetrics();
  if (processing > 0) {
    queueStatus.textContent = `Запрос выполняется. В очереди: ${waiting}.`;
    queueStatus.classList.add("is-busy");
    return;
  }
  if (waiting > 0) {
    queueStatus.textContent = `В очереди: ${waiting}.`;
    queueStatus.classList.remove("is-busy");
    return;
  }
  queueStatus.textContent = "Очередь пуста.";
  queueStatus.classList.remove("is-busy");
}

function renderQueue() {
  queueList.innerHTML = "";
  const visible = requestQueue.slice(-6);
  if (!visible.length) {
    const empty = document.createElement("li");
    empty.className = "queue-empty";
    empty.textContent = "Очередь пуста";
    queueList.appendChild(empty);
    updateQueueStatus();
    return;
  }

  visible.forEach((item) => {
    const li = document.createElement("li");
    li.className = `queue-item is-${item.state}`;

    const text = document.createElement("span");
    text.className = "queue-item-text";
    text.textContent = shorten(item.question);

    const status = document.createElement("span");
    status.className = "queue-item-state";
    const elapsedText = Number.isFinite(item.elapsedMs) ? ` (${Math.round(item.elapsedMs / 1000)}с)` : "";
    status.textContent = `${stateLabels[item.state]}${elapsedText}`;

    li.appendChild(text);
    li.appendChild(status);
    queueList.appendChild(li);
  });

  updateQueueStatus();
}

function updateTaskStage(stage, status) {
  currentTaskStage = stageSequence.includes(stage) ? stage : "queued";
  currentTaskStatus = status || currentTaskStage;
  renderTaskFlow(currentTaskStage, currentTaskStatus);

  const activeStage = currentTaskStage;
  const activeIndex = stageSequence.indexOf(activeStage);
  const isErrorStatus = currentTaskStatus === "error" || activeStage === "error";
  const isDoneStatus = currentTaskStatus === "done" || activeStage === "done";

  Array.from(taskStages.querySelectorAll("li")).forEach((node) => {
    node.classList.remove("is-active", "is-done", "is-error");
    const nodeStage = node.getAttribute("data-stage");
    const nodeIndex = stageSequence.indexOf(nodeStage);

    if (isErrorStatus && nodeStage === "error") {
      node.classList.add("is-error");
      return;
    }
    if (isDoneStatus && nodeStage === "done") {
      node.classList.add("is-done");
      return;
    }
    if (nodeStage !== "error" && nodeStage !== "done" && nodeIndex >= 0 && nodeIndex < activeIndex) {
      node.classList.add("is-done");
      return;
    }
    if (!isErrorStatus && nodeStage === activeStage) {
      node.classList.add("is-active");
    }
  });
}

function resolveStageStatus(nodeStage, activeStage, status) {
  if (nodeStage === "error") {
    return status === "error" || activeStage === "error" ? "error" : "pending";
  }
  if (nodeStage === "done") {
    return status === "done" || activeStage === "done" ? "done" : "pending";
  }

  const normalizedActive = stageSequence.includes(activeStage) ? activeStage : "queued";
  const nodeIndex = stageSequence.indexOf(nodeStage);
  const activeIndex = stageSequence.indexOf(normalizedActive);
  if (nodeIndex < 0 || activeIndex < 0) {
    return "pending";
  }
  if (normalizedActive !== "error" && nodeIndex < activeIndex) {
    return "done";
  }
  if (nodeStage === normalizedActive && normalizedActive !== "done" && normalizedActive !== "error") {
    return "active";
  }
  return "pending";
}

function renderTaskFlow(stage, status) {
  if (!taskFlow || typeof d3 === "undefined") {
    return;
  }
  taskFlow.innerHTML = "";

  const width = Math.max(taskFlow.clientWidth || 0, 320);
  const compact = width < 760;
  const panelPadding = compact ? 12 : 14;
  const sectionGap = compact ? 10 : 14;
  const nodeWidth = compact ? 132 : 142;
  const nodeHeight = compact ? 34 : 38;
  const nodeGap = compact ? 8 : 10;
  const headingSpace = 30;
  const legendSpace = 22;

  const sectionConfig = [
    { id: "queue", label: "Queue", nodes: ["queued", "processing"] },
    { id: "llm", label: "LLM", nodes: ["model_load", "rag_retrieval"] },
    { id: "sql", label: "SQL", nodes: ["sql_generation", "sql_validation", "sql_execution"] },
    { id: "result", label: "Result", nodes: ["done", "error"] },
  ];

  const maxNodesInSection = Math.max(...sectionConfig.map((item) => item.nodes.length));
  const innerHeight = maxNodesInSection * nodeHeight + (maxNodesInSection - 1) * nodeGap;
  const height = panelPadding * 2 + headingSpace + innerHeight + legendSpace;
  const usableWidth = Math.max(width - panelPadding * 2, 260);
  const sectionWidth = Math.max(usableWidth / sectionConfig.length - sectionGap, nodeWidth + 10);

  const colorByStatus = {
    pending: { fill: "#f8fafc", stroke: "#cbd5e1", text: "#475569" },
    active: { fill: "#eaf2ff", stroke: "#2563eb", text: "#1e3a8a" },
    done: { fill: "#ecfdf5", stroke: "#16a34a", text: "#166534" },
    error: { fill: "#fef2f2", stroke: "#dc2626", text: "#991b1b" },
  };

  const sectionColors = {
    queue: { fill: "#f8fafc", stroke: "#dbe4ef", text: "#334155" },
    llm: { fill: "#f8fafc", stroke: "#dbe4ef", text: "#334155" },
    sql: { fill: "#f8fafc", stroke: "#dbe4ef", text: "#334155" },
    result: { fill: "#f8fafc", stroke: "#dbe4ef", text: "#334155" },
  };

  const linkColorByStatus = {
    pending: "#cbd5e1",
    active: "#2563eb",
    done: "#16a34a",
    error: "#dc2626",
  };

  const sections = sectionConfig.map((section, index) => {
    const x = panelPadding + index * (sectionWidth + sectionGap);
    const y = panelPadding;
    return {
      ...section,
      x,
      y,
      width: sectionWidth,
      height: headingSpace + innerHeight + 8,
    };
  });

  const nodes = [];
  const nodeById = {};
  sections.forEach((section) => {
    const total = section.nodes.length;
    const sectionNodeWidth = Math.min(nodeWidth, Math.max(section.width - 12, 108));
    const startY = panelPadding + headingSpace + (innerHeight - (total * nodeHeight + (total - 1) * nodeGap)) / 2;
    const nodeX = section.x + (section.width - sectionNodeWidth) / 2;
    section.nodes.forEach((id, index) => {
      const y = startY + index * (nodeHeight + nodeGap);
      const stageStatus = resolveStageStatus(id, stage, status);
      const node = {
        id,
        sectionId: section.id,
        label: stageLabels[id] || id,
        x: nodeX,
        y,
        width: sectionNodeWidth,
        height: nodeHeight,
        cx: nodeX + sectionNodeWidth / 2,
        cy: y + nodeHeight / 2,
        status: stageStatus,
      };
      nodes.push(node);
      nodeById[id] = node;
    });
  });

  const links = [
    ["queued", "processing"],
    ["processing", "model_load"],
    ["model_load", "rag_retrieval"],
    ["rag_retrieval", "sql_generation"],
    ["sql_generation", "sql_validation"],
    ["sql_validation", "sql_execution"],
    ["sql_execution", "done"],
    ["sql_execution", "error"],
  ]
    .map(([sourceId, targetId]) => {
      const source = nodeById[sourceId];
      const target = nodeById[targetId];
      if (!source || !target) {
        return null;
      }

      let edgeStatus = "pending";
      if (targetId === "error") {
        edgeStatus = status === "error" || stage === "error" ? "error" : "pending";
      } else if (targetId === "done") {
        edgeStatus = status === "done" || stage === "done" ? "done" : "pending";
      } else if (source.status === "done") {
        edgeStatus = "done";
      } else if (source.status === "active" || target.status === "active") {
        edgeStatus = "active";
      }

      return {
        source,
        target,
        status: edgeStatus,
      };
    })
    .filter(Boolean);

  const svg = d3
    .select(taskFlow)
    .append("svg")
    .attr("class", "task-flow-svg")
    .attr("viewBox", `0 0 ${width} ${height}`)
    .attr("preserveAspectRatio", "xMidYMid meet");

  const defs = svg.append("defs");
  Object.entries(linkColorByStatus).forEach(([state, color]) => {
    defs
      .append("marker")
      .attr("id", `flow-arrow-${state}`)
      .attr("viewBox", "0 0 10 10")
      .attr("refX", 9)
      .attr("refY", 5)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto-start-reverse")
      .append("path")
      .attr("d", "M 0 0 L 10 5 L 0 10 z")
      .attr("fill", color);
  });

  const sectionLayer = svg.append("g").attr("class", "task-flow-sections");
  const section = sectionLayer.selectAll("g").data(sections).join("g");
  section
    .append("rect")
    .attr("x", (d) => d.x)
    .attr("y", (d) => d.y)
    .attr("width", (d) => d.width)
    .attr("height", (d) => d.height)
    .attr("rx", 10)
    .attr("ry", 10)
    .attr("fill", (d) => sectionColors[d.id].fill)
    .attr("stroke", (d) => sectionColors[d.id].stroke)
    .attr("stroke-width", 1);
  section
    .append("text")
    .attr("x", (d) => d.x + d.width / 2)
    .attr("y", (d) => d.y + 16)
    .attr("text-anchor", "middle")
    .attr("class", "task-flow-section-label")
    .attr("fill", (d) => sectionColors[d.id].text)
    .text((d) => d.label);

  svg
    .append("g")
    .attr("class", "task-flow-links")
    .selectAll("path")
    .data(links)
    .join("path")
    .attr("d", (d) => {
      const startX = d.source.x + d.source.width;
      const startY = d.source.cy;
      const endX = d.target.x;
      const endY = d.target.cy;
      const bend = Math.max((endX - startX) * 0.55, 18);
      return `M ${startX} ${startY} C ${startX + bend} ${startY}, ${endX - bend} ${endY}, ${endX} ${endY}`;
    })
    .attr("fill", "none")
    .attr("stroke", (d) => linkColorByStatus[d.status])
    .attr("stroke-width", (d) => (d.status === "active" ? 2.2 : 1.8))
    .attr("stroke-dasharray", (d) => (d.status === "pending" ? "4 4" : null))
    .attr("marker-end", (d) => `url(#flow-arrow-${d.status})`);

  const node = svg.append("g").attr("class", "task-flow-nodes").selectAll("g").data(nodes).join("g");

  node
    .append("rect")
    .attr("x", (d) => d.x)
    .attr("y", (d) => d.y)
    .attr("width", (d) => d.width)
    .attr("height", (d) => d.height)
    .attr("rx", 8)
    .attr("ry", 8)
    .attr("fill", (d) => colorByStatus[d.status].fill)
    .attr("stroke", (d) => colorByStatus[d.status].stroke)
    .attr("stroke-width", (d) => (d.status === "active" ? 2.4 : 1.5));

  node
    .append("text")
    .attr("x", (d) => d.cx)
    .attr("y", (d) => d.cy)
    .attr("text-anchor", "middle")
    .attr("dominant-baseline", "central")
    .attr("class", "task-flow-label")
    .attr("fill", (d) => colorByStatus[d.status].text)
    .text((d) => d.label);

  const legendItems = [
    { id: "pending", label: "pending" },
    { id: "active", label: "active" },
    { id: "done", label: "done" },
    { id: "error", label: "error" },
  ];

  const legendX = panelPadding;
  const legendY = panelPadding + headingSpace + innerHeight + 12;
  const legend = svg.append("g").attr("class", "task-flow-legend");
  const item = legend.selectAll("g").data(legendItems).join("g");
  item.attr("transform", (_, index) => `translate(${legendX + index * (compact ? 80 : 90)}, ${legendY})`);
  item
    .append("rect")
    .attr("x", 0)
    .attr("y", -8)
    .attr("width", 10)
    .attr("height", 10)
    .attr("rx", 2)
    .attr("ry", 2)
    .attr("fill", (d) => colorByStatus[d.id].fill)
    .attr("stroke", (d) => colorByStatus[d.id].stroke)
    .attr("stroke-width", 1.2);
  item
    .append("text")
    .attr("x", 14)
    .attr("y", 0)
    .attr("class", "task-flow-legend-label")
    .attr("fill", "#475569")
    .text((d) => d.label);
}

function setFormBusy(isBusy) {
  input.disabled = isBusy;
  submitButton.disabled = isBusy;
  submitButton.textContent = isBusy ? "Обрабатывается..." : "Отправить";
}

function renderTable(data) {
  chartRoot.innerHTML = "";
  if (!data.length) {
    chartRoot.textContent = "Нет данных";
    return;
  }
  const table = document.createElement("table");
  const head = document.createElement("thead");
  const body = document.createElement("tbody");
  const columns = Object.keys(data[0]);

  const headerRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headerRow.appendChild(th);
  });
  head.appendChild(headerRow);

  data.forEach((row) => {
    const tr = document.createElement("tr");
    columns.forEach((col) => {
      const td = document.createElement("td");
      td.textContent = row[col];
      tr.appendChild(td);
    });
    body.appendChild(tr);
  });

  table.appendChild(head);
  table.appendChild(body);
  chartRoot.appendChild(table);
}

function renderBarChart(data) {
  chartRoot.innerHTML = "";
  const width = 600;
  const height = 300;
  const margin = { top: 20, right: 20, bottom: 40, left: 60 };
  const cols = Object.keys(data[0]);
  const xKey = cols[0];
  const yKey = cols[1];

  const svg = d3
    .select(chartRoot)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const x = d3
    .scaleBand()
    .domain(data.map((d) => String(d[xKey])))
    .range([margin.left, width - margin.right])
    .padding(0.2);

  const y = d3
    .scaleLinear()
    .domain([0, d3.max(data, (d) => Number(d[yKey]) || 0)])
    .nice()
    .range([height - margin.bottom, margin.top]);

  svg
    .append("g")
    .selectAll("rect")
    .data(data)
    .join("rect")
    .attr("x", (d) => x(String(d[xKey])))
    .attr("y", (d) => y(Number(d[yKey]) || 0))
    .attr("width", x.bandwidth())
    .attr("height", (d) => y(0) - y(Number(d[yKey]) || 0))
    .attr("fill", "#2563eb");

  svg
    .append("g")
    .attr("transform", `translate(0,${height - margin.bottom})`)
    .call(d3.axisBottom(x))
    .selectAll("text")
    .attr("transform", "rotate(-20)")
    .style("text-anchor", "end");

  svg.append("g").attr("transform", `translate(${margin.left},0)`).call(d3.axisLeft(y));
}

function renderResult(result) {
  sqlOutput.textContent = result.sql;
  if (!Array.isArray(result.data)) {
    chartRoot.textContent = "Некорректный ответ";
    return;
  }
  if (result.chart === "bar" && result.data.length > 0) {
    renderBarChart(result.data);
    return;
  }
  renderTable(result.data);
}

async function parseResponsePayload(response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return { error: text, raw: text };
}

async function pollJob(jobId, onUpdate) {
  const started = Date.now();
  let lastStatus = null;
  while (Date.now() - started < 900000) {
    const response = await fetch(`query/${jobId}`);
    const payload = await parseResponsePayload(response);
    if (!response.ok) {
      const message = typeof payload.error === "string" ? payload.error : `HTTP ${response.status}`;
      throw new Error(message);
    }
    if (payload.status === "done") {
      onUpdate(payload);
      return payload.result || {};
    }
    if (payload.status === "error") {
      onUpdate(payload);
      const tid = payload.trace_id ? ` [${payload.trace_id}]` : "";
      throw new Error(`${payload.error || "ошибка выполнения"}${tid}`);
    }
    lastStatus = payload;
    onUpdate(payload);
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  const timeoutError = new Error("сервер обрабатывает запрос слишком долго");
  timeoutError.name = "PollTimeout";
  timeoutError.lastStatus = lastStatus;
  throw timeoutError;
}

async function handleRequest(item) {
  item.state = "processing";
  item.stage = "queued";
  item.elapsedMs = 0;
  renderQueue();
  setFormBusy(true);
  activeJobId = null;
  taskMeta.textContent = "Постановка в очередь...";
  updateTaskStage("queued", "queued");
  sqlOutput.textContent = "Запрос обрабатывается...";
  chartRoot.textContent = "Ожидаем результат...";
  const startedAt = Date.now();
  let currentJobId = null;

  try {
    const response = await fetch("query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: item.question }),
    });
    const payload = await parseResponsePayload(response);
    if (!response.ok) {
      const tid = payload.trace_id ? ` [${payload.trace_id}]` : "";
      const message = typeof payload.error === "string" && payload.error.trim()
        ? payload.error
        : `HTTP ${response.status}`;
      addMessage("bot", `Ошибка: ${message}${tid}`);
      item.state = "error";
      item.stage = "error";
      taskMeta.textContent = "Ошибка постановки задачи";
      updateTaskStage("error", "error");
      sqlOutput.textContent = "Не удалось поставить задачу в очередь.";
      chartRoot.textContent = "Нет результата";
      return;
    }
    activeJobId = payload.job_id;
    currentJobId = payload.job_id;
    taskMeta.textContent = `job_id: ${activeJobId}`;
    const result = await pollJob(payload.job_id, (jobStatus) => {
      item.stage = jobStatus.stage || jobStatus.status;
      item.elapsedMs = Number(jobStatus.elapsed_ms || 0);
      taskMeta.textContent = formatTaskMeta(
        payload.job_id,
        item.stage,
        Number(jobStatus.queue_position),
        item.elapsedMs,
      );
      updateTaskStage(item.stage, jobStatus.status);
      renderQueue();
    });
    const latency = Number(result.latency_ms);
    addMessage("bot", Number.isFinite(latency) ? `Готово за ${latency} мс` : "Готово");
    renderResult(result);
    item.state = "done";
    item.stage = "done";
    updateTaskStage("done", "done");
  } catch (error) {
    if (error?.name === "PollTimeout") {
      const last = error.lastStatus || {};
      item.state = "queued";
      item.stage = last.stage || "queued";
      item.elapsedMs = Number(last.elapsed_ms || item.elapsedMs || 0);
      taskMeta.textContent = formatTaskMeta(
        currentJobId || activeJobId || "unknown",
        item.stage,
        Number(last.queue_position),
        item.elapsedMs,
      );
      updateTaskStage(item.stage, "queued");
      addMessage("bot", "Задача все еще в очереди/обработке. Backend продолжает работу.");
    } else {
      addMessage("bot", `Ошибка: ${error.message}`);
      item.state = "error";
      item.stage = "error";
      updateTaskStage("error", "error");
      sqlOutput.textContent = "Ошибка выполнения запроса";
      chartRoot.textContent = "Нет результата";
    }
  } finally {
    const elapsed = Date.now() - startedAt;
    if (elapsed < 700) {
      await new Promise((resolve) => setTimeout(resolve, 700 - elapsed));
    }
    setFormBusy(false);
    activeJobId = null;
    if (item.state === "done") {
      taskMeta.textContent = "Задача выполнена";
    } else if (item.state === "error") {
      taskMeta.textContent = "Задача завершилась ошибкой";
    } else if (item.state === "queued" || item.state === "processing") {
      taskMeta.textContent = "Задача еще в работе";
    }
    renderQueue();
  }
}

async function processQueue() {
  if (isProcessing) {
    return;
  }
  isProcessing = true;
  while (true) {
    const next = requestQueue.find((item) => item.state === "queued");
    if (!next) {
      break;
    }
    await handleRequest(next);
  }
  isProcessing = false;
  renderQueue();
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    return;
  }
  addMessage("user", question);
  input.value = "";
  requestQueue.push({ question, state: "queued" });
  renderQueue();
  processQueue();
});

function bootstrapQuestionFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const question = (params.get("question") || "").trim();
  if (!question) {
    return;
  }
  input.value = question;
  form.requestSubmit();
}

renderQueue();
renderTaskFlow("queued", "queued");
bootstrapQuestionFromUrl();

window.addEventListener("resize", () => {
  renderTaskFlow(currentTaskStage, currentTaskStatus);
});
