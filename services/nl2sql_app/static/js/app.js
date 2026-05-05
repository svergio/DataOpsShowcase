const form = document.getElementById("query-form");
const input = document.getElementById("question");
const messages = document.getElementById("messages");
const sqlOutput = document.getElementById("sql-output");
const chartRoot = document.getElementById("chart-root");

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

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = input.value.trim();
  if (!question) {
    return;
  }
  addMessage("user", question);
  input.value = "";
  try {
    const response = await fetch("/query", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();
    if (!response.ok) {
      const tid = payload.trace_id ? ` [${payload.trace_id}]` : "";
      addMessage("bot", `Ошибка: ${payload.error || "неизвестно"}${tid}`);
      return;
    }
    addMessage("bot", `Готово за ${payload.latency_ms} мс`);
    renderResult(payload);
  } catch (error) {
    addMessage("bot", `Ошибка сети: ${error.message}`);
  }
});
