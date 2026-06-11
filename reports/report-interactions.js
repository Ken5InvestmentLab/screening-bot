(() => {
  const STORAGE_KEY = "megaReportTheme:v1";
  const root = document.documentElement;
  const buttons = Array.from(document.querySelectorAll("[data-theme-toggle]"));

  const readTheme = () => {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      return value === "dark" || value === "light" ? value : "light";
    } catch (_error) {
      return "light";
    }
  };

  const writeTheme = (theme) => {
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch (_error) {
      // Theme switching should keep working even when storage is unavailable.
    }
  };

  const applyTheme = (theme, persist = false) => {
    const normalized = theme === "dark" ? "dark" : "light";
    if (normalized === "dark") {
      root.dataset.theme = "dark";
    } else {
      root.removeAttribute("data-theme");
    }
    buttons.forEach((button) => {
      button.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
      button.setAttribute(
        "aria-label",
        normalized === "dark" ? "ライトモードに切り替える" : "ダークモードに切り替える"
      );
      const label = button.querySelector(".theme-toggle-label");
      if (label) label.textContent = normalized === "dark" ? "ライト" : "ダーク";
    });
    if (persist) writeTheme(normalized);
  };

  applyTheme(readTheme(), false);
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const nextTheme = root.dataset.theme === "dark" ? "light" : "dark";
      applyTheme(nextTheme, true);
    });
  });
})();

