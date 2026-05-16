const YEAR_MIN = 2025;
const YEAR_MAX = 2040;
const DEFAULT_YEAR = 2026;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const CHART_COLORS = ["#4F8EF7", "#7C5CFC", "#F59E0B", "#EF6B6B", "#10B981", "#6366F1"];

let activeClientId = parseInt(localStorage.getItem("activeClientId") || "0", 10);
let activeYear = parseInt(localStorage.getItem("activeYear") || String(DEFAULT_YEAR), 10);
let clientsList = [];

let meta = null;
let budget = null;

function getLang() {
  return localStorage.getItem("budget_lang") || "en";
}

function apiBase() {
  return `/api/clients/${activeClientId}/budget/${activeYear}`;
}

function lineLabel(line) {
  return getLang() === "de" ? line.label_de : line.label_en;
}

function sectionTitle(sec) {
  return getLang() === "de" ? sec.title_de : sec.title_en;
}
let selectedMonth = 8;
let donutChart = null;
let barChart = null;
let chartsDonut = null;
let drilldownChart = null;
let importPreview = null;
let selectedLineKey = null;

function formatEuro(n) {
  const loc = getLang() === "de" ? "de-DE" : "en-GB";
  return new Intl.NumberFormat(loc, { style: "currency", currency: "EUR" }).format(n ?? 0);
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function toast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 3000);
}

function openPanel(title, html, showConfirm = false) {
  document.getElementById("panel-title").textContent = title;
  document.getElementById("panel-body").innerHTML = html;
  document.getElementById("panel-confirm").style.display = showConfirm ? "block" : "none";
  document.getElementById("overlay").classList.add("open");
  document.getElementById("slide-panel").classList.add("open");
}

function closePanel() {
  document.getElementById("overlay").classList.remove("open");
  document.getElementById("slide-panel").classList.remove("open");
}

function fillMonthSelects() {
  ["dashboard-month", "charts-month", "bulk-from-month", "bulk-to-month"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = MONTHS.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("");
    el.value = String(selectedMonth);
  });
  const toM = document.getElementById("bulk-to-month");
  if (toM) toM.value = "12";
}

let activePlanTab = "income";
let saveEntryTimer = null;

function lineMonatlich(vals) {
  const summe = vals.reduce((a, b) => a + (Number(b) || 0), 0);
  if (budget?.settings?.monatlich_mode === "filled") {
    const filled = vals.filter((v) => v !== 0).length;
    return filled ? summe / filled : 0;
  }
  return summe / 12;
}

/** Refresh Summe/Monatlich cells and section totals in the Enter data grid. */
function updatePlanGridTotals() {
  const container = document.getElementById("plan-grids");
  if (!container || !budget) return;

  container.querySelectorAll("tr[data-key]").forEach((row) => {
    const key = row.dataset.key;
    const vals = budget.entries[key] || Array(12).fill(0);
    const summe = vals.reduce((a, b) => a + (Number(b) || 0), 0);
    const mon = lineMonatlich(vals);
    const computed = row.querySelectorAll("td.computed");
    if (computed.length >= 2) {
      computed[0].textContent = formatEuro(summe);
      computed[1].textContent = formatEuro(mon);
    }
  });

  container.querySelectorAll("tr.summary-row[data-summary-key]").forEach((row) => {
    const sk = row.dataset.summaryKey;
    const sm = budget.summary?.section_summaries?.[sk];
    if (!sm) return;
    const tds = row.querySelectorAll("td");
    for (let i = 1; i <= 12; i++) {
      if (tds[i]) tds[i].textContent = formatEuro(sm.months[i - 1]);
    }
    if (tds[13]) tds[13].textContent = formatEuro(sm.summe);
    if (tds[14]) tds[14].textContent = formatEuro(sm.monatlich);
  });
}

/** Recompute all visible totals after a cell or bulk save. */
async function refreshAfterDataChange() {
  if (!budget) return;
  renderSummary();
  updatePlanGridTotals();
  const active = document.querySelector("main > .panel.active")?.id;
  if (active === "panel-dashboard") await renderDashboard();
  else if (active === "panel-charts") await renderChartsPanel();
}

