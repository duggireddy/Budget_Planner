/** Display currency for budget amounts (format only; no FX conversion). */
const CURRENCY_STORAGE_KEY = "budget_currency";
const DEFAULT_CURRENCY = "EUR";

const POPULAR_CURRENCIES = [
  "EUR",
  "USD",
  "INR",
  "GBP",
  "CHF",
  "JPY",
  "CAD",
  "AUD",
  "CNY",
  "SGD",
  "AED",
  "SAR",
  "BRL",
  "MXN",
  "ZAR",
  "KRW",
  "HKD",
  "NZD",
  "SEK",
  "NOK",
  "DKK",
  "PLN",
  "CZK",
  "HUF",
  "TRY",
  "THB",
  "MYR",
  "PHP",
  "IDR",
  "VND",
  "PKR",
  "BDT",
  "EGP",
  "NGN",
  "KES",
  "ILS",
  "RON",
  "BGN",
  "HRK",
  "UAH",
];

const FALLBACK_CURRENCIES = [
  ...POPULAR_CURRENCIES,
  "ARS",
  "CLP",
  "COP",
  "PEN",
  "QAR",
  "KWD",
  "BHD",
  "OMR",
  "JOD",
  "LKR",
  "NPR",
  "TWD",
  "ISK",
];

const CURRENCY_LOCALE_MAP = {
  EUR: "de-DE",
  USD: "en-US",
  INR: "en-IN",
  GBP: "en-GB",
  CHF: "de-CH",
  JPY: "ja-JP",
  CAD: "en-CA",
  AUD: "en-AU",
  CNY: "zh-CN",
  BRL: "pt-BR",
  MXN: "es-MX",
  KRW: "ko-KR",
  AED: "ar-AE",
  SAR: "ar-SA",
  ZAR: "en-ZA",
  RUB: "ru-RU",
  TRY: "tr-TR",
  PLN: "pl-PL",
  SEK: "sv-SE",
  NOK: "nb-NO",
  DKK: "da-DK",
  HKD: "zh-HK",
  SGD: "en-SG",
  NZD: "en-NZ",
  THB: "th-TH",
  PHP: "en-PH",
  IDR: "id-ID",
  VND: "vi-VN",
  PKR: "ur-PK",
  BDT: "bn-BD",
  ILS: "he-IL",
};

function getAllCurrencyCodes() {
  try {
    if (typeof Intl !== "undefined" && typeof Intl.supportedValuesOf === "function") {
      return Intl.supportedValuesOf("currency");
    }
  } catch (_) {
    /* ignore */
  }
  return FALLBACK_CURRENCIES;
}

function getCurrency() {
  const stored = localStorage.getItem(CURRENCY_STORAGE_KEY);
  if (stored && getAllCurrencyCodes().includes(stored)) return stored;
  return DEFAULT_CURRENCY;
}

function setCurrency(code) {
  localStorage.setItem(CURRENCY_STORAGE_KEY, code);
}

function currencyDisplayLocale() {
  const uiLang = localStorage.getItem("budget_lang") || "en";
  const mapped = CURRENCY_LOCALE_MAP[getCurrency()];
  if (mapped) return mapped;
  return uiLang === "de" ? "de-DE" : "en-US";
}

function formatMoney(n) {
  const value = n ?? 0;
  try {
    return new Intl.NumberFormat(currencyDisplayLocale(), {
      style: "currency",
      currency: getCurrency(),
    }).format(value);
  } catch {
    return `${Number(value).toFixed(2)} ${getCurrency()}`;
  }
}

function getCurrencySymbol() {
  try {
    const parts = new Intl.NumberFormat(currencyDisplayLocale(), {
      style: "currency",
      currency: getCurrency(),
      currencyDisplay: "narrowSymbol",
    }).formatToParts(0);
    const sym = parts.find((p) => p.type === "currency");
    return sym?.value || getCurrency();
  } catch {
    return getCurrency();
  }
}

function currencyLabel(code, uiLocale) {
  try {
    const dn = new Intl.DisplayNames([uiLocale], { type: "currency" });
    const name = dn.of(code);
    return name ? `${code} — ${name}` : code;
  } catch {
    return code;
  }
}

function populateCurrencySelect(selectEl) {
  if (!selectEl) return;
  const uiLocale = (localStorage.getItem("budget_lang") || "en") === "de" ? "de" : "en";
  const all = getAllCurrencyCodes();
  const popularSet = new Set(POPULAR_CURRENCIES);
  const popular = POPULAR_CURRENCIES.filter((c) => all.includes(c));
  const rest = all
    .filter((c) => !popularSet.has(c))
    .sort((a, b) => currencyLabel(a, uiLocale).localeCompare(currencyLabel(b, uiLocale), uiLocale));

  const opt = (code) => `<option value="${code}">${escapeCurrencyHtml(currencyLabel(code, uiLocale))}</option>`;
  let html = `<optgroup label="${escapeCurrencyHtml(uiLocale === "de" ? "Häufig" : "Popular")}">`;
  html += popular.map(opt).join("");
  html += `</optgroup><optgroup label="${escapeCurrencyHtml(uiLocale === "de" ? "Alle Währungen" : "All currencies")}">`;
  html += rest.map(opt).join("");
  html += "</optgroup>";
  selectEl.innerHTML = html;
  selectEl.value = getCurrency();
  if (!selectEl.value) selectEl.value = DEFAULT_CURRENCY;
}

function escapeCurrencyHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function updateCurrencyChrome() {
  const logo = document.getElementById("logo-symbol");
  if (logo) logo.textContent = getCurrencySymbol();
  const bulk = document.getElementById("bulk-amount");
  if (bulk) bulk.placeholder = `${getCurrencySymbol()} 0.00`;
  document.documentElement.dataset.currency = getCurrency();
}
