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
  const loadMore = document.getElementById("daily-load-more");
  if (!select || rows.length === 0) return;
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

  const applyFilter = (resetLimit = true) => {
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
  loadMore?.addEventListener("click", () => {
    visibleLimit += pageSize;
    applyFilter(false);
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
  applyFilter(true);
})();