async function savePlanCell(inp) {
  const row = inp.closest("tr");
  if (!row?.dataset.key) return;
  const key = row.dataset.key;
  const month = parseInt(inp.dataset.month, 10);
  const amount = parseFloat(inp.value) || 0;
  try {
    const res = await api(`${apiBase()}/entry`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ line_key: key, month, amount }),
    });
    if (!budget.entries[key]) budget.entries[key] = Array(12).fill(0);
    budget.entries[key][month - 1] = amount;
    budget.summary = res.summary;
    await refreshAfterDataChange();
  } catch (e) {
    showError(e);
  }
}

function switchPanel(panelId) {
  const nav = document.getElementById("main-tabs");
  nav?.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.panel === panelId);
  });
  document.querySelectorAll("main > .panel").forEach((p) => p.classList.remove("active"));
  const panel = document.getElementById(`panel-${panelId}`);
  if (panel) panel.classList.add("active");

  if (panelId === "clients") {
    renderClientsPanel().catch((e) => showError(e));
    return;
  }
  if (!budget || !meta) return;
  if (panelId === "plan") renderPlanGrid(activePlanTab);
  else if (panelId === "charts") renderChartsPanel().catch((e) => showError(e));
  else if (panelId === "dashboard") renderDashboard().catch((e) => showError(e));
  else if (panelId === "summary") renderSummary();
}

function showError(err) {
  console.error(err);
  toast("Error: " + (err.message || "request failed"));
}

function initTabs() {
  const nav = document.getElementById("main-tabs");
  if (!nav) return;
  nav.querySelectorAll("button[data-panel]").forEach((btn) => {
    btn.addEventListener("click", () => switchPanel(btn.dataset.panel));
  });
}

function initPlanTabs() {
  const planTabs = document.getElementById("plan-tabs");
  if (!planTabs || !meta) return;
  const tabs = meta.tabs.filter((t) => !["dashboard", "summary", "charts"].includes(t.id));
  planTabs.innerHTML = tabs
    .map(
      (t, i) =>
        `<button type="button" data-tab="${t.id}" class="${t.id === activePlanTab || (i === 0 && !activePlanTab) ? "active" : ""}">${getLang() === "de" ? t.label_de : t.label_en}</button>`
    )
    .join("");
  planTabs.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      activePlanTab = btn.dataset.tab;
      planTabs.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      renderPlanGrid(activePlanTab);
    });
  });
  populateBulkLineSelect();
}

function populateBulkLineSelect() {
  const sel = document.getElementById("bulk-line-select");
  if (!sel || !meta) return;
  const opts = [];
  for (const sec of meta.sections) {
    for (const line of sec.lines) {
      opts.push(
        `<option value="${line.key}">${sectionTitle(sec)} — ${lineLabel(line)}</option>`
      );
    }
  }
  sel.innerHTML = opts.join("");
  if (!selectedLineKey && opts.length) selectedLineKey = sel.value;
  sel.value = selectedLineKey || sel.value;
  sel.onchange = () => {
    selectedLineKey = sel.value;
  };
}

async function ensureClient() {
  const data = await api("/api/clients");
  clientsList = data.clients || [];
  if (!clientsList.length) throw new Error("No clients in database");
  if (!clientsList.some((c) => c.id === activeClientId)) {
    activeClientId = clientsList[0].id;
    localStorage.setItem("activeClientId", String(activeClientId));
  }
  populateClientSelect();
}

function initYearSelect() {
  const sel = document.getElementById("year-select");
  if (!sel) return;
  let html = "";
  for (let y = YEAR_MIN; y <= YEAR_MAX; y++) {
    html += `<option value="${y}">${y}</option>`;
  }
  sel.innerHTML = html;
  if (activeYear < YEAR_MIN || activeYear > YEAR_MAX) {
    activeYear = DEFAULT_YEAR;
    localStorage.setItem("activeYear", String(activeYear));
  }
  sel.value = String(activeYear);
}

function populateClientSelect() {
  const sel = document.getElementById("client-select");
  if (!sel) return;
  if (!clientsList.length) {
    sel.innerHTML = `<option value="">—</option>`;
    return;
  }
  sel.innerHTML = clientsList
    .map(
      (c) =>
        `<option value="${c.id}" ${c.id === activeClientId ? "selected" : ""}>${escapeHtml(c.name)}</option>`
    )
    .join("");
}

