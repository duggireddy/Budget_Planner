const YEAR_MIN = 2025;
const YEAR_MAX = 2040;
const DEFAULT_YEAR = 2026;
const CHART_COLORS = ["#4F8EF7", "#7C5CFC", "#F59E0B", "#EF6B6B", "#10B981", "#6366F1"];

let activeClientId = parseInt(localStorage.getItem("activeClientId") || "0", 10);
let activeYear = parseInt(localStorage.getItem("activeYear") || String(DEFAULT_YEAR), 10);
let clientsList = [];

let meta = null;
let budget = null;
let chartsCache = null;
let chartsCacheKey = "";
let balanceSheetStale = true;
let clientsCacheTime = 0;
const CLIENTS_CACHE_MS = 30000;
const balanceSaveTimers = new Map();
const debtRowSaveState = new Map();
let balanceAssetsAbort = null;

function isEditingDebtTable() {
  return !!document.querySelector("#debts-table input:focus");
}

/** Parse number from input (supports 5.5 and 5,5). */
function parseNumInput(val) {
  if (val == null || val === "") return 0;
  const s = String(val).trim().replace(/\s/g, "").replace(",", ".");
  const n = parseFloat(s);
  return Number.isFinite(n) ? n : 0;
}

function getActiveClientId() {
  const sel = document.getElementById("client-select");
  const fromSel = sel ? parseInt(sel.value, 10) : 0;
  if (fromSel > 0) {
    activeClientId = fromSel;
    localStorage.setItem("activeClientId", String(activeClientId));
    return activeClientId;
  }
  if (activeClientId > 0) return activeClientId;
  return 0;
}

function getActiveYear() {
  const sel = document.getElementById("year-select");
  const y = sel ? parseInt(sel.value, 10) : activeYear;
  if (y >= YEAR_MIN && y <= YEAR_MAX) {
    activeYear = y;
    localStorage.setItem("activeYear", String(activeYear));
    return activeYear;
  }
  return activeYear;
}

function apiBase() {
  return `/api/clients/${getActiveClientId()}/budget/${getActiveYear()}`;
}

function requireClient() {
  const cid = getActiveClientId();
  if (!cid) {
    throw new Error(t("selectClient"));
  }
  return cid;
}

async function postCustomLine(payload) {
  const cid = requireClient();
  const year = getActiveYear();
  const body = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  try {
    return await api(`${apiBase()}/custom-lines`, body);
  } catch (e) {
    if (!String(e.message || "").includes("Not found")) throw e;
    return await api(`/api/clients/${cid}/custom-lines?year=${year}`, body);
  }
}

async function postAsset(payload) {
  const cid = requireClient();
  const year = getActiveYear();
  const opts = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const urls = [
    `/api/clients/${cid}/assets?year=${year}`,
    `/api/clients/${cid}/assets`,
  ];
  let lastErr;
  for (const url of urls) {
    try {
      return await api(url, opts);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("Could not save asset");
}

async function postDebt(payload) {
  const cid = requireClient();
  const year = getActiveYear();
  const opts = {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  };
  const urls = [
    `/api/clients/${cid}/debts?year=${year}`,
    `/api/clients/${cid}/debts`,
  ];
  let lastErr;
  for (const url of urls) {
    try {
      return await api(url, opts);
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr || new Error("Could not save debt");
}

function markBalanceStale() {
  balanceSheetStale = true;
}

function invalidateChartsCache() {
  chartsCache = null;
  chartsCacheKey = "";
}

function activePanelId() {
  return document.querySelector("main > .panel.active")?.id || "";
}

function emptyBalanceSheet() {
  return {
    assets: [],
    debts: [],
    total_assets: 0,
    total_debts: 0,
    net_worth: 0,
    payoff: null,
    future_invest_plan: {
      items: [],
      total_current: 0,
      total_target: 0,
      total_monthly_contribution: 0,
      overall_progress_pct: null,
    },
  };
}

async function applyBalanceSheetResponse(res, options = {}) {
  if (!budget) {
    await loadBudget();
  }
  if (res?.balance_sheet) {
    budget.balance_sheet = res.balance_sheet;
    balanceSheetStale = false;
  } else {
    markBalanceStale();
  }
  if (res?.debt) mergeDebtIntoBalanceSheet(res.debt);
  if (activePanelId() === "panel-balance") {
    const bs = budget.balance_sheet || emptyBalanceSheet();
    const hasDebtRows = !!document.querySelector("#debts-table tr[data-debt-id]");
    if (options.forceFull || !hasDebtRows || !options.softDebts) {
      paintBalancePanel(bs);
    } else {
      if (res?.debt) patchDebtRowFromServer(res.debt);
      patchDebtBalanceUI(bs);
    }
  }
  if (activePanelId() === "panel-future" || options.forceFuture) {
    paintFuturePanel(budget.balance_sheet || emptyBalanceSheet());
  }
  if (activePanelId() === "panel-dashboard") {
    invalidateChartsCache();
    await renderDashboard();
  }
}

async function submitAsset(name, amount) {
  const n = String(name || "").trim();
  if (!n) throw new Error(t("nameRequired"));
  const res = await postAsset({
    name: n,
    asset_type: "other",
    amount: parseNumInput(amount),
    notes: "",
  });
  await applyBalanceSheetResponse(res);
  toast(t("saved"));
}

async function submitDebt(name, amount, interestRate, monthlyPayment) {
  const n = String(name || "").trim();
  if (!n) throw new Error(t("nameRequired"));
  const res = await postDebt({
    name: n,
    amount: parseNumInput(amount),
    interest_rate_annual: parseNumInput(interestRate),
    monthly_payment: parseNumInput(monthlyPayment),
    notes: "",
  });
  await applyBalanceSheetResponse(res);
  toast(t("saved"));
}

function getFuturePlan(bs) {
  return (
    bs?.future_invest_plan || {
      items: [],
      total_current: 0,
      total_target: 0,
      total_monthly_contribution: 0,
      overall_progress_pct: null,
    }
  );
}

function initBalanceForms() {
  const formAsset = document.getElementById("form-inline-asset");
  const formDebt = document.getElementById("form-inline-debt");
  if (formAsset && !formAsset.dataset.bound) {
    formAsset.dataset.bound = "1";
    formAsset.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await submitAsset(
          document.getElementById("inline-asset-name").value,
          document.getElementById("inline-asset-amount").value
        );
        formAsset.reset();
        document.getElementById("inline-asset-name")?.focus();
      } catch (err) {
        showError(err);
      }
    });
  }
  if (formDebt && !formDebt.dataset.bound) {
    formDebt.dataset.bound = "1";
    formDebt.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await submitDebt(
          document.getElementById("inline-debt-name").value,
          document.getElementById("inline-debt-amount").value,
          document.getElementById("inline-debt-rate").value,
          document.getElementById("inline-debt-payment").value
        );
        formDebt.reset();
        const rateEl = document.getElementById("inline-debt-rate");
        if (rateEl) rateEl.value = "";
        document.getElementById("inline-debt-name")?.focus();
      } catch (err) {
        showError(err);
      }
    });
  }
  initFutureInvestPanel();
}

function readInlineFuturePayload() {
  const yearRaw = document.getElementById("inline-future-year")?.value?.trim() ?? "";
  let target_year = null;
  if (yearRaw) {
    const y = parseInt(yearRaw, 10);
    if (!Number.isFinite(y) || y < 2020 || y > 2100) {
      throw new Error(t("targetYearInvalid"));
    }
    target_year = y;
  }
  const name = document.getElementById("inline-future-name")?.value?.trim() ?? "";
  if (!name) throw new Error(t("nameRequired"));
  return {
    name,
    investment_type: "other",
    current_amount: parseNumInput(document.getElementById("inline-future-current")?.value),
    target_amount: parseNumInput(document.getElementById("inline-future-target")?.value),
    monthly_contribution: parseNumInput(document.getElementById("inline-future-monthly")?.value),
    expected_return_annual: parseNumInput(document.getElementById("inline-future-return")?.value),
    target_year,
    notes: "",
  };
}