(() => {
  const select = document.getElementById("daily-date-filter");
  const rows = Array.from(document.querySelectorAll("[data-detection-row]"));
  const count = document.getElementById("daily-visible-count");
  const total = document.getElementById("daily-total-count");
  const empty = document.getElementById("daily-empty-message");
  const dateFrom = document.getElementById("search-date-from");
  const dateTo = document.getElementById("search-date-to");
  const symbolInput = document.getElementById("search-symbol");
  const starMin = document.getElementById("search-star-min");
  const starMax = document.getElementById("search-star-max");
  const priceMin = document.getElementById("search-price-min");
  const priceMax = document.getElementById("search-price-max");
  const modeInputs = Array.from(document.querySelectorAll("[data-mode-filter]"));
  const indicatorInputs = Array.from(document.querySelectorAll("[data-indicator-filter]"));
  const reset = document.getElementById("search-reset");
  const persistToggle = document.getElementById("search-persist-toggle");
  const loadMore = document.getElementById("daily-load-more");
  if (!select || rows.length === 0) return;
  const STORAGE_KEY = "megaReportDailySearchPrefs:v1";
  const configuredPageSize = Number(select.dataset.pageSize || 100);
  const pageSize = Number.isFinite(configuredPageSize) ? Math.max(20, configuredPageSize) : 100;
  let visibleLimit = pageSize;

  const normalizeSymbol = (value) => String(value || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  const numericValue = (element) => {
    const value = String(element?.value || "").trim();
    if (value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const readSearchPrefs = () => {
    try {
      const raw = window.localStorage.getItem(STORAGE_KEY);
      if (!raw) return null;
      const prefs = JSON.parse(raw);
      return prefs && typeof prefs === "object" && prefs.enabled ? prefs : null;
    } catch (_error) {
      return null;
    }
  };

  const clearSearchPrefs = () => {
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch (_error) {
      // Keep search usable even when localStorage is unavailable.
    }
  };

  const writeSearchPrefs = () => {
    if (!persistToggle?.checked) return;
    const prefs = {
      enabled: true,
      version: 1,
      symbol: String(symbolInput?.value || ""),
      starMin: String(starMin?.value || ""),
      starMax: String(starMax?.value || ""),
      priceMin: String(priceMin?.value || ""),
      priceMax: String(priceMax?.value || ""),
      modes: modeInputs.filter((input) => input.checked).map((input) => input.value),
      indicators: indicatorInputs.filter((input) => input.checked).map((input) => input.value),
    };
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
    } catch (_error) {
      // Keep search usable even when localStorage is unavailable.
    }
  };

  const setSelectValue = (element, value) => {
    if (!element) return;
    const candidate = String(value || "");
    const hasOption = Array.from(element.options || []).some((option) => option.value === candidate);
    element.value = candidate === "" || hasOption ? candidate : "";
  };

  const restoreSearchPrefs = (prefs) => {
    if (!prefs) return;
    if (persistToggle) persistToggle.checked = true;
    const defaultDate = select.dataset.defaultDate || "";
    if (defaultDate) select.value = defaultDate;
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    if (symbolInput) symbolInput.value = String(prefs.symbol || "");
    setSelectValue(starMin, prefs.starMin);
    setSelectValue(starMax, prefs.starMax);
    if (priceMin) priceMin.value = String(prefs.priceMin || "");
    if (priceMax) priceMax.value = String(prefs.priceMax || "");
    const savedModes = new Set(Array.isArray(prefs.modes) ? prefs.modes.map(String) : []);
    const savedIndicators = new Set(Array.isArray(prefs.indicators) ? prefs.indicators.map(String) : []);
    modeInputs.forEach((input) => {
      input.checked = savedModes.has(input.value);
    });
    indicatorInputs.forEach((input) => {
      input.checked = savedIndicators.has(input.value);
    });
  };

  const applyFilter = (resetLimit = true, persist = true) => {
    if (resetLimit) visibleLimit = pageSize;
    const selectedDate = String(select.value || "");
    const from = String(dateFrom?.value || "");
    const to = String(dateTo?.value || "");
    const useCustomDateRange = Boolean(from || to);
    const symbol = normalizeSymbol(symbolInput?.value);
    const minStar = numericValue(starMin);
    const maxStar = numericValue(starMax);
    const minPrice = numericValue(priceMin);
    const maxPrice = numericValue(priceMax);
    const selectedModes = modeInputs
      .filter((input) => input.checked)
      .map((input) => input.value);
    const requiredConditions = indicatorInputs
      .filter((input) => input.checked)
      .map((input) => input.value);
    let matched = 0;
    let rendered = 0;
    rows.forEach((row) => {
      const rowDate = row.dataset.date || "";
      const rowSymbol = normalizeSymbol(row.dataset.symbol);
      const rowStar = Number(row.dataset.star);
      const rowPrice = row.dataset.price === "" ? NaN : Number(row.dataset.price);
      const rowConditions = new Set(String(row.dataset.conditions || "").split(/\s+/).filter(Boolean));
      const rowModes = new Set(String(row.dataset.modes || "").split(/\s+/).filter(Boolean));
      let shouldShow = true;
      if (useCustomDateRange) {
        if (from && rowDate < from) shouldShow = false;
        if (to && rowDate > to) shouldShow = false;
      } else if (selectedDate && rowDate !== selectedDate) {
        shouldShow = false;
      }
      if (symbol && !rowSymbol.includes(symbol)) shouldShow = false;
      if (minStar !== null && (!Number.isFinite(rowStar) || rowStar < minStar)) shouldShow = false;
      if (maxStar !== null && (!Number.isFinite(rowStar) || rowStar > maxStar)) shouldShow = false;
      if (minPrice !== null && (!Number.isFinite(rowPrice) || rowPrice < minPrice)) shouldShow = false;
      if (maxPrice !== null && (!Number.isFinite(rowPrice) || rowPrice > maxPrice)) shouldShow = false;
      if (selectedModes.length > 0 && !selectedModes.some((mode) => rowModes.has(mode))) shouldShow = false;
      if (requiredConditions.some((condition) => !rowConditions.has(condition))) shouldShow = false;
      const shouldRender = shouldShow && rendered < visibleLimit;
      row.classList.toggle("is-hidden", !shouldRender);
      if (shouldShow) matched += 1;
      if (shouldRender) rendered += 1;
    });
    if (count) count.textContent = String(rendered);
    if (total) total.textContent = String(matched);
    if (empty) empty.hidden = matched !== 0;
    if (loadMore) {
      const remaining = matched - rendered;
      loadMore.hidden = remaining <= 0;
      loadMore.textContent = remaining > 0
        ? `さらに${Math.min(pageSize, remaining)}件表示`
        : "さらに表示";
    }
    if (persist) writeSearchPrefs();
  };

  const applySelectedDate = () => {
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    applyFilter(true);
  };

  select.addEventListener("change", applySelectedDate);
  select.addEventListener("input", applySelectedDate);
  [dateFrom, dateTo].filter(Boolean).forEach((element) => {
    element.addEventListener("change", () => {
      select.value = "";
      applyFilter(true);
    });
    element.addEventListener("input", () => {
      select.value = "";
      applyFilter(true);
    });
  });
  [
    symbolInput,
    starMin,
    starMax,
    priceMin,
    priceMax,
    ...modeInputs,
    ...indicatorInputs,
  ].filter(Boolean).forEach((element) => {
    element.addEventListener("change", applyFilter);
    element.addEventListener("input", applyFilter);
  });
  persistToggle?.addEventListener("change", () => {
    if (persistToggle.checked) {
      writeSearchPrefs();
    } else {
      clearSearchPrefs();
    }
  });
  loadMore?.addEventListener("click", () => {
    visibleLimit += pageSize;
    applyFilter(false, false);
  });
  reset?.addEventListener("click", () => {
    const defaultDate = select.dataset.defaultDate || "";
    select.value = defaultDate;
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    if (symbolInput) symbolInput.value = "";
    if (starMin) starMin.value = "";
    if (starMax) starMax.value = "";
    if (priceMin) priceMin.value = "";
    if (priceMax) priceMax.value = "";
    modeInputs.forEach((input) => {
      input.checked = false;
    });
    indicatorInputs.forEach((input) => {
      input.checked = false;
    });
    applyFilter(true);
  });
  const savedPrefs = readSearchPrefs();
  if (savedPrefs) {
    restoreSearchPrefs(savedPrefs);
  } else if (persistToggle) {
    persistToggle.checked = false;
  }
  applyFilter(true, false);
})();

(() => {
  const rows = Array.from(document.querySelectorAll("[data-confirmed-row]"));
  const button = document.getElementById("confirmed-load-more");
  const visibleCount = document.getElementById("confirmed-visible-count");
  const totalCount = document.getElementById("confirmed-total-count");
  if (!button || rows.length === 0) return;
  const configuredPageSize = Number(button.dataset.pageSize || 10);
  const pageSize = Number.isFinite(configuredPageSize) ? Math.max(1, configuredPageSize) : 10;
  let visibleLimit = pageSize;

  const render = () => {
    let rendered = 0;
    rows.forEach((row, index) => {
      const shouldShow = index < visibleLimit;
      row.classList.toggle("is-hidden", !shouldShow);
      if (shouldShow) rendered += 1;
    });
    if (visibleCount) visibleCount.textContent = String(rendered);
    if (totalCount) totalCount.textContent = String(rows.length);
    const remaining = rows.length - rendered;
    button.hidden = remaining <= 0;
    button.textContent = remaining > 0
      ? `さらに${Math.min(pageSize, remaining)}件表示`
      : "さらに表示";
  };

  button.addEventListener("click", () => {
    visibleLimit += pageSize;
    render();
  });
  render();
})();

(() => {
  const buttons = Array.from(document.querySelectorAll("[data-fundamental-toggle]"));
  if (buttons.length === 0) return;
  const pairs = buttons.map((button) => {
    const container = button.closest(".symbol-actions");
    const detail = container?.querySelector(".fundamental-detail");
    const closeButton = detail?.querySelector(".fundamental-close");
    return detail ? { button, closeButton, detail } : null;
  }).filter(Boolean);
  const render = ({ button, detail }) => {
    const expanded = !detail.hidden;
    button.setAttribute("aria-expanded", expanded ? "true" : "false");
    button.textContent = expanded ? "閉じる" : "ファンダ分析";
  };
  const closePair = (pair) => {
    pair.detail.hidden = true;
    render(pair);
  };
  pairs.forEach((pair) => {
    const { button, detail } = pair;
    button.addEventListener("click", () => {
      const shouldOpen = detail.hidden;
      pairs.forEach((other) => {
        if (other !== pair) closePair(other);
      });
      detail.hidden = !shouldOpen;
      render(pair);
    });
    pair.closeButton?.addEventListener("click", () => {
      closePair(pair);
    });
    render(pair);
  });
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    if (target.closest(".fundamental-detail") || target.closest("[data-fundamental-toggle]")) return;
    pairs.forEach(closePair);
  });
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    pairs.forEach(closePair);
  });
})();

(() => {
  const buttons = Array.from(document.querySelectorAll(".mobile-row-toggle"));
  if (buttons.length === 0) return;
  buttons.forEach((button) => {
    const row = button.closest("tr");
    if (!row) return;
    const render = () => {
      const expanded = row.classList.contains("mobile-details-open");
      button.setAttribute("aria-expanded", expanded ? "true" : "false");
      button.textContent = expanded ? "閉じる" : "詳細を見る";
    };
    button.addEventListener("click", () => {
      row.classList.toggle("mobile-details-open");
      render();
    });
    render();
  });
})();