async function loadBudget() {
  const loading = document.getElementById("plan-loading");
  if (loading) loading.hidden = false;
  try {
    await ensureClient();
    budget = await api(apiBase());
    budget.settings = budget.settings || { monatlich_mode: "div12" };
    meta = await api("/api/meta");
    fillMonthSelects();
    initPlanTabs();
    if (document.getElementById("panel-plan")?.classList.contains("active")) {
      renderPlanGrid(activePlanTab);
    }
    await refreshAfterDataChange();
  } finally {
    if (loading) loading.hidden = true;
  }
}

function getChartsData() {
  return api(`${apiBase()}/summary?month=${selectedMonth}`);
}

async function renderDashboard() {
  if (!budget) return;
  const { charts, summary } = await getChartsData();
  const period = document.getElementById("chart-period")?.value || "month";
  const h = charts.hero;
  const yr = charts.year;

  let rev, exp, diff;
  if (period === "year") {
    rev = yr.revenue;
    exp = yr.expenses;
    diff = yr.difference;
  } else {
    rev = h.revenue;
    exp = h.expenses;
    diff = h.difference;
  }

  document.getElementById("hero-balance").textContent = formatEuro(diff);
  document.getElementById("hero-balance").className = `hero-balance ${diff < 0 ? "deficit" : "surplus"}`;
  document.getElementById("hero-revenue").textContent = formatEuro(rev);
  document.getElementById("hero-expenses").textContent = formatEuro(exp);
  document.getElementById("hero-pill").innerHTML = diff < 0
    ? `<span class="pill deficit">${t("deficit")}</span>`
    : `<span class="pill surplus">${t("surplus")}</span>`;

  document.getElementById("kpi-row").innerHTML = `
    <div class="kpi-card income"><div class="label">Revenue</div><div class="value">${formatEuro(rev)}</div></div>
    <div class="kpi-card expense"><div class="label">Expenses</div><div class="value">${formatEuro(exp)}</div></div>
    <div class="kpi-card ${diff < 0 ? "deficit" : "surplus"}"><div class="label">Balance</div><div class="value">${formatEuro(diff)}</div></div>
    <div class="kpi-card"><div class="label">Year total (Diff)</div><div class="value">${formatEuro(summary.difference.summe)}</div></div>
  `;

  const t1 = summary.total_1.months[selectedMonth - 1];
  const t2 = summary.total_2.months[selectedMonth - 1];
  const t3 = summary.total_3.months[selectedMonth - 1];
  const t4 = summary.total_4.months[selectedMonth - 1];
  document.getElementById("section-cards").innerHTML = `
    <div class="kpi-card"><div class="label">Total - 1 Living</div><div class="value">${formatEuro(t1)}</div></div>
    <div class="kpi-card"><div class="label">Total - 2 Housing</div><div class="value">${formatEuro(t2)}</div></div>
    <div class="kpi-card"><div class="label">Total - 3 Insurance</div><div class="value">${formatEuro(t3)}</div></div>
    <div class="kpi-card"><div class="label">Total - 4 Savings/Loans</div><div class="value">${formatEuro(t4)}</div></div>
  `;

  renderDonut(charts.donut_sections, "donut-chart", "donut-legend", (id) => loadDrilldown(id));
  renderBarChart(charts.monthly_bars);
}

function renderDonut(slices, canvasId, legendId, onClick) {
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  if (donutChart && canvasId === "donut-chart") donutChart.destroy();
  if (chartsDonut && canvasId === "charts-donut") chartsDonut.destroy();

  const chart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: slices.map((s) => s.label_de || s.label),
      datasets: [{
        data: slices.map((s) => s.amount),
        backgroundColor: CHART_COLORS,
        borderWidth: 2,
        borderColor: "#fff",
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "65%",
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (c) => `${c.label}: ${formatEuro(c.raw)} (${slices[c.dataIndex]?.pct ?? 0}%)`,
          },
        },
      },
      onClick: (_, els) => {
        if (els.length && onClick) onClick(slices[els[0].index].id);
      },
    },
  });

  if (canvasId === "donut-chart") donutChart = chart;
  else chartsDonut = chart;

  const leg = document.getElementById(legendId);
  if (leg) {
    leg.innerHTML = slices
      .map(
        (s, i) =>
          `<li data-id="${s.id}"><span class="dot" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></span>${s.label_de || s.label} · ${formatEuro(s.amount)} (${s.pct}%)</li>`
      )
      .join("");
    leg.querySelectorAll("li").forEach((li, i) => {
      li.addEventListener("click", () => onClick && onClick(slices[i].id));
    });
  }
}