async function submitFutureInvestment() {
  const cid = requireClient();
  const payload = readInlineFuturePayload();
  const btn = document.getElementById("btn-add-future");
  if (btn) btn.disabled = true;
  try {
    const res = await api(
      `/api/clients/${cid}/future-investments?year=${getActiveYear()}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    if (!budget) await loadBudget();
    if (res?.balance_sheet) {
      budget.balance_sheet = res.balance_sheet;
      balanceSheetStale = false;
    }
    await applyBalanceSheetResponse(res, { forceFuture: true });
    paintFuturePanel(budget.balance_sheet || emptyBalanceSheet());
    document.getElementById("form-inline-future")?.reset();
    document.getElementById("inline-future-name")?.focus();
    toast(t("saved"));
  } finally {
    if (btn) btn.disabled = false;
  }
}

function initFutureInvestPanel() {
  const panel = document.getElementById("panel-future");
  if (!panel || panel.dataset.futurePanelBound === "1") return;
  panel.dataset.futurePanelBound = "1";
  panel.addEventListener("submit", async (e) => {
    if (e.target?.id !== "form-inline-future") return;
    e.preventDefault();
    try {
      await submitFutureInvestment();
    } catch (err) {
      showError(err);
    }
  });
  document.getElementById("btn-add-future")?.addEventListener("click", (e) => {
    const form = document.getElementById("form-inline-future");
    if (!form) return;
    if (e.target?.type === "submit") return;
    e.preventDefault();
    if (typeof form.requestSubmit === "function") form.requestSubmit();
    else form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
  });
}

function initHeaderClientsButton() {
  const btn = document.getElementById("btn-header-clients");
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", () => openClientsPanel());
}

function openClientsPanel() {
  document.getElementById("main-tabs")?.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
  document.querySelectorAll("main > .panel").forEach((p) => p.classList.remove("active"));
  document.getElementById("panel-clients")?.classList.add("active");
  scrollActivePanelToTop();
  renderClientsPanel().catch((e) => showError(e));
}

async function deleteCustomLine(lineKey) {
  const cid = requireClient();
  const year = getActiveYear();
  try {
    return await api(`${apiBase()}/custom-lines/${encodeURIComponent(lineKey)}`, { method: "DELETE" });
  } catch (e) {
    if (!String(e.message || "").includes("Not found")) throw e;
    return await api(
      `/api/clients/${cid}/budget/${year}/custom-lines/${encodeURIComponent(lineKey)}`,
      { method: "DELETE" }
    );
  }
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
let chartsItemsPie = null;
const donutChartByCanvas = {};
let drilldownChart = null;

const INCOME_SECTION_IDS = new Set([
  "income",
  "self_employed_a",
  "self_employed_b",
  "net_a",
  "net_b",
  "other_income_a",
  "other_income_b",
]);

/** Summary row key → sections included in that total (for expand / filled breakdown). */
const SUMMARY_EXPAND_CONFIG = {
  sumTotalRevenue: {
    sections: ["self_employed_a", "self_employed_b", "net_a", "net_b", "other_income_a", "other_income_b"],
    lineType: "income",
  },
  sumLiving: { sections: ["living"], lineType: "expense" },
  sumHousing: { sections: ["housing"], lineType: "expense" },
  sumInsurance: { sections: ["health_a", "health_b", "property_insurance"], lineType: "expense" },
  sumSavingsLoans: { sections: ["pension", "wealth", "credit"], lineType: "expense" },
  sumChildren: { sections: ["child_1", "child_2"], lineType: "expense" },
  sumExpenses5: {
    sections: [
      "living",
      "housing",
      "baufinanzierung",
      "health_a",
      "health_b",
      "property_insurance",
      "pension",
      "wealth",
      "credit",
      "child_1",
      "child_2",
    ],
    lineType: "expense",
  },
  sumTotalExpenses: {
    sections: [
      "living",
      "housing",
      "baufinanzierung",
      "health_a",
      "health_b",
      "property_insurance",
      "pension",
      "wealth",
      "credit",
      "child_1",
      "child_2",
    ],
    lineType: "expense",
  },
};
let selectedLineKey = null;

const FETCH_OPTS = { credentials: "same-origin" };
let appBooted = false;

function showLoginGate() {
  document.body.classList.add("login-locked");
  const gate = document.getElementById("login-gate");
  if (gate) gate.hidden = false;
  appBooted = false;
}

function hideLoginGate() {
  document.body.classList.remove("login-locked");
  const gate = document.getElementById("login-gate");
  if (gate) gate.hidden = true;
}

function setProfileUsername(name) {
  const userEl = document.getElementById("profile-username");
  const label = document.getElementById("profile-label");
  if (userEl) userEl.textContent = name || "";
  if (label && name) label.textContent = name;
}

function initAuthUI() {
  document.getElementById("login-form")?.addEventListener("submit", submitLogin);
  document.getElementById("btn-profile")?.addEventListener("click", (e) => {
    e.stopPropagation();
    document.getElementById("profile-dropdown")?.classList.toggle("open");
  });
  document.getElementById("profile-menu")?.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    document.getElementById("profile-dropdown")?.classList.remove("open");
    const action = btn.dataset.action;
    if (action === "logout") doLogout();
    else if (action === "monthly-mode") openMonthlyModePanel();
    else if (action === "change-password") openChangePasswordPanel();
  });
}

async function checkAuthOnLoad() {
  try {
    const res = await fetch("/api/auth/status", FETCH_OPTS);
    if (!res.ok) return false;
    const d = await res.json();
    if (d.authenticated) {
      hideLoginGate();
      setProfileUsername(d.username);
      return true;
    }
  } catch (_) {
    /* offline */
  }
  showLoginGate();
  return false;
}

async function submitLogin(e) {
  e.preventDefault();
  const username = document.getElementById("login-username")?.value?.trim() || "";
  const password = document.getElementById("login-password")?.value || "";
  const errEl = document.getElementById("login-error");
  if (errEl) errEl.hidden = true;
  try {
    const res = await fetch("/api/auth/login", {
      ...FETCH_OPTS,
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) {
      let msg = "Invalid username or password";
      try {
        const j = await res.json();
        if (typeof j.detail === "string") msg = j.detail;
      } catch (_) {
        /* ignore */
      }
      throw new Error(msg);
    }
    const d = await res.json();
    hideLoginGate();
    setProfileUsername(d.username);
    const pw = document.getElementById("login-password");
    if (pw) pw.value = "";
    if (!appBooted) {
      appBooted = true;
      await boot();
    }
  } catch (err) {
    if (errEl) {
      errEl.textContent = err.message;
      errEl.hidden = false;
    }
  }
}

async function doLogout() {
  try {
    await fetch("/api/auth/logout", { ...FETCH_OPTS, method: "POST" });
  } catch (_) {
    /* ignore */
  }
  showLoginGate();
  const u = document.getElementById("login-username");
  const p = document.getElementById("login-password");
  if (u) u.value = "";
  if (p) p.value = "";
}

function openMonthlyModePanel() {
  const mode = budget?.settings?.monatlich_mode || "div12";
  openPanel(
    t("monthlyCalculation"),
    `<div class="settings-group"><label>${t("monthlyCalculation")}</label>
    <select id="set-monatlich"><option value="div12" ${mode === "div12" ? "selected" : ""}>${t("monthlyModeDiv12")}</option>
    <option value="filled" ${mode === "filled" ? "selected" : ""}>${t("monthlyModeFilled")}</option></select></div>`
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
    toast(t("saved"));
  };
}

function openChangePasswordPanel() {
  openPanel(
    t("changePassword"),
    `<div class="settings-group"><label>${t("resetCode")}</label>
    <input type="password" id="reset-code" autocomplete="off" /></div>
    <div class="settings-group"><label>${t("newPassword")}</label>
    <input type="password" id="new-password" autocomplete="new-password" /></div>
    <div class="settings-group"><label>${t("newUsername")}</label>
    <input type="text" id="new-username" autocomplete="username" placeholder="${t("optional")}" /></div>`
  );
  document.getElementById("panel-confirm").style.display = "block";
  document.getElementById("panel-confirm").onclick = async () => {
    const reset_code = document.getElementById("reset-code")?.value || "";
    const new_password = document.getElementById("new-password")?.value || "";
    const new_username = document.getElementById("new-username")?.value?.trim() || "";
    try {
      await api("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reset_code, new_password, new_username }),
      });
      closePanel();
      toast(t("passwordChanged"));
      await doLogout();
    } catch (err) {
      toast(err.message);
    }
  };
}

async function api(path, opts = {}) {
  const res = await fetch(path, { ...FETCH_OPTS, ...opts });
  if (res.status === 401 && !String(path).includes("/api/auth/")) {
    showLoginGate();
    throw new Error("Please sign in");
  }
  if (!res.ok) {
    const text = await res.text();
    try {
      const j = JSON.parse(text);
      if (j.detail) {
        const d = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
        throw new Error(d);
      }
    } catch (e) {
      if (e instanceof Error && e.message && !e.message.startsWith("{")) throw e;
    }
    if (res.status === 404) {
      throw new Error(
        "Not found — select a client in the top bar, then refresh (Ctrl+F5). Restart the app if it still fails."
      );
    }
    throw new Error(text || `Request failed (${res.status})`);
  }
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
  const months = getMonthLabels();
  ["dashboard-month", "charts-month", "bulk-from-month", "bulk-to-month"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.innerHTML = months.map((m, i) => `<option value="${i + 1}">${m}</option>`).join("");
    el.value = String(selectedMonth);
  });
  const toM = document.getElementById("bulk-to-month");
  if (toM) toM.value = "12";
}

let activePlanTab = "income";
let addRowTargetSection = "";
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
      computed[0].textContent = formatMoney(summe);
      computed[1].textContent = formatMoney(mon);
    }
  });

  container.querySelectorAll("tr.summary-row[data-summary-key]").forEach((row) => {
    const sk = row.dataset.summaryKey;
    const sm = budget.summary?.section_summaries?.[sk];
    if (!sm) return;
    const tds = row.querySelectorAll("td");
    for (let i = 1; i <= 12; i++) {
      if (tds[i]) tds[i].textContent = formatMoney(sm.months[i - 1]);
    }
    if (tds[13]) tds[13].textContent = formatMoney(sm.summe);
    if (tds[14]) tds[14].textContent = formatMoney(sm.monatlich);
  });
}

/** Update only the visible panel after budget data changes. */
async function refreshAfterDataChange() {
  if (!budget) return;
  invalidateChartsCache();
  markBalanceStale();
  const active = activePanelId();
  if (active === "panel-plan") {
    updatePlanGridTotals();
    return;
  }
  if (active === "panel-summary") {
    renderSummary();
    return;
  }
  if (active === "panel-dashboard") await renderDashboard();
  else if (active === "panel-charts") await renderChartsPanel();
  else if (active === "panel-balance") await renderBalancePanel();
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
    invalidateChartsCache();
    markBalanceStale();
    const active = activePanelId();
    if (active === "panel-plan") updatePlanGridTotals();
    else if (active === "panel-summary") renderSummary();
    else if (active === "panel-dashboard") await renderDashboard();
    else if (active === "panel-charts") await renderChartsPanel();
  } catch (e) {
    showError(e);
  }
}

function scrollActivePanelToTop() {
  const panel = document.querySelector("main > .panel.active");
  if (!panel) {
    window.scrollTo({ top: 0, left: 0, behavior: "auto" });
    return;
  }
  const chrome = document.querySelector(".app-top");
  const stickyH = chrome?.getBoundingClientRect().height || 0;
  const y = panel.getBoundingClientRect().top + window.scrollY - stickyH - 8;
  window.scrollTo({ top: Math.max(0, y), left: 0, behavior: "auto" });
}

function switchPanel(panelId) {
  const nav = document.getElementById("main-tabs");
  nav?.querySelectorAll("button").forEach((b) => {
    b.classList.toggle("active", b.dataset.panel === panelId);
  });
  document.querySelectorAll("main > .panel").forEach((p) => p.classList.remove("active"));
  const panel = document.getElementById(`panel-${panelId}`);
  if (panel) panel.classList.add("active");
  scrollActivePanelToTop();

  if (panelId === "clients") {
    openClientsPanel();
    return;
  }
  if (panelId === "future") {
    initFutureInvestPanel();
    markBalanceStale();
    renderFuturePanel()
      .then(() => document.getElementById("inline-future-name")?.focus())
      .catch((e) => showError(e));
    return;
  }
  if (panelId === "balance") {
    markBalanceStale();
    renderBalancePanel()
      .then(() => document.getElementById("inline-asset-name")?.focus())
      .catch((e) => showError(e));
    return;
  }
  if (!budget || !meta) return;
  if (panelId === "plan") {
    renderPlanGrid(activePlanTab);
    requestAnimationFrame(() => scrollActivePanelToTop());
  }
  else if (panelId === "charts") renderChartsPanel().catch((e) => showError(e));
  else if (panelId === "dashboard") renderDashboard().catch((e) => showError(e));
  else if (panelId === "summary") renderSummary();
}

function showError(err) {
  console.error(err);
  toast(`${t("errorPrefix")}: ${err.message || t("requestFailed")}`);
}

function initTabs() {
  const nav = document.getElementById("main-tabs");
  if (!nav) return;
  nav.querySelectorAll("button[data-panel]").forEach((btn) => {
    btn.addEventListener("click", () => switchPanel(btn.dataset.panel));
  });
}

function scrollPlanTabIntoView(btn) {
  if (!btn) return;
  btn.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
}

function bindPlanTabsScroll(planTabs) {
  if (!planTabs || planTabs.dataset.scrollBound === "1") return;
  planTabs.dataset.scrollBound = "1";
  planTabs.addEventListener(
    "wheel",
    (e) => {
      if (planTabs.scrollWidth <= planTabs.clientWidth) return;
      e.preventDefault();
      planTabs.scrollLeft += e.deltaY;
    },
    { passive: false }
  );
}

function initPlanTabs() {
  const planTabs = document.getElementById("plan-tabs");
  if (!planTabs || !meta) return;
  const tabs = meta.tabs.filter(
    (t) => !["dashboard", "summary", "charts", "balance"].includes(t.id)
  );
  planTabs.innerHTML = tabs
    .map(
      (t, i) =>
        `<button type="button" data-tab="${t.id}" class="${t.id === activePlanTab || (i === 0 && !activePlanTab) ? "active" : ""}">${getLang() === "de" ? t.label_de : t.label_en}</button>`
    )
    .join("");
  bindPlanTabsScroll(planTabs);
  planTabs.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      activePlanTab = btn.dataset.tab;
      planTabs.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      scrollPlanTabIntoView(btn);
      populateBulkLineSelect();
      syncAddRowTargetToTab();
      renderPlanGrid(activePlanTab);
      requestAnimationFrame(() => scrollActivePanelToTop());
    });
  });
  scrollPlanTabIntoView(planTabs.querySelector("button.active"));
  populateBulkLineSelect();
  syncAddRowTargetToTab();
}

function linesForSection(sec) {
  const built = sec.lines.map((line) => ({ ...line, custom: false }));
  const custom = (budget?.custom_lines?.[sec.id] || []).map((line) => ({
    key: line.line_key,
    label_de: line.label_de,
    label_en: line.label_en,
    line_type: line.line_type,
    custom: true,
  }));
  return built.concat(custom);
}

function sectionsForActivePlanTab() {
  if (!meta) return [];
  return meta.sections.filter((s) => s.tab === activePlanTab);
}

function defaultLineTypeForSection(sectionId) {
  const sec = meta?.sections?.find((s) => s.id === sectionId);
  if (!sec?.lines?.length) return "expense";
  const income = sec.lines.some((l) => l.line_type === "income");
  const expense = sec.lines.some((l) => l.line_type === "expense");
  if (income && !expense) return "income";
  if (sec.tab === "income") return "income";
  return "expense";
}

function updateAddRowTargetHint() {
  const el = document.getElementById("add-row-target-hint");
  if (!el) return;
  const sec = meta?.sections?.find((s) => s.id === addRowTargetSection);
  if (sec) {
    el.textContent = `${t("addRowAddsTo")}: ${sectionTitle(sec)} — ${t("addRowClickSection")}`;
  } else {
    el.textContent = t("addRowClickSection");
  }
}

function highlightAddRowTargetSection() {
  document.querySelectorAll(".grid-wrap[data-section-id]").forEach((wrap) => {
    wrap.classList.toggle("plan-section-target", wrap.dataset.sectionId === addRowTargetSection);
  });
}

function setAddRowTargetSection(sectionId) {
  addRowTargetSection = sectionId;
  updateAddRowTargetHint();
  highlightAddRowTargetSection();
}

function syncAddRowTargetToTab() {
  const sections = sectionsForActivePlanTab();
  if (!sections.length) {
    addRowTargetSection = "";
    updateAddRowTargetHint();
    highlightAddRowTargetSection();
    return;
  }
  if (!sections.some((s) => s.id === addRowTargetSection)) {
    addRowTargetSection = sections[0].id;
  }
  updateAddRowTargetHint();
  highlightAddRowTargetSection();
}

async function submitAddRow() {
  requireClient();
  const name = document.getElementById("add-row-name")?.value?.trim();
  if (!name) throw new Error(t("nameRequired"));
  syncAddRowTargetToTab();
  if (!addRowTargetSection) throw new Error(t("addRowClickSection"));
  const res = await postCustomLine({
    section_id: addRowTargetSection,
    label_de: name,
    label_en: name,
    line_type: defaultLineTypeForSection(addRowTargetSection),
  });
  if (res.custom_lines) budget.custom_lines = res.custom_lines;
  if (res.entries) budget.entries = res.entries;
  if (res.summary) budget.summary = res.summary;
  selectedLineKey = res.line?.line_key || selectedLineKey;
  const nameInput = document.getElementById("add-row-name");
  if (nameInput) nameInput.value = "";
  invalidateChartsCache();
  markBalanceStale();
  populateBulkLineSelect();
  renderPlanGrid(activePlanTab);
  toast(t("saved"));
  if (selectedLineKey) {
    const row = document.querySelector(`tr[data-key="${selectedLineKey}"]`);
    row?.querySelector("input[data-month='1']")?.focus();
  }
}

function populateBulkLineSelect() {
  const sel = document.getElementById("bulk-line-select");
  if (!sel || !meta) return;
  const opts = [];
  for (const sec of sectionsForActivePlanTab()) {
    for (const line of linesForSection(sec)) {
      const label = getLang() === "de" ? line.label_de : line.label_en;
      opts.push(
        `<option value="${line.key}">${sectionTitle(sec)} — ${label}${line.custom ? " *" : ""}</option>`
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

async function ensureClient(force = false) {
  const now = Date.now();
  if (!force && clientsList.length && now - clientsCacheTime < CLIENTS_CACHE_MS) {
    if (!clientsList.some((c) => c.id === activeClientId)) {
      activeClientId = clientsList[0].id;
      localStorage.setItem("activeClientId", String(activeClientId));
    }
    populateClientSelect();
    return;
  }
  const data = await api("/api/clients");
  clientsList = data.clients || [];
  clientsCacheTime = now;
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

async function syncBalanceSheet() {
  const cid = getActiveClientId();
  if (!cid || !budget) return budget?.balance_sheet ?? null;
  try {
    const year = getActiveYear();
    const bs = await api(`/api/clients/${cid}/balance-sheet?year=${year}`);
    budget.balance_sheet = bs;
    balanceSheetStale = false;
    return bs;
  } catch (e) {
    console.warn("balance-sheet", e);
    return budget.balance_sheet ?? null;
  }
}

async function loadBudget() {
  const loading = document.getElementById("plan-loading");
  if (loading) loading.hidden = false;
  try {
    await ensureClient();
    const needMeta = !meta;
    const [budgetData, metaData] = await Promise.all([
      api(apiBase()),
      needMeta ? api("/api/meta") : Promise.resolve(null),
    ]);
    budget = budgetData;
    budget.settings = budget.settings || { monatlich_mode: "div12" };
    if (metaData) meta = metaData;
    balanceSheetStale = false;
    invalidateChartsCache();
    fillMonthSelects();
    initPlanTabs();
    const active = activePanelId();
    if (active === "panel-plan") renderPlanGrid(activePlanTab);
    else if (active === "panel-dashboard") await renderDashboard();
    else if (active === "panel-charts") await renderChartsPanel();
    else if (active === "panel-balance") await renderBalancePanel();
    else if (active === "panel-future") await renderFuturePanel();
    else if (active === "panel-summary") renderSummary();
    updateBalanceClientBanner();
  } finally {
    if (loading) loading.hidden = true;
  }
}

async function getChartsData() {
  const key = `${getActiveClientId()}-${getActiveYear()}-${selectedMonth}`;
  if (chartsCache && chartsCacheKey === key) return chartsCache;
  chartsCache = await api(`${apiBase()}/summary?month=${selectedMonth}`);
  chartsCacheKey = key;
  return chartsCache;
}

async function renderDashboard() {
  if (!budget) return;
  const { charts, summary, balance_sheet: bs } = await getChartsData();
  const period = document.getElementById("chart-period")?.value || "month";
  const h = charts.hero;
  const yr = charts.year;
  const netWorth = bs?.net_worth ?? budget.balance_sheet?.net_worth ?? 0;

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

  document.getElementById("hero-balance").textContent = formatMoney(diff);
  document.getElementById("hero-balance").className = `hero-balance ${diff < 0 ? "deficit" : "surplus"}`;
  document.getElementById("hero-revenue").textContent = formatMoney(rev);
  document.getElementById("hero-expenses").textContent = formatMoney(exp);
  document.getElementById("hero-pill").innerHTML = diff < 0
    ? `<span class="pill deficit">${t("deficit")}</span>`
    : `<span class="pill surplus">${t("surplus")}</span>`;

  document.getElementById("kpi-row").innerHTML = `
    <div class="kpi-card income"><div class="label">${t("revenue")}</div><div class="value">${formatMoney(rev)}</div></div>
    <div class="kpi-card expense"><div class="label">${t("expenses")}</div><div class="value">${formatMoney(exp)}</div></div>
    <div class="kpi-card ${diff < 0 ? "deficit" : "surplus"}"><div class="label">${t("balance")}</div><div class="value">${formatMoney(diff)}</div></div>
    <div class="kpi-card"><div class="label">${t("yearTotalDiff")}</div><div class="value">${formatMoney(summary.difference.summe)}</div></div>
    ${bs ? `<div class="kpi-card ${netWorth < 0 ? "deficit" : "surplus"}"><div class="label">${t("netWorth")}</div><div class="value">${formatMoney(netWorth)}</div></div>` : ""}
  `;

  const t1 = summary.total_1.months[selectedMonth - 1];
  const t2 = summary.total_2.months[selectedMonth - 1];
  const t3 = summary.total_3.months[selectedMonth - 1];
  const t4 = summary.total_4.months[selectedMonth - 1];
  const tch = summary.total_children?.months?.[selectedMonth - 1] ?? 0;
  document.getElementById("section-cards").innerHTML = `
    <div class="kpi-card"><div class="label">${t("sumLiving")}</div><div class="value">${formatMoney(t1)}</div></div>
    <div class="kpi-card"><div class="label">${t("sumHousing")}</div><div class="value">${formatMoney(t2)}</div></div>
    <div class="kpi-card"><div class="label">${t("sumInsurance")}</div><div class="value">${formatMoney(t3)}</div></div>
    <div class="kpi-card"><div class="label">${t("sumSavingsLoans")}</div><div class="value">${formatMoney(t4)}</div></div>
    <div class="kpi-card"><div class="label">${t("sumChildren")}</div><div class="value">${formatMoney(tch)}</div></div>
  `;

  renderDonut(charts.donut_sections, "donut-chart", "donut-legend", (id) => loadDrilldown(id));
  renderBarChart(charts.monthly_bars);
}

function buildExpenseItemSlices(maxVisible = 12) {
  if (!budget || !meta) return [];
  const items = [];
  for (const sec of meta.sections) {
    if (INCOME_SECTION_IDS.has(sec.id)) continue;
    for (const line of linesForSection(sec)) {
      if (line.line_type === "income") continue;
      const vals = budget.entries[line.key] || [];
      const amt = vals[selectedMonth - 1] || 0;
      if (amt > 0) {
        items.push({
          id: line.key,
          label: line.label_en,
          label_en: line.label_en,
          label_de: line.label_de,
          amount: amt,
        });
      }
    }
  }
  items.sort((a, b) => b.amount - a.amount);
  let shown = items;
  if (items.length > maxVisible) {
    const top = items.slice(0, maxVisible - 1);
    const restAmt = items.slice(maxVisible - 1).reduce((s, i) => s + i.amount, 0);
    top.push({
      id: "other_items",
      label: "Other",
      label_en: "Other",
      label_de: "Sonstiges",
      amount: restAmt,
    });
    shown = top;
  }
  const total = shown.reduce((s, i) => s + i.amount, 0) || 1;
  return shown.map((i) => ({
    ...i,
    pct: Math.round((1000 * i.amount) / total) / 10,
  }));
}

function renderDonut(slices, canvasId, legendId, onClick, opts = {}) {
  const ctx = document.getElementById(canvasId);
  const leg = legendId ? document.getElementById(legendId) : null;
  const chartType = opts.type || "doughnut";
  const cutout = opts.cutout ?? (chartType === "pie" ? 0 : "65%");

  if (!slices.length) {
    const existing = donutChartByCanvas[canvasId];
    if (existing) {
      existing.destroy();
      delete donutChartByCanvas[canvasId];
    }
    if (canvasId === "donut-chart") donutChart = null;
    else if (canvasId === "charts-donut") chartsDonut = null;
    else if (canvasId === "charts-items-pie") chartsItemsPie = null;
    if (leg) leg.innerHTML = `<li class="legend-empty">${escapeHtml(t("noExpensesMonth"))}</li>`;
    return;
  }

  if (!ctx) return;
  const labels = slices.map((s) => chartSliceLabel(s));
  const values = slices.map((s) => s.amount);
  const colors = slices.map((_, i) => CHART_COLORS[i % CHART_COLORS.length]);
  const existing = donutChartByCanvas[canvasId];
  if (existing) {
    existing.config.type = chartType;
    existing.data.labels = labels;
    existing.data.datasets[0].data = values;
    existing.data.datasets[0].backgroundColor = colors;
    if (existing.options.cutout !== undefined) existing.options.cutout = cutout;
    existing.update("none");
  } else {
    const chart = new Chart(ctx, {
      type: chartType,
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderWidth: 2,
          borderColor: "#fff",
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (c) =>
                `${c.label}: ${formatMoney(c.raw)} (${slices[c.dataIndex]?.pct ?? 0}%)`,
            },
          },
        },
        onClick: (_, els) => {
          if (els.length && onClick) onClick(slices[els[0].index].id);
        },
      },
    });
    donutChartByCanvas[canvasId] = chart;
    if (canvasId === "donut-chart") donutChart = chart;
    else if (canvasId === "charts-donut") chartsDonut = chart;
    else if (canvasId === "charts-items-pie") chartsItemsPie = chart;
  }

  if (leg) {
    leg.innerHTML = slices
      .map(
        (s, i) =>
          `<li data-id="${s.id}"><span class="dot" style="background:${CHART_COLORS[i % CHART_COLORS.length]}"></span>${chartSliceLabel(s)} · ${formatMoney(s.amount)} (${s.pct}%)</li>`
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
  const revData = bars.map((b) => b.revenue);
  const expData = bars.map((b) => b.expenses);
  if (barChart) {
    barChart.data.labels = getMonthLabels();
    barChart.data.datasets[0].data = revData;
    barChart.data.datasets[0].label = t("revenue");
    barChart.data.datasets[1].data = expData;
    barChart.data.datasets[1].label = t("expenses");
    barChart.update("none");
    return;
  }
  barChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: getMonthLabels(),
      datasets: [
        { label: t("revenue"), data: revData, backgroundColor: "#059669" },
        { label: t("expenses"), data: expData, backgroundColor: "#ea580c" },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: (v) => formatMoney(v),
          },
        },
      },
    },
  });
}

async function loadDrilldown(sectionId) {
  const data = await api(`${apiBase()}/drilldown?section=${sectionId}&month=${selectedMonth}`);
  const card = document.getElementById("drilldown-card");
  if (!data.slices.length) {
    toast(t("noExpensesSection"));
    return;
  }
  card.style.display = "block";
  document.getElementById("drilldown-title").textContent = `${t("drilldownPrefix")}: ${(meta?.sections?.find((x) => x.id === sectionId) ? sectionTitle(meta.sections.find((x) => x.id === sectionId)) : sectionId)}`;
  if (drilldownChart) drilldownChart.destroy();
  drilldownChart = new Chart(document.getElementById("drilldown-chart"), {
    type: "doughnut",
    data: {
      labels: data.slices.map((s) => chartSliceLabel(s)),
      datasets: [{ data: data.slices.map((s) => s.amount), backgroundColor: CHART_COLORS }],
    },
    options: { responsive: true, maintainAspectRatio: false },
  });
}

async function renderChartsPanel() {
  if (!budget || !meta) return;
  const { charts } = await getChartsData();
  renderDonut(charts.donut_sections, "charts-donut", null, loadDrilldown);
  renderDonut(buildExpenseItemSlices(12), "charts-items-pie", "charts-items-legend", null, {
    type: "pie",
    cutout: 0,
  });
  const allLines = [];
  for (const sec of meta.sections) {
    if (INCOME_SECTION_IDS.has(sec.id)) continue;
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
      return `<div style="margin-bottom:10px"><div style="display:flex;justify-content:space-between;font-size:0.9rem"><span>${l.label}</span><span>${formatMoney(l.amount)}</span></div><div style="height:8px;background:#e2e8f0;border-radius:4px"><div style="width:${w}%;height:100%;background:var(--primary);border-radius:4px"></div></div>`;
    })
    .join("");
}

const ASSET_TYPE_LABELS = {
  savings: { en: "Savings account", de: "Sparkonto" },
  gold: { en: "Gold", de: "Gold" },
  silver: { en: "Silver", de: "Silber" },
  etf: { en: "ETF / funds", de: "ETF / Fonds" },
  fd: { en: "Fixed deposit", de: "Festgeld" },
  property: { en: "Property", de: "Immobilie" },
  stocks: { en: "Stocks", de: "Aktien" },
  crypto: { en: "Crypto", de: "Krypto" },
  other: { en: "Other", de: "Sonstiges" },
};

function assetTypeLabel(type) {
  const L = ASSET_TYPE_LABELS[type] || ASSET_TYPE_LABELS.other;
  return getLang() === "de" ? L.de : L.en;
}

/** Monthly rate from annual % p.a. (matches app/debt_payoff.py). */
function debtMonthlyRate(annualPct) {
  return Math.max(0, Number(annualPct) || 0) / 100 / 12;
}

/** Interest for one month: outstanding × (annual% / 100) / 12 */
function debtMonthlyInterest(principal, annualPct) {
  const p = Number(principal) || 0;
  if (p <= 0) return 0;
  return Math.round(p * debtMonthlyRate(annualPct) * 100) / 100;
}

/** Amortization months (fixed payment); null if payment does not cover interest. */
function debtMonthsToClear(principal, payment, annualPct) {
  const P = Number(principal) || 0;
  const M = Number(payment) || 0;
  if (P <= 0) return 0;
  if (M <= 0) return null;
  const r = debtMonthlyRate(annualPct);
  if (r <= 0) return Math.ceil(P / M);
  const interestFirstMonth = P * r;
  if (M <= interestFirstMonth + 1e-9) return null;
  const ratio = 1 - interestFirstMonth / M;
  if (ratio <= 0) return 0;
  const n = -Math.log(ratio) / Math.log(1 + r);
  return Math.max(1, Math.ceil(n));
}

function formatDebtMonthsCell(pd) {
  if (pd.months_to_clear != null) return String(pd.months_to_clear);
  if (pd.payment_covers_interest === false) return "!";
  return "—";
}

function readDebtRowPayload(row) {
  const get = (field) => row.querySelector(`[data-field="${field}"]`);
  const rateEl = get("interest_rate_annual");
  const rateRaw = rateEl?.value?.trim() ?? "";
  let interest_rate_annual;
  if (rateRaw === "") {
    const existing = debtById(row.dataset.debtId);
    interest_rate_annual = existing ? Number(existing.interest_rate_annual || 0) : 0;
  } else {
    interest_rate_annual = parseNumInput(rateRaw);
  }
  return {
    name: get("name")?.value?.trim() || "",
    amount: parseNumInput(get("amount")?.value),
    interest_rate_annual,
    monthly_payment: parseNumInput(get("monthly_payment")?.value),
    notes: "",
  };
}

function formatRateInputValue(rate) {
  const n = Number(rate);
  if (!Number.isFinite(n)) return "";
  return String(n);
}

function debtById(debtId) {
  return (budget?.balance_sheet?.debts || []).find((d) => String(d.id) === String(debtId));
}

function mergeDebtIntoBalanceSheet(debt) {
  if (!debt || !budget?.balance_sheet) return;
  const debts = budget.balance_sheet.debts || [];
  const i = debts.findIndex((d) => String(d.id) === String(debt.id));
  if (i >= 0) debts[i] = { ...debts[i], ...debt };
  else debts.push(debt);
  budget.balance_sheet.debts = debts;
}

/** Sync one debt row from server without full table repaint (skips focused inputs). */
function patchDebtRowFromServer(debt) {
  if (!debt?.id) return;
  const row = document.querySelector(`#debts-table tr[data-debt-id="${debt.id}"]`);
  if (!row) return;
  const active = document.activeElement;
  const setIfIdle = (field, value) => {
    const el = row.querySelector(`[data-field="${field}"]`);
    if (!el || el === active) return;
    if (field === "interest_rate_annual") el.value = formatRateInputValue(value);
    else if (el.type === "number") el.value = value ?? 0;
    else el.value = value ?? "";
  };
  setIfIdle("name", debt.name);
  setIfIdle("amount", debt.amount);
  setIfIdle("interest_rate_annual", debt.interest_rate_annual);
  setIfIdle("monthly_payment", debt.monthly_payment);
}

function resolveDebtPayForCalc(principal, monthlyPayment, pd, effectivePay, totalDebts) {
  let pay = Number(monthlyPayment) || 0;
  if (pay <= 0 && pd.planned_payment > 0) pay = pd.planned_payment;
  else if (pay <= 0 && effectivePay > 0 && principal > 0 && totalDebts > 0) {
    pay = Math.round(effectivePay * (principal / totalDebts) * 100) / 100;
  }
  return pay;
}

function computeDebtRowDisplay(principal, rateVal, monthlyPayment, pd, effectivePay, totalDebts) {
  const payForCalc = resolveDebtPayForCalc(
    principal,
    monthlyPayment,
    pd || {},
    effectivePay,
    totalDebts
  );
  const intMo = debtMonthlyInterest(principal, rateVal);
  const monthsCalc = debtMonthsToClear(principal, payForCalc, rateVal);
  let monthsLabel = "—";
  let monthsWarn = false;
  if (monthsCalc != null) monthsLabel = String(monthsCalc);
  else if (rateVal > 0 && payForCalc > 0 && payForCalc <= intMo + 1e-9) {
    monthsLabel = "!";
    monthsWarn = true;
  }
  return { intMo, monthsLabel, monthsWarn, payForCalc };
}

function syncDebtRowComputedCells(row, principal, rateVal, monthlyPayment, pd, effectivePay, totalDebts) {
  const { intMo, monthsLabel, monthsWarn } = computeDebtRowDisplay(
    principal,
    rateVal,
    monthlyPayment,
    pd,
    effectivePay,
    totalDebts
  );
  const intCell = row.querySelector(".debt-interest-mo");
  if (intCell) {
    intCell.textContent = formatMoney(intMo);
    intCell.title = `${t("interestFormula")}: ${formatMoney(intMo)}`;
  }
  const monthsCell = row.querySelector(".payoff-months");
  if (!monthsCell) return;
  monthsCell.textContent = monthsLabel;
  monthsCell.title = monthsWarn ? t("payoffInterestTooLow") : "";
  row.classList.toggle("debt-row-warn", monthsWarn);
}

function liveDebtsTotalsFromTable() {
  let totalPrincipal = 0;
  let totalInt = 0;
  let totalRepay = 0;
  document.querySelectorAll("#debts-table tr[data-debt-id]").forEach((row) => {
    const p = readDebtRowPayload(row);
    totalPrincipal += p.amount;
    totalInt += debtMonthlyInterest(p.amount, p.interest_rate_annual);
    totalRepay += p.monthly_payment;
  });
  return {
    totalDebts: Math.round(totalPrincipal * 100) / 100,
    totalInt: Math.round(totalInt * 100) / 100,
    totalRepay: Math.round(totalRepay * 100) / 100,
  };
}

function buildLivePayoffPreview(serverPayoff) {
  const base = serverPayoff ? { ...serverPayoff } : {};
  const live = liveDebtsTotalsFromTable();
  const effectivePay = live.totalRepay > 0 ? live.totalRepay : base.effective_monthly_payment || 0;
  const per_debt = [];
  document.querySelectorAll("#debts-table tr[data-debt-id]").forEach((row) => {
    const p = readDebtRowPayload(row);
    const pd =
      (base.per_debt || []).find((x) => String(x.id) === String(row.dataset.debtId)) || {};
    const disp = computeDebtRowDisplay(
      p.amount,
      p.interest_rate_annual,
      p.monthly_payment,
      pd,
      effectivePay,
      live.totalDebts
    );
    let monthsNum = null;
    if (disp.monthsLabel !== "—" && disp.monthsLabel !== "!") {
      monthsNum = parseInt(disp.monthsLabel, 10);
    }
    per_debt.push({
      ...pd,
      id: Number(row.dataset.debtId),
      name: p.name || pd.name || "",
      amount: p.amount,
      interest_rate_annual: p.interest_rate_annual,
      monthly_interest: disp.intMo,
      monthly_payment: p.monthly_payment,
      planned_payment: disp.payForCalc,
      months_to_clear: monthsNum,
      payment_covers_interest: disp.monthsLabel !== "!",
      debt_free_label: pd.debt_free_label || null,
    });
  });
  return {
    ...base,
    total_debt: live.totalDebts,
    total_monthly_interest: live.totalInt,
    total_monthly_payment: live.totalRepay,
    effective_monthly_payment: effectivePay,
    per_debt,
  };
}

function updatePayoffCardLive() {
  const bs = budget?.balance_sheet || emptyBalanceSheet();
  renderPayoffCard(buildLivePayoffPreview(bs.payoff));
}

function updateDebtsTableFooterLive() {
  const live = liveDebtsTotalsFromTable();
  const foot = document.querySelector("#debts-table tfoot .balance-total-row");
  if (!foot) return;
  const cells = foot.querySelectorAll("td");
  if (cells.length >= 5) {
    cells[1].innerHTML = `<strong>${formatMoney(live.totalDebts)}</strong>`;
    cells[3].innerHTML = `<strong>${formatMoney(live.totalInt)}</strong>`;
    cells[4].innerHTML = `<strong>${formatMoney(live.totalRepay)}</strong>`;
  }
}

function updateBalanceKpisLive(bs) {
  const kpiEl = document.getElementById("balance-kpi-row");
  if (!kpiEl) return;
  bs = bs || budget?.balance_sheet || emptyBalanceSheet();
  const totalAssets = Number(bs.total_assets) || 0;
  const live = liveDebtsTotalsFromTable();
  const totalDebts = document.querySelector("#debts-table tr[data-debt-id]")
    ? live.totalDebts
    : Number(bs.total_debts) || 0;
  const netWorth = totalAssets - totalDebts;
  kpiEl.innerHTML = `
    <div class="kpi-card income"><div class="label">${t("totalAssets")}</div><div class="value">${formatMoney(totalAssets)}</div></div>
    <div class="kpi-card expense"><div class="label">${t("totalDebts")}</div><div class="value">${formatMoney(totalDebts)}</div></div>
    <div class="kpi-card ${netWorth < 0 ? "deficit" : "surplus"}"><div class="label">${t("netWorth")}</div><div class="value">${formatMoney(netWorth)}</div></div>`;
  const hint = document.querySelector("#panel-balance > .hint-banner");
  if (hint) {
    hint.textContent = `${t("hintBalance")} — ${t("netWorthFormula")}: ${formatMoney(totalAssets)} − ${formatMoney(totalDebts)} = ${formatMoney(netWorth)}`;
  }
}

function refreshDebtRowAndFooter() {
  refreshAllDebtRowsLive();
  updatePayoffCardLive();
  updateBalanceKpisLive();
}

function patchDebtBalanceUI(bs) {
  updateBalanceKpisLive(bs);
  updatePayoffCardLive();
  refreshAllDebtRowsLive();
  updateDebtsTableFooterLive();
}

function renderPayoffCard(payoff) {
  const el = document.getElementById("balance-payoff-card");
  if (!el) return;
  if (!payoff) {
    const cid = getActiveClientId();
    if (!cid) {
      el.innerHTML = `<p class="hint-banner">${escapeHtml(t("payoffNoBudget"))}</p>`;
    } else {
      el.innerHTML = `<p class="hint-banner">${escapeHtml(t("payoffNoIncome"))}</p>`;
    }
    return;
  }
  const year = getActiveYear();
  let monthsText = "—";
  let freeText = "—";
  if (payoff.months_to_clear_debts != null) {
    monthsText = `${payoff.months_to_clear_debts} ${t("months")}`;
    freeText = payoff.debt_free_label || "—";
  } else if (payoff.any_interest_blocked) {
    monthsText = t("payoffInterestTooLow");
  } else if (payoff.total_debt > 0) {
    monthsText = t("payoffNeedPayment");
  } else {
    monthsText = t("payoffNoDebt");
  }
  const surplusCls = payoff.monthly_surplus >= 0 ? "surplus" : "deficit";
  const planNote = payoff.using_budget_surplus
    ? t("payoffUsingSurplus")
    : t("payoffUsingEntered");
  const interestStat =
    (payoff.total_monthly_interest || 0) > 0
      ? `<div class="payoff-stat"><span class="label">${t("interestPerMonth")}</span><span class="value expense">${formatMoney(payoff.total_monthly_interest)}</span></div>`
      : "";
  el.innerHTML = `
    <h2>${t("payoffTitle")} (${year})</h2>
    <p class="hint-banner">${escapeHtml(planNote)}</p>
    <div class="payoff-grid">
      <div class="payoff-stat"><span class="label">${t("monthlyIncome")}</span><span class="value income">${formatMoney(payoff.monthly_income)}</span></div>
      <div class="payoff-stat"><span class="label">${t("monthlyExpenses")}</span><span class="value expense">${formatMoney(payoff.monthly_expenses)}</span></div>
      <div class="payoff-stat"><span class="label">${t("monthlySurplus")}</span><span class="value ${surplusCls}">${formatMoney(payoff.monthly_surplus)}</span></div>
      ${interestStat}
      <div class="payoff-stat"><span class="label">${t("repayPerMonth")}</span><span class="value">${formatMoney(payoff.effective_monthly_payment)}</span></div>
      <div class="payoff-stat highlight"><span class="label">${t("monthsToClearAll")}</span><span class="value">${monthsText}</span></div>
      <div class="payoff-stat highlight"><span class="label">${t("debtFreeBy")}</span><span class="value">${freeText}</span></div>
    </div>`;
}

function setPanelConfirm(handler) {
  const btn = document.getElementById("panel-confirm");
  if (!btn) return;
  btn.onclick = async (e) => {
    e.preventDefault();
    try {
      await handler();
    } catch (err) {
      showError(err);
    }
  };
}

function updateFutureClientBanner() {
  const banner = document.getElementById("future-client-banner");
  if (!banner) return;
  const cid = getActiveClientId();
  if (!cid) {
    banner.textContent = t("balanceSelectClient");
    banner.classList.add("error");
    return;
  }
  banner.classList.remove("error");
  const name =
    budget?.client_name ||
    clientsList.find((c) => c.id === cid)?.name ||
    document.getElementById("client-select")?.selectedOptions?.[0]?.textContent ||
    `#${cid}`;
  banner.innerHTML = `<strong>${escapeHtml(t("futureForClient"))}:</strong> ${escapeHtml(name)} · ${t("year")} ${getActiveYear()}`;
}

function futureMonthsLabel(item) {
  const m = item.months_to_target;
  if (m === 0) return "0";
  if (m == null) return "—";
  return String(m);
}

function paintFuturePanel(bs) {
  const kpiEl = document.getElementById("future-kpi-row");
  const tableEl = document.getElementById("future-invest-table");
  if (!kpiEl || !tableEl) return;
  updateFutureClientBanner();
  const cid = getActiveClientId();
  if (!cid) {
    kpiEl.innerHTML = `<p class="hint-banner error">${escapeHtml(t("selectClient"))}</p>`;
    tableEl.innerHTML = "";
    return;
  }
  if (!budget) {
    kpiEl.innerHTML = `<p class="hint-banner">${escapeHtml(t("loading"))}</p>`;
    return;
  }
  const plan = getFuturePlan(bs);
  const items = plan.items || [];
  kpiEl.innerHTML = `
    <div class="kpi-card income"><div class="label">${t("totalCurrentInvest")}</div><div class="value">${formatMoney(plan.total_current || 0)}</div></div>
    <div class="kpi-card expense"><div class="label">${t("totalTargetInvest")}</div><div class="value">${formatMoney(plan.total_target || 0)}</div></div>
    <div class="kpi-card surplus"><div class="label">${t("totalMonthlyContrib")}</div><div class="value">${formatMoney(plan.total_monthly_contribution || 0)}</div></div>
    <div class="kpi-card income"><div class="label">${t("progressToTarget")}</div><div class="value">${plan.overall_progress_pct != null ? plan.overall_progress_pct + "%" : "—"}</div></div>
  `;
  let html = `<thead><tr>
    <th>${t("assetName")}</th>
    <th class="col-money">${t("currentAmount")}</th>
    <th class="col-money">${t("targetAmount")}</th>
    <th class="col-money">${t("monthlyContribution")}</th>
    <th class="col-narrow">${t("expectedReturn")}</th>
    <th class="col-narrow">${t("targetYear")}</th>
    <th class="col-money">${t("gapToTarget")}</th>
    <th>${t("monthsToTarget")}</th>
    <th class="col-money">${t("projectedValue")}</th>
    <th></th>
  </tr></thead><tbody>`;
  if (items.length) {
    for (const it of items) {
      const rateVal = Number(it.expected_return_annual ?? 0);
      html += `<tr data-future-id="${it.id}">
        <td><input type="text" data-field="name" value="${escapeHtml(it.name)}" /></td>
        <td class="col-money"><input type="number" step="0.01" min="0" data-field="current_amount" value="${it.current_amount || 0}" /></td>
        <td class="col-money"><input type="number" step="0.01" min="0" data-field="target_amount" value="${it.target_amount || 0}" /></td>
        <td class="col-money"><input type="number" step="0.01" min="0" data-field="monthly_contribution" value="${it.monthly_contribution || 0}" /></td>
        <td class="col-narrow"><input type="text" inputmode="decimal" class="input-rate" data-field="expected_return_annual" value="${formatRateInputValue(rateVal)}" /></td>
        <td class="col-narrow"><input type="number" min="2020" max="2100" step="1" data-field="target_year" value="${it.target_year ?? ""}" placeholder="—" /></td>
        <td class="computed col-money">${formatMoney(it.gap || 0)}</td>
        <td class="computed future-months">${futureMonthsLabel(it)}</td>
        <td class="computed col-money future-projected">${it.projected_value != null ? formatMoney(it.projected_value) : "—"}</td>
        <td><button type="button" class="btn-delete-row" data-future-id="${it.id}" aria-label="${t("deleteRow")}">×</button></td>
      </tr>`;
    }
  } else {
    html += `<tr><td colspan="10" class="empty-hint">${escapeHtml(t("noFutureInvest"))}</td></tr>`;
  }
  html += `</tbody>`;
  tableEl.innerHTML = html;
  bindFutureInvestTable();
}

let futureInvestAbort = null;

function readFutureRowPayload(row) {
  const payload = { investment_type: "other", notes: "" };
  row.querySelectorAll("[data-field]").forEach((el) => {
    const f = el.dataset.field;
    if (f === "target_year") {
      const v = el.value.trim();
      payload.target_year = v ? parseInt(v, 10) : null;
    } else if (f === "expected_return_annual") {
      payload[f] = parseNumInput(el.value);
    } else if (el.type === "number") {
      payload[f] = parseNumInput(el.value);
    } else {
      payload[f] = el.value;
    }
  });
  return payload;
}

function bindFutureInvestTable() {
  futureInvestAbort?.abort();
  futureInvestAbort = new AbortController();
  const { signal } = futureInvestAbort;
  const root = document.querySelector(".future-invest-card");
  if (root && root.dataset.futureDelegation !== "1") {
    root.dataset.futureDelegation = "1";
    root.addEventListener("click", async (e) => {
      const btn = e.target.closest(".btn-delete-row[data-future-id]");
      if (!btn) return;
      if (!confirm(t("deleteRow") + "?")) return;
      try {
        const res = await api(
          `/api/clients/${requireClient()}/future-investments/${btn.dataset.futureId}?year=${getActiveYear()}`,
          { method: "DELETE" }
        );
        await applyBalanceSheetResponse(res);
        toast(t("saved"));
      } catch (err) {
        showError(err);
      }
    });
  }
  document.querySelectorAll("#future-invest-table tr[data-future-id]").forEach((row) => {
    const id = row.dataset.futureId;
    const save = async () => {
      try {
        const res = await api(
          `/api/clients/${requireClient()}/future-investments/${id}?year=${getActiveYear()}`,
          {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(readFutureRowPayload(row)),
          }
        );
        await applyBalanceSheetResponse(res);
      } catch (e) {
        showError(e);
      }
    };
    row.querySelectorAll("input[data-field]").forEach((inp) => {
      inp.addEventListener("change", () => save(), { signal });
    });
  });
}

async function renderFuturePanel() {
  updateFutureClientBanner();
  const kpiEl = document.getElementById("future-kpi-row");
  const tableEl = document.getElementById("future-invest-table");
  if (!kpiEl || !tableEl) return;
  const cid = getActiveClientId();
  if (!cid) {
    kpiEl.innerHTML = `<p class="hint-banner error">${escapeHtml(t("selectClient"))}</p>`;
    tableEl.innerHTML = "";
    return;
  }
  if (!budget) {
    kpiEl.innerHTML = `<p class="hint-banner">${escapeHtml(t("loading"))}</p>`;
    return;
  }
  if (balanceSheetStale || !budget.balance_sheet?.future_invest_plan) {
    await syncBalanceSheet();
  }
  paintFuturePanel(budget.balance_sheet || emptyBalanceSheet());
}

async function renderBalancePanel() {
  const kpiEl = document.getElementById("balance-kpi-row");
  const assetsEl = document.getElementById("assets-table");
  const debtsEl = document.getElementById("debts-table");
  if (!kpiEl || !assetsEl || !debtsEl) return;
  try {
    await renderBalancePanelInner(kpiEl, assetsEl, debtsEl);
  } catch (err) {
    console.error(err);
    kpiEl.innerHTML = `<p class="hint-banner error">${escapeHtml(err.message || String(err))}</p>`;
  }
}

function updateBalanceClientBanner() {
  const banner = document.getElementById("balance-client-banner");
  if (!banner) return;
  const cid = getActiveClientId();
  if (!cid) {
    banner.textContent = t("balanceSelectClient");
    banner.classList.add("error");
    return;
  }
  banner.classList.remove("error");
  const name =
    budget?.client_name ||
    clientsList.find((c) => c.id === cid)?.name ||
    document.getElementById("client-select")?.selectedOptions?.[0]?.textContent ||
    `#${cid}`;
  banner.innerHTML = `<strong>${escapeHtml(t("balanceForClient"))}:</strong> ${escapeHtml(name)} · ${t("year")} ${getActiveYear()}`;
}

function paintBalancePanel(bs) {
  const kpiEl = document.getElementById("balance-kpi-row");
  const assetsEl = document.getElementById("assets-table");
  const debtsEl = document.getElementById("debts-table");
  if (!kpiEl || !assetsEl || !debtsEl) return;

  updateBalanceClientBanner();

  const cid = getActiveClientId();
  if (!cid) {
    kpiEl.innerHTML = `<p class="hint-banner error">${escapeHtml(t("selectClient"))}</p>`;
    assetsEl.innerHTML = "";
    debtsEl.innerHTML = "";
    document.getElementById("balance-payoff-card").innerHTML = "";
    return;
  }
  if (!budget) {
    kpiEl.innerHTML = `<p class="hint-banner">${escapeHtml(t("loading"))}</p>`;
    return;
  }

  bs = bs || budget.balance_sheet || emptyBalanceSheet();
  const assets = bs.assets || [];
  const debts = bs.debts || [];
  const totalAssets = Number(bs.total_assets) || 0;
  const totalDebts = Number(bs.total_debts) || 0;
  const netWorth = Number(bs.net_worth ?? totalAssets - totalDebts);

  kpiEl.innerHTML = `
    <div class="kpi-card income"><div class="label">${t("totalAssets")}</div><div class="value">${formatMoney(totalAssets)}</div></div>
    <div class="kpi-card expense"><div class="label">${t("totalDebts")}</div><div class="value">${formatMoney(totalDebts)}</div></div>
    <div class="kpi-card ${netWorth < 0 ? "deficit" : "surplus"}"><div class="label">${t("netWorth")}</div><div class="value">${formatMoney(netWorth)}</div></div>
  `;

  const hint = document.querySelector("#panel-balance > .hint-banner");
  if (hint) {
    hint.textContent = `${t("hintBalance")} — ${t("netWorthFormula")}: ${formatMoney(totalAssets)} − ${formatMoney(totalDebts)} = ${formatMoney(netWorth)}`;
  }

  renderPayoffCard(bs.payoff);

  let aHtml = `<thead><tr><th>${t("assetName")}</th><th>${t("amount")}</th><th></th></tr></thead><tbody>`;
  if (assets.length) {
  for (const a of assets) {
    aHtml += `<tr data-asset-id="${a.id}">
      <td><input type="text" data-field="name" value="${escapeHtml(a.name)}" /></td>
      <td class="col-money"><input type="number" step="0.01" data-field="amount" value="${a.amount || 0}" /></td>
      <td><button type="button" class="btn-delete-row" data-asset-id="${a.id}" aria-label="${t("deleteRow")}">×</button></td>
    </tr>`;
  }
  } else {
    aHtml += `<tr><td colspan="3" class="empty-hint">${escapeHtml(t("noAssets"))}</td></tr>`;
  }
  aHtml += `</tbody><tfoot><tr class="balance-total-row"><td><strong>${t("totalAssets")}</strong></td><td><strong>${formatMoney(totalAssets)}</strong></td><td></td></tr></tfoot>`;
  assetsEl.innerHTML = aHtml;
  let dHtml = `<thead><tr><th>${t("assetName")}</th><th class="col-money">${t("outstanding")}</th><th class="col-interest">${t("interestRate")}</th><th class="col-money">${t("interestPerMonth")}</th><th class="col-money">${t("repayPerMonth")}</th><th>${t("monthsToClear")}</th><th></th></tr></thead><tbody>`;
  const perDebt = bs.payoff?.per_debt || [];
  const perById = Object.fromEntries(perDebt.map((p) => [String(p.id), p]));
  const effectivePay = bs.payoff?.effective_monthly_payment || 0;
  if (debts.length) {
  for (const d of debts) {
    const pd = perById[String(d.id)] || {};
    const rateVal = Number(d.interest_rate_annual ?? 0);
    const principal = Number(d.amount || 0);
    const disp = computeDebtRowDisplay(
      principal,
      rateVal,
      Number(d.monthly_payment || 0),
      pd,
      effectivePay,
      bs.total_debts || 0
    );
    const rowCls = disp.monthsWarn ? "debt-row-warn" : "";
    const intTitle = `${t("interestFormula")}: ${formatMoney(disp.intMo)}`;
    const monthsTitle = disp.monthsWarn ? t("payoffInterestTooLow") : "";
    dHtml += `<tr data-debt-id="${d.id}" class="${rowCls}">
      <td><input type="text" data-field="name" value="${escapeHtml(d.name)}" /></td>
      <td class="col-money"><input type="number" step="0.01" min="0" data-field="amount" value="${d.amount || 0}" /></td>
      <td class="col-interest"><input type="text" inputmode="decimal" class="input-rate" data-field="interest_rate_annual" value="${formatRateInputValue(rateVal)}" placeholder="0" title="${t("interestRate")}" /></td>
      <td class="computed col-money debt-interest-mo" title="${escapeHtml(intTitle)}">${formatMoney(disp.intMo)}</td>
      <td class="col-money"><input type="number" step="0.01" min="0" data-field="monthly_payment" value="${d.monthly_payment || 0}" /></td>
      <td class="computed payoff-months" title="${escapeHtml(monthsTitle)}">${disp.monthsLabel}</td>
      <td><button type="button" class="btn-delete-row" data-debt-id="${d.id}" aria-label="${t("deleteRow")}">×</button></td>
    </tr>`;
  }
  } else {
    dHtml += `<tr><td colspan="7" class="empty-hint">${escapeHtml(t("noDebts"))}</td></tr>`;
  }
  const totalIntMo = bs.payoff?.total_monthly_interest || 0;
  dHtml += `</tbody><tfoot><tr class="balance-total-row"><td><strong>${t("totalDebts")}</strong></td><td class="col-money"><strong>${formatMoney(totalDebts)}</strong></td><td></td><td class="col-money"><strong>${formatMoney(totalIntMo)}</strong></td><td class="col-money"><strong>${formatMoney(bs.payoff?.total_monthly_payment || 0)}</strong></td><td></td><td></td></tr></tfoot>`;
  debtsEl.innerHTML = dHtml;

  bindBalanceAssetsTable();
  ensureDebtsTableDelegation();
  refreshAllDebtRowsLive();
  updatePayoffCardLive();
}

function isDebtTableInput(el) {
  return el && el.tagName === "INPUT" && el.hasAttribute("data-field");
}

function ensureDebtsTableDelegation() {
  const root = document.querySelector(".balance-debts-card");
  if (!root || root.dataset.delegationBound === "1") return;
  root.dataset.delegationBound = "1";
  root.addEventListener("input", (e) => {
    if (!isDebtTableInput(e.target)) return;
    const row = e.target.closest("tr[data-debt-id]");
    if (row) refreshDebtRowAndFooter();
  });
  root.addEventListener("change", (e) => {
    if (!isDebtTableInput(e.target)) return;
    const row = e.target.closest("tr[data-debt-id]");
    if (!row) return;
    refreshDebtRowAndFooter();
    saveDebtRow(row);
  });
  root.addEventListener(
    "focusout",
    (e) => {
      if (!isDebtTableInput(e.target)) return;
      if (e.target.dataset.field !== "interest_rate_annual") return;
      const row = e.target.closest("tr[data-debt-id]");
      if (row) saveDebtRow(row);
    },
    true
  );
  root.addEventListener("keydown", (e) => {
    if (e.key !== "Enter" || !isDebtTableInput(e.target)) return;
    e.preventDefault();
    e.target.blur();
  });
  root.addEventListener("click", async (e) => {
    const btn = e.target.closest(".btn-delete-row[data-debt-id]");
    if (!btn) return;
    if (!confirm(t("deleteRow") + "?")) return;
    const id = btn.dataset.debtId;
    try {
      const res = await api(`/api/clients/${requireClient()}/debts/${id}?year=${getActiveYear()}`, {
        method: "DELETE",
      });
      await applyBalanceSheetResponse(res, { forceFull: true });
    } catch (err) {
      showError(err);
    }
  });
}

function bindBalanceAssetsTable() {
  balanceAssetsAbort?.abort();
  balanceAssetsAbort = new AbortController();
  const { signal } = balanceAssetsAbort;
  document.querySelectorAll("#assets-table tr[data-asset-id]").forEach((row) => {
    const id = row.dataset.assetId;
    const timerKey = `asset-${id}`;
    const save = async () => {
      const cid = requireClient();
      const payload = { asset_type: "other", notes: "" };
      row.querySelectorAll("[data-field]").forEach((el) => {
        const f = el.dataset.field;
        payload[f] = el.type === "number" ? parseNumInput(el.value) : el.value;
      });
      try {
        const res = await api(`/api/clients/${cid}/assets/${id}?year=${getActiveYear()}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        await applyBalanceSheetResponse(res);
      } catch (e) {
        showError(e);
      }
    };
    const scheduleSave = (delay = 400) => {
      clearTimeout(balanceSaveTimers.get(timerKey));
      balanceSaveTimers.set(timerKey, setTimeout(save, delay));
    };
    row.querySelectorAll("input,select").forEach((inp) => {
      inp.addEventListener("change", () => scheduleSave(400), { signal });
    });
    row.querySelector(".btn-delete-row")?.addEventListener(
      "click",
      async () => {
        if (!confirm(t("deleteRow") + "?")) return;
        try {
          const res = await api(`/api/clients/${requireClient()}/assets/${id}?year=${getActiveYear()}`, {
            method: "DELETE",
          });
          await applyBalanceSheetResponse(res);
        } catch (e) {
          showError(e);
        }
      },
      { signal }
    );
  });
}

function updateDebtRowPreview(row, payoff, totalDebts) {
  const payload = readDebtRowPayload(row);
  const pd =
    (payoff.per_debt || []).find((p) => String(p.id) === String(row.dataset.debtId)) || {};
  syncDebtRowComputedCells(
    row,
    payload.amount,
    payload.interest_rate_annual,
    payload.monthly_payment,
    pd,
    payoff.effective_monthly_payment || 0,
    totalDebts
  );
}

function refreshAllDebtRowsLive() {
  const bs = budget?.balance_sheet || emptyBalanceSheet();
  const payoff = buildLivePayoffPreview(bs.payoff);
  const totalDebts = liveDebtsTotalsFromTable().totalDebts;
  document.querySelectorAll("#debts-table tr[data-debt-id]").forEach((row) => {
    updateDebtRowPreview(row, payoff, totalDebts);
  });
  updateDebtsTableFooterLive();
}

async function saveDebtRow(row) {
  const id = row.dataset.debtId;
  const stateKey = `debt-${id}`;
  let state = debtRowSaveState.get(stateKey);
  if (!state) {
    state = { inFlight: false, pending: false, generation: 0 };
    debtRowSaveState.set(stateKey, state);
  }
  if (state.inFlight) {
    state.pending = true;
    return;
  }
  const generation = ++state.generation;
  const payload = readDebtRowPayload(row);
  state.inFlight = true;
  try {
    const cid = requireClient();
    const res = await api(`/api/clients/${cid}/debts/${id}?year=${getActiveYear()}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (generation !== state.generation) return;
    await applyBalanceSheetResponse(res, { softDebts: true });
  } catch (e) {
    showError(e);
  } finally {
    state.inFlight = false;
    if (state.pending) {
      state.pending = false;
      saveDebtRow(row);
    }
  }
}

async function renderBalancePanelInner(kpiEl, assetsEl, debtsEl) {
  updateBalanceClientBanner();
  const cid = getActiveClientId();
  if (!cid) {
    kpiEl.innerHTML = `<p class="hint-banner error">${escapeHtml(t("selectClient"))}</p>`;
    assetsEl.innerHTML = "";
    debtsEl.innerHTML = "";
    return;
  }
  if (!budget) {
    kpiEl.innerHTML = `<p class="hint-banner">${escapeHtml(t("loading"))}</p>`;
    return;
  }
  if (balanceSheetStale || !budget.balance_sheet) {
    await syncBalanceSheet();
  }
  paintBalancePanel(budget.balance_sheet || emptyBalanceSheet());
}

function getFilledLinesForSummaryKey(summaryKey) {
  const cfg = SUMMARY_EXPAND_CONFIG[summaryKey];
  if (!cfg || !budget || !meta) return [];
  const out = [];
  const seen = new Set();
  for (const sectionId of cfg.sections) {
    const sec = meta.sections.find((s) => s.id === sectionId);
    if (!sec) continue;
    for (const line of linesForSection(sec)) {
      if (cfg.lineType && line.line_type !== cfg.lineType) continue;
      if (seen.has(line.key)) continue;
      const vals = budget.entries[line.key] || Array(12).fill(0);
      if (!vals.some((v) => v !== 0)) continue;
      seen.add(line.key);
      const summe = vals.reduce((a, b) => a + b, 0);
      out.push({
        key: line.key,
        label: `${sectionTitle(sec)} — ${lineLabel(line)}`,
        months: vals,
        summe,
        monatlich: lineMonatlich(vals),
      });
    }
  }
  out.sort((a, b) => b.summe - a.summe);
  return out;
}

function renderSummaryDetailRows(summaryKey, colCount) {
  const filled = getFilledLinesForSummaryKey(summaryKey);
  if (!filled.length) {
    return `<tr class="summary-detail summary-detail-empty" data-parent="${summaryKey}" hidden>
      <td colspan="${colCount}">${escapeHtml(t("summaryNoFilled"))}</td></tr>`;
  }
  return filled
    .map((line) => {
      let row = `<tr class="summary-detail" data-parent="${summaryKey}" hidden>`;
      row += `<td>${escapeHtml(line.label)}</td>`;
      for (let i = 0; i < 12; i++) row += `<td>${formatMoney(line.months[i])}</td>`;
      row += `<td>${formatMoney(line.summe)}</td><td>${formatMoney(line.monatlich)}</td></tr>`;
      return row;
    })
    .join("");
}

function bindSummaryTableExpand() {
  const table = document.getElementById("summary-table");
  if (!table || table.dataset.expandBound) return;
  table.dataset.expandBound = "1";
  table.addEventListener("click", (e) => {
    const row = e.target.closest("tr.summary-row-toggle");
    if (!row) return;
    const key = row.dataset.summaryKey;
    if (!key) return;
    const open = !row.classList.contains("expanded");
    table.querySelectorAll("tr.summary-row-toggle.expanded").forEach((r) => {
      if (r === row) return;
      r.classList.remove("expanded");
      const k = r.dataset.summaryKey;
      table.querySelectorAll(`tr.summary-detail[data-parent="${k}"]`).forEach((d) => {
        d.hidden = true;
      });
      const icon = r.querySelector(".summary-expand");
      if (icon) icon.textContent = "▶";
    });
    row.classList.toggle("expanded", open);
    table.querySelectorAll(`tr.summary-detail[data-parent="${key}"]`).forEach((d) => {
      d.hidden = !open;
    });
    const icon = row.querySelector(".summary-expand");
    if (icon) icon.textContent = open ? "▼" : "▶";
  });
}

function renderSummary() {
  if (!budget?.summary) return;
  const s = budget.summary;
  const rows = summaryRowsForTable(s);
  const months = getMonthLabels();
  const colCount = 15;
  let html =
    "<thead><tr><th>" +
    t("colRow") +
    "</th>" +
    months.map((m) => `<th>${m}</th>`).join("") +
    "<th>" +
    t("colSumme") +
    "</th><th>" +
    t("colMonatlich") +
    "</th></tr></thead><tbody>";
  for (const [key, data] of rows) {
    const label = t(key);
    const isDiff = key === "sumDifference";
    const canExpand = !!SUMMARY_EXPAND_CONFIG[key];
    const cls = [
      isDiff ? `difference ${data.summe < 0 ? "deficit" : "surplus"} highlight` : "",
      canExpand ? "summary-row-toggle" : "",
    ]
      .filter(Boolean)
      .join(" ");
    const expandBtn = canExpand
      ? `<span class="summary-expand" title="${escapeHtml(t("summaryShowFilled"))}">▶</span> `
      : "";
    html += `<tr class="${cls}" data-summary-key="${key}"><td>${expandBtn}${escapeHtml(label)}</td>`;
    for (let i = 0; i < 12; i++) html += `<td>${formatMoney(data.months[i])}</td>`;
    html += `<td>${formatMoney(data.summe)}</td><td>${formatMoney(data.monatlich)}</td></tr>`;
    if (canExpand) html += renderSummaryDetailRows(key, colCount);
  }
  html += "</tbody>";
  const table = document.getElementById("summary-table");
  table.innerHTML = html;
  bindSummaryTableExpand();
}

function renderPlanGrid(tabId) {
  const container = document.getElementById("plan-grids");
  if (!container) return;
  if (!meta || !budget) {
    container.innerHTML = `<p class='hint-banner'>${t('loadError')}</p>`;
    return;
  }
  const sections = meta.sections.filter((s) => s.tab === tabId);
  let html = "";
  for (const sec of sections) {
    html += `<div class="grid-wrap" data-section-id="${sec.id}" style="margin-bottom:24px"><table class="budget-grid"><caption class="plan-section-caption" style="caption-side:top;text-align:left;padding:12px;font-weight:700">${sectionTitle(sec)}</caption><thead><tr><th>${t("category")}</th>${getMonthLabels().map((m) => `<th>${m}</th>`).join("")}<th>${t("colSumme")}</th><th>${t("colMonatlich")}</th></tr></thead><tbody>`;
    for (const line of linesForSection(sec)) {
      const vals = budget.entries[line.key] || Array(12).fill(0);
      const summe = vals.reduce((a, b) => a + b, 0);
      const mon = budget.settings?.monatlich_mode === "filled"
        ? (vals.filter((v) => v !== 0).length ? summe / vals.filter((v) => v !== 0).length : 0)
        : summe / 12;
      const rowCls = line.custom ? "custom-line" : "";
      const delBtn = line.custom
        ? `<button type="button" class="btn-delete-row" data-line-key="${line.key}" title="${t("deleteRow")}">×</button> `
        : "";
      html += `<tr class="${rowCls}" data-key="${line.key}"><td>${delBtn}<span>${lineLabel(line)}</span></td>`;
      for (let m = 1; m <= 12; m++) {
        const v = vals[m - 1];
        const cellCls = v ? " has-value" : "";
        html += `<td class="${cellCls.trim()}" title="${v ? formatMoney(v) : ""}"><input type="number" step="0.01" data-month="${m}" value="${v || ""}" /></td>`;
      }
      html += `<td class="computed">${formatMoney(summe)}</td><td class="computed">${formatMoney(mon)}</td></tr>`;
    }
    const sk = sec.summary_key;
    if (sk && budget.summary.section_summaries?.[sk]) {
      const sm = budget.summary.section_summaries[sk];
      html += `<tr class="summary-row" data-summary-key="${sk}"><td>${t("sectionTotal")}: ${sectionTitle(sec)}</td>`;
      for (let i = 0; i < 12; i++) html += `<td class="computed">${formatMoney(sm.months[i])}</td>`;
      html += `<td class="computed">${formatMoney(sm.summe)}</td><td class="computed">${formatMoney(sm.monatlich)}</td></tr>`;
    }
    html += "</tbody></table></div>";
  }
  container.innerHTML = html;

  container.querySelectorAll(".plan-section-caption").forEach((cap) => {
    cap.addEventListener("click", () => {
      const sid = cap.closest(".grid-wrap")?.dataset.sectionId;
      if (sid) setAddRowTargetSection(sid);
      document.getElementById("add-row-name")?.focus();
    });
  });
  highlightAddRowTargetSection();

  container.querySelectorAll("tr[data-key]").forEach((row) => {
    row.addEventListener("click", () => {
      selectedLineKey = row.dataset.key;
      const sel = document.getElementById("bulk-line-select");
      if (sel) sel.value = selectedLineKey;
    });
  });

  container.querySelectorAll("input[type='number']").forEach((inp) => {
    inp.addEventListener("input", () => {
      const cell = inp.closest("td");
      const amount = parseFloat(inp.value) || 0;
      if (cell) {
        cell.classList.toggle("has-value", amount !== 0);
        cell.title = amount ? formatMoney(amount) : "";
      }
      const row = inp.closest("tr");
      if (row?.dataset.key) {
        const key = row.dataset.key;
        const month = parseInt(inp.dataset.month, 10);
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

  container.querySelectorAll(".btn-delete-row").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(t("deleteRow") + "?")) return;
      try {
        const res = await deleteCustomLine(btn.dataset.lineKey);
        if (res.entries) budget.entries = res.entries;
        budget.custom_lines = res.custom_lines;
        budget.summary = res.summary;
        invalidateChartsCache();
        markBalanceStale();
        populateBulkLineSelect();
        renderPlanGrid(activePlanTab);
        toast(t("saved"));
      } catch (err) {
        showError(err);
      }
    });
  });
}

async function applyBulk(startMonth, endMonth) {
  const sel = document.getElementById("bulk-line-select");
  const lineKey = sel?.value || selectedLineKey;
  if (!lineKey) {
    toast(t("chooseCategory"));
    return;
  }
  const amount = parseFloat(document.getElementById("bulk-amount").value);
  const start = startMonth ?? parseInt(document.getElementById("bulk-from-month").value, 10);
  const end = endMonth ?? parseInt(document.getElementById("bulk-to-month").value, 10);
  if (isNaN(amount)) {
    toast(t("enterAmount"));
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
  invalidateChartsCache();
  markBalanceStale();
  updatePlanGridTotals();
  const active = activePanelId();
  if (active === "panel-summary") renderSummary();
  else if (active === "panel-dashboard") await renderDashboard();
  else if (active === "panel-charts") await renderChartsPanel();
  toast(`${t("saved")}: ${formatMoney(amount)} (${start}–${end})`);
}

document.getElementById("btn-bulk-apply")?.addEventListener("click", () => applyBulk());

document.getElementById("btn-apply-all-year")?.addEventListener("click", () => applyBulk(1, 12));

document.getElementById("btn-add-row")?.addEventListener("click", () => {
  submitAddRow().catch((err) => showError(err));
});
document.getElementById("add-row-name")?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    document.getElementById("btn-add-row")?.click();
  }
});

document.getElementById("dashboard-month")?.addEventListener("change", (e) => {
  selectedMonth = parseInt(e.target.value, 10);
  renderDashboard();
});
document.getElementById("charts-month")?.addEventListener("change", (e) => {
  selectedMonth = parseInt(e.target.value, 10);
  renderChartsPanel();
});
document.getElementById("chart-period")?.addEventListener("change", renderDashboard);

document.getElementById("btn-recalculate")?.addEventListener("click", async () => {
  invalidateChartsCache();
  markBalanceStale();
  await loadBudget();
  toast(t("recalculated") || "Totals recalculated");
});

document.getElementById("btn-download")?.addEventListener("click", () => {
  document.getElementById("download-dropdown").classList.toggle("open");
});
document.addEventListener("click", (e) => {
  if (!e.target.closest("#download-dropdown, #action-dock")) {
    document.getElementById("download-dropdown")?.classList.remove("open");
  }
  if (!e.target.closest("#profile-dropdown")) {
    document.getElementById("profile-dropdown")?.classList.remove("open");
  }
});

function parseFilenameFromDisposition(header, fallback) {
  if (!header) return fallback;
  const m = /filename\*?=(?:UTF-8''|")?([^";\n]+)"?/i.exec(header);
  return m ? decodeURIComponent(m[1].trim()) : fallback;
}

async function downloadExport(kind) {
  const cid = getActiveClientId();
  const year = getActiveYear();
  if (!cid) {
    toast(t("selectClient"));
    return;
  }
  const paths = {
    excel: { url: `/api/clients/${cid}/export/excel?year=${year}`, fallback: `budget_${year}.xlsx` },
    csv: { url: `/api/clients/${cid}/export/csv?year=${year}`, fallback: `budget_${year}.csv` },
    pdf: {
      url: `/api/clients/${cid}/export/pdf?year=${year}&month=${selectedMonth}`,
      fallback: `budget_${year}.pdf`,
    },
  };
  const spec = paths[kind];
  if (!spec) return;
  try {
    const res = await fetch(spec.url, FETCH_OPTS);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(text || `Export failed (${res.status})`);
    }
    const blob = await res.blob();
    const filename = parseFilenameFromDisposition(
      res.headers.get("Content-Disposition"),
      spec.fallback
    );
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(a.href);
    toast(t("saved"));
  } catch (err) {
    showError(err);
  }
}

document.getElementById("download-menu")?.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-action]");
  if (!btn) return;
  document.getElementById("download-dropdown").classList.remove("open");
  const action = btn.dataset.action;
  if (action === "export-excel") await downloadExport("excel");
  else if (action === "export-csv") await downloadExport("csv");
  else if (action === "export-pdf") await downloadExport("pdf");
});