function renderBarChart(bars) {
  const ctx = document.getElementById("bar-chart");
  if (!ctx) return;
  if (barChart) barChart.destroy();
  barChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: MONTHS,
      datasets: [
        { label: "Revenue", data: bars.map((b) => b.revenue), backgroundColor: "#059669" },
        { label: "Expenses", data: bars.map((b) => b.expenses), backgroundColor: "#ea580c" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: { y: { beginAtZero: true } },
    },
  });
}

async function loadDrilldown(sectionId) {
  const data = await api(`${apiBase()}/drilldown?section=${sectionId}&month=${selectedMonth}`);
  const card = document.getElementById("drilldown-card");
  if (!data.slices.length) {
    toast("No expenses in this section for selected month");
    return;
  }
  card.style.display = "block";
  document.getElementById("drilldown-title").textContent = `Drill-down: ${sectionId}`;
  if (drilldownChart) drilldownChart.destroy();
  drilldownChart = new Chart(document.getElementById("drilldown-chart"), {
    type: "doughnut",
    data: {
      labels: data.slices.map((s) => s.label),
      datasets: [{ data: data.slices.map((s) => s.amount), backgroundColor: CHART_COLORS }],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

async function renderChartsPanel() {
  if (!budget || !meta) return;
  const { charts } = await getChartsData();
  renderDonut(charts.donut_sections, "charts-donut", null, loadDrilldown);
  const allLines = [];
  for (const sec of meta.sections) {
    if (["income", "self_employed_a", "self_employed_b", "net_a", "net_b", "other_income_a", "other_income_b"].some((x) => sec.id.startsWith(x) || sec.id === x)) continue;
    for (const line of sec.lines) {
      const vals = budget.entries[line.key] || [];
      const amt = vals[selectedMonth - 1] || 0;
      if (amt > 0) allLines.push({ label: lineLabel(line), amount: amt });
    }
  }
  allLines.sort((a, b) => b.amount - a.amount);
  document.getElementById("top-expenses").innerHTML = allLines
    .slice(0, 10)
    .map((l) => {
      const max = allLines[0].amount || 1;
      const w = Math.round((100 * l.amount) / max);
      return `<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:0.9rem"><span>${l.label}</span><span>${formatEuro(l.amount)}</span></div><div style="height:8px;background:#e2e8f0;border-radius:4px"><div style="width:${w}%;height:100%;background:var(--primary);border-radius:4px"></div></div>`;
    })
    .join("");
}

function renderSummary() {
  if (!budget?.summary) return;
  const s = budget.summary;
  const rows = [
    ["Total revenue", s.total_revenue],
    ["Total - 1 Living", s.total_1],
    ["Total - 2 Housing", s.total_2],
    ["Total - 3 Insurance", s.total_3],
    ["Total - 4 Savings/Loans", s.total_4],
    ["Total - 5 Expenses", s.total_5],
    ["Total expenses", s.total_expenses],
    ["Difference", s.difference],
  ];
  let html = "<thead><tr><th>Row</th>" + MONTHS.map((m) => `<th>${m}</th>`).join("") + "<th>Summe</th><th>Monatlich</th></tr></thead><tbody>";
  for (const [label, data] of rows) {
    const isDiff = label === "Difference";
    const cls = isDiff ? `difference ${data.summe < 0 ? "deficit" : "surplus"} highlight` : "";
    html += `<tr class="${cls}"><td>${label}</td>`;
    for (let i = 0; i < 12; i++) html += `<td>${formatEuro(data.months[i])}</td>`;
    html += `<td>${formatEuro(data.summe)}</td><td>${formatEuro(data.monatlich)}</td></tr>`;
  }
  html += "</tbody>";
  document.getElementById("summary-table").innerHTML = html;
}

function renderPlanGrid(tabId) {
  const container = document.getElementById("plan-grids");
  if (!container) return;
  if (!meta || !budget) {
    container.innerHTML = "<p class='hint-banner'>Could not load budget. Refresh the page or check the server.</p>";
    return;
  }
  const sections = meta.sections.filter((s) => s.tab === tabId);
  let html = "";
  for (const sec of sections) {
    html += `<div class="grid-wrap" style="margin-bottom:24px"><table class="budget-grid"><caption style="caption-side:top;text-align:left;padding:12px;font-weight:700">${sectionTitle(sec)}</caption><thead><tr><th>${t("category")}</th>${MONTHS.map((m) => `<th>${m}</th>`).join("")}<th>Summe</th><th>Monatlich</th></tr></thead><tbody>`;
    for (const line of sec.lines) {
      const vals = budget.entries[line.key] || Array(12).fill(0);
      const summe = vals.reduce((a, b) => a + b, 0);
      const mon = budget.settings?.monatlich_mode === "filled"
        ? (vals.filter((v) => v !== 0).length ? summe / vals.filter((v) => v !== 0).length : 0)
        : summe / 12;
      html += `<tr data-key="${line.key}"><td><span>${line.label_de}</span><span class="sub-label">${line.label_en}</span></td>`;
      for (let m = 1; m <= 12; m++) {
        html += `<td><input type="number" step="0.01" data-month="${m}" value="${vals[m - 1] || ""}" /></td>`;
      }
      html += `<td class="computed">${formatEuro(summe)}</td><td class="computed">${formatEuro(mon)}</td></tr>`;
    }
    const sk = sec.summary_key;
    if (sk && budget.summary.section_summaries?.[sk]) {
      const sm = budget.summary.section_summaries[sk];
      html += `<tr class="summary-row" data-summary-key="${sk}"><td>${sec.summary_key}</td>`;
      for (let i = 0; i < 12; i++) html += `<td class="computed">${formatEuro(sm.months[i])}</td>`;
      html += `<td class="computed">${formatEuro(sm.summe)}</td><td class="computed">${formatEuro(sm.monatlich)}</td></tr>`;
    }
    html += "</tbody></table></div>";
  }
  container.innerHTML = html;

  container.querySelectorAll("tr[data-key]").forEach((row) => {
    row.addEventListener("click", () => {
      selectedLineKey = row.dataset.key;
      const sel = document.getElementById("bulk-line-select");
      if (sel) sel.value = selectedLineKey;
    });
  });

  container.querySelectorAll("input[type='number']").forEach((inp) => {
    inp.addEventListener("change", () => {
      clearTimeout(saveEntryTimer);
      savePlanCell(inp);
    });
    inp.addEventListener("input", () => {
      const row = inp.closest("tr");
      if (row?.dataset.key) {
        const key = row.dataset.key;
        const month = parseInt(inp.dataset.month, 10);
        const amount = parseFloat(inp.value) || 0;
        if (!budget.entries[key]) budget.entries[key] = Array(12).fill(0);
        budget.entries[key][month - 1] = amount;
        updatePlanGridTotals();
      }
      clearTimeout(saveEntryTimer);
      saveEntryTimer = setTimeout(() => savePlanCell(inp), 600);
    });
    inp.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        clearTimeout(saveEntryTimer);
        savePlanCell(inp);
        inp.blur();
      }
    });
  });
}

async function applyBulk(startMonth, endMonth) {
  const sel = document.getElementById("bulk-line-select");
  const lineKey = sel?.value || selectedLineKey;
  if (!lineKey) {
    toast("Choose a category");
    return;
  }
  const amount = parseFloat(document.getElementById("bulk-amount").value);
  const start = startMonth ?? parseInt(document.getElementById("bulk-from-month").value, 10);
  const end = endMonth ?? parseInt(document.getElementById("bulk-to-month").value, 10);
  if (isNaN(amount)) {
    toast("Enter an amount");
    return;
  }
  const res = await api(`${apiBase()}/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ line_key: lineKey, amount, start_month: start, end_month: end }),
  });
  if (!budget.entries[lineKey]) budget.entries[lineKey] = Array(12).fill(0);
  for (let m = start; m <= end; m++) budget.entries[lineKey][m - 1] = amount;
  budget.summary = res.summary;
  renderPlanGrid(activePlanTab);
  await refreshAfterDataChange();
  toast(`${t("saved")}: ${formatEuro(amount)} (${start}–${end})`);
}

document.getElementById("btn-bulk-apply")?.addEventListener("click", () => applyBulk());

document.getElementById("btn-apply-all-year")?.addEventListener("click", () => applyBulk(1, 12));

document.getElementById("dashboard-month")?.addEventListener("change", (e) => {
  selectedMonth = parseInt(e.target.value, 10);
  renderDashboard();
});
document.getElementById("charts-month")?.addEventListener("change", (e) => {
  selectedMonth = parseInt(e.target.value, 10);
  renderChartsPanel();
});
document.getElementById("chart-period")?.addEventListener("change", renderDashboard);

document.getElementById("btn-automation")?.addEventListener("click", () => {
  document.getElementById("automation-dropdown").classList.toggle("open");
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#automation-dropdown")) {
    document.getElementById("automation-dropdown")?.classList.remove("open");
  }
});

document.getElementById("automation-menu")?.addEventListener("click", async (e) => {
  const action = e.target.dataset?.action;
  if (!action) return;
  document.getElementById("automation-dropdown").classList.remove("open");

  if (action === "import-excel" || action === "import-csv") {
    document.getElementById("file-input").dataset.type = action === "import-csv" ? "csv" : "excel";
    document.getElementById("file-input").click();
  } else if (action === "export-excel") {
    window.location.href = `/api/clients/${activeClientId}/export/excel?year=${activeYear}`;
  } else if (action === "recalculate") {
    await loadBudget();
    toast("Totals recalculated");
  } else if (action === "import-log") {
    const log = await api("/api/import/log");
    openPanel("Import log", `<pre>${log.log.join("\n") || "No imports yet"}</pre>`);
  } else if (action === "map-categories") {
    showMappingPanel();
  }
});

document.getElementById("file-input")?.addEventListener("change", async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const type = e.target.dataset.type || "excel";
  const fd = new FormData();
  fd.append("file", file);
  const endpoint = type === "csv"
    ? `/api/clients/${activeClientId}/import/csv?year=${activeYear}`
    : `/api/clients/${activeClientId}/import/excel?year=${activeYear}`;
  const res = await fetch(endpoint, { method: "POST", body: fd });
  const data = await res.json();
  importPreview = data.preview;
  let html = `<p>${data.count} rows. ${data.warnings?.length ? data.warnings.join("<br>") : ""}</p><ul>`;
  data.preview.slice(0, 20).forEach((r) => {
    html += `<li>${r.status}: ${r.label}</li>`;
  });
  html += "</ul>";
  openPanel("Import preview", html, true);
  document.getElementById("panel-confirm").onclick = async () => {
    await api(`/api/clients/${activeClientId}/import/confirm?year=${activeYear}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows: importPreview.filter((r) => r.line_key) }),
    });
    closePanel();
    await loadBudget();
    toast("Import complete");
  };
  e.target.value = "";
});

async function showMappingPanel() {
  const { categories } = await api("/api/meta");
  const { mappings } = await api("/api/mappings");
  let html = "";
  Object.entries(mappings).forEach(([label, key]) => {
    html += mappingRowHtml(label, key, categories);
  });
  html += mappingRowHtml("", "", categories);
  openPanel("Map categories", html + '<button class="btn btn-ghost" id="add-map">Add row</button>');
  document.getElementById("add-map")?.addEventListener("click", () => {
    document.getElementById("panel-body").insertAdjacentHTML("beforeend", mappingRowHtml("", "", categories));
  });
  document.getElementById("panel-body").addEventListener("change", async (ev) => {
    if (ev.target.classList.contains("map-key")) {
      const label = ev.target.closest(".mapping-row").querySelector(".map-label").value;
      if (label) {
        await api("/api/mappings", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_label: label, line_key: ev.target.value }),
        });
        toast("Mapping saved");
      }
    }
  });
}

function mappingRowHtml(label, key, categories) {
  const opts = categories.map((c) => `<option value="${c.key}" ${c.key === key ? "selected" : ""}>${c.label}</option>`).join("");
  return `<div class="mapping-row"><input class="map-label" placeholder="Excel label" value="${label}" /><select class="map-key"><option value="">—</option>${opts}</select></div>`;
}