document.getElementById("panel-cancel")?.addEventListener("click", closePanel);
document.getElementById("overlay")?.addEventListener("click", closePanel);

async function renderClientsPanel() {
  const data = await api("/api/clients");
  clientsList = data.clients || [];
  clientsCacheTime = Date.now();
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
      const sel = document.getElementById("currency-select");
      if (sel) populateCurrencySelect(sel);
      if (meta) initPlanTabs();
      await refreshUiLanguage();
      updateAddRowTargetHint();
    });
  });
  applyTranslations();
  updateAddRowTargetHint();
}

function updateBarChartLanguage() {
  if (!barChart) return;
  barChart.data.labels = getMonthLabels();
  barChart.data.datasets[0].label = t("revenue");
  barChart.data.datasets[1].label = t("expenses");
  barChart.update("none");
}

async function refreshUiLanguage() {
  applyTranslations();
  fillMonthSelects();
  if (!budget) return;
  updateCurrencyChrome();
  invalidateChartsCache();
  renderSummary();
  updatePlanGridTotals();
  updateBarChartLanguage();
  const panel = activePanelId();
  if (panel === "panel-dashboard") await renderDashboard();
  else if (panel === "panel-charts") await renderChartsPanel();
  else if (panel === "panel-plan") renderPlanGrid(activePlanTab);
  else if (panel === "panel-summary") renderSummary();
  else if (panel === "panel-balance") await renderBalancePanel();
  else if (panel === "panel-future") await renderFuturePanel();
  else if (panel === "panel-clients") await renderClientsPanel();
}