document.getElementById("btn-settings")?.addEventListener("click", () => {
  const mode = budget?.settings?.monatlich_mode || "div12";
  openPanel(
    "Settings",
    `<div class="settings-group"><label>Monatlich calculation</label>
    <select id="set-monatlich"><option value="div12" ${mode === "div12" ? "selected" : ""}>Summe / 12</option>
    <option value="filled" ${mode === "filled" ? "selected" : ""}>Average of filled months</option></select></div>`
  );
  document.getElementById("panel-confirm").style.display = "block";
  document.getElementById("panel-confirm").onclick = async () => {
    const m = document.getElementById("set-monatlich").value;
    await api(`${apiBase()}/settings`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ monatlich_mode: m }),
    });
    closePanel();
    await loadBudget();
    toast("Settings saved");
  };
});

document.getElementById("panel-cancel")?.addEventListener("click", closePanel);
document.getElementById("overlay")?.addEventListener("click", closePanel);

async function renderClientsPanel() {
  const data = await api("/api/clients");
  clientsList = data.clients || [];
  const list = document.getElementById("client-list");
  const hint = document.getElementById("clients-hint");
  if (!list) return;
  if (!clientsList.length) {
    list.innerHTML = "";
    if (hint) hint.hidden = false;
    return;
  }
  if (hint) hint.hidden = true;
  list.innerHTML = clientsList
    .map((c) => {
      const addr = [c.street, c.postal_code, c.city].filter(Boolean).join(", ");
      const sub = [c.company_name, addr, c.email].filter(Boolean).join(" · ");
      return `
    <li class="client-item ${c.id === activeClientId ? "active" : ""}">
      <div>
        <span class="client-name">${escapeHtml(c.name)}</span>
        ${sub ? `<div class="client-meta">${escapeHtml(sub)}</div>` : ""}
      </div>
      <span class="client-actions">
        <button type="button" class="btn btn-ghost btn-sm" data-edit="${c.id}">${t("editClient")}</button>
        <button type="button" class="btn btn-primary btn-sm" data-open="${c.id}">${t("openClient")}</button>
        <button type="button" class="btn btn-ghost btn-sm" data-delete="${c.id}">${t("deleteClient")}</button>
      </span>
    </li>`;
    })
    .join("");
  list.querySelectorAll("[data-edit]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const c = clientsList.find((x) => x.id === parseInt(btn.dataset.edit, 10));
      if (c) fillClientForm(c);
    });
  });
  list.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      activeClientId = parseInt(btn.dataset.open, 10);
      localStorage.setItem("activeClientId", String(activeClientId));
      populateClientSelect();
      await loadBudget();
      switchPanel("dashboard");
      toast(t("saved"));
    });
  });
  list.querySelectorAll("[data-delete]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm(t("confirmDelete"))) return;
      await api(`/api/clients/${btn.dataset.delete}`, { method: "DELETE" });
      if (activeClientId === parseInt(btn.dataset.delete, 10)) {
        activeClientId = 0;
        localStorage.removeItem("activeClientId");
      }
      await renderClientsPanel();
      await loadBudget().catch(() => {});
    });
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function initLanguage() {
  const lang = getLang();
  document.documentElement.lang = lang;
  document.querySelectorAll(".lang-btn").forEach((b) => {
    b.classList.toggle("active", b.dataset.lang === lang);
    if (b.dataset.bound) return;
    b.dataset.bound = "1";
    b.addEventListener("click", async () => {
      setLanguage(b.dataset.lang);
      document.querySelectorAll(".lang-btn").forEach((x) =>
        x.classList.toggle("active", x.dataset.lang === b.dataset.lang)
      );
      if (meta) initPlanTabs();
      if (budget) {
        renderSummary();
        const panel = document.querySelector("main > .panel.active")?.id;
        if (panel === "panel-dashboard") await renderDashboard();
        if (panel === "panel-plan") renderPlanGrid(activePlanTab);
      }
    });
  });
  applyTranslations();
}

function setAppStatus(msg, isError) {
  let el = document.getElementById("app-status");
  if (!el) {
    el = document.createElement("p");
    el.id = "app-status";
    el.className = "hint-banner";
    document.getElementById("main-tabs")?.after(el);
  }
  el.textContent = msg;
  el.className = isError ? "hint-banner error" : "hint-banner";
  el.hidden = !msg;
}

function readClientForm() {
  const form = document.getElementById("client-form");
  const fd = new FormData(form);
  return {
    name: (fd.get("name") || "").trim(),
    company_name: (fd.get("company_name") || "").trim(),
    contact_person: (fd.get("contact_person") || "").trim(),
    email: (fd.get("email") || "").trim(),
    phone: (fd.get("phone") || "").trim(),
    street: (fd.get("street") || "").trim(),
    postal_code: (fd.get("postal_code") || "").trim(),
    city: (fd.get("city") || "").trim(),
    country: (fd.get("country") || "Germany").trim(),
    tax_id: (fd.get("tax_id") || "").trim(),
    vat_id: (fd.get("vat_id") || "").trim(),
    iban: (fd.get("iban") || "").trim(),
    notes: (fd.get("notes") || "").trim(),
  };
}

function fillClientForm(c) {
  const form = document.getElementById("client-form");
  if (!form) return;
  const fields = [
    "name", "company_name", "contact_person", "email", "phone",
    "street", "postal_code", "city", "country", "tax_id", "vat_id", "iban", "notes",
  ];
  fields.forEach((f) => {
    const el = form.elements[f];
    if (el) el.value = c[f] || "";
  });
  document.getElementById("client-edit-id").value = String(c.id);
  document.getElementById("client-form-title").textContent = t("editClientTitle");
  document.getElementById("btn-cancel-edit").hidden = false;
  form.scrollIntoView({ behavior: "smooth", block: "start" });
}