async function refreshCurrencyDisplay() {
  await refreshUiLanguage();
}

function initCurrency() {
  const sel = document.getElementById("currency-select");
  if (!sel) return;
  populateCurrencySelect(sel);
  updateCurrencyChrome();
  if (sel.dataset.bound) return;
  sel.dataset.bound = "1";
  sel.addEventListener("change", async () => {
    setCurrency(sel.value);
    await refreshCurrencyDisplay();
  });
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
    clientsCacheTime = 0;
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
  invalidateChartsCache();
  markBalanceStale();
  await loadBudget();
});

document.getElementById("client-select")?.addEventListener("change", async (e) => {
  const id = parseInt(e.target.value, 10);
  if (!id) return;
  activeClientId = id;
  localStorage.setItem("activeClientId", String(activeClientId));
  invalidateChartsCache();
  markBalanceStale();
  await loadBudget();
});

function boot() {
  fillMonthSelects();
  initYearSelect();
  initTabs();
  initCurrency();
  initLanguage();
  initBalanceForms();
  initHeaderClientsButton();
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
      toast(t('loadError'));
    });
}

async function startApplication() {
  initAuthUI();
  const authed = await checkAuthOnLoad();
  if (authed) {
    appBooted = true;
    await boot();
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", startApplication);
} else {
  startApplication();
}