function resetClientForm() {
  const form = document.getElementById("client-form");
  if (!form) return;
  form.reset();
  const country = form.elements.country;
  if (country) country.value = "Germany";
  document.getElementById("client-edit-id").value = "";
  document.getElementById("client-form-title").textContent = t("newClient");
  document.getElementById("btn-cancel-edit").hidden = true;
}

document.getElementById("client-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = readClientForm();
  if (!payload.name) {
    toast(t("clientName"));
    return;
  }
  const editId = document.getElementById("client-edit-id").value;
  try {
    let res;
    if (editId) {
      res = await api(`/api/clients/${editId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
    } else {
      res = await api("/api/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      activeClientId = res.client.id;
      localStorage.setItem("activeClientId", String(activeClientId));
    }
    resetClientForm();
    await renderClientsPanel();
    populateClientSelect();
    if (!editId) await loadBudget();
    toast(t("saved"));
  } catch (err) {
    showError(err);
  }
});

document.getElementById("btn-cancel-edit")?.addEventListener("click", resetClientForm);

document.getElementById("year-select")?.addEventListener("change", async (e) => {
  activeYear = parseInt(e.target.value, 10);
  localStorage.setItem("activeYear", String(activeYear));
  await loadBudget();
});

document.getElementById("client-select")?.addEventListener("change", async (e) => {
  const id = parseInt(e.target.value, 10);
  if (!id) return;
  activeClientId = id;
  localStorage.setItem("activeClientId", String(activeClientId));
  await loadBudget();
});

function boot() {
  fillMonthSelects();
  initYearSelect();
  initTabs();
  initLanguage();
  setAppStatus(t("loading"), false);
  loadBudget()
    .then(() => setAppStatus("", false))
    .catch((err) => {
      console.error(err);
      setAppStatus(
        "Cannot load data. Run: python -m uvicorn app.main:app --host 127.0.0.1 --port 8765",
        true
      );
      const g = document.getElementById("plan-grids");
      if (g) g.innerHTML = "<p class='hint-banner error'>Server not reachable. See message above.</p>";
      toast("Failed to load — start the server and refresh (Ctrl+F5)");
    });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
