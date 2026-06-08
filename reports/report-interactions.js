(() => {
  const select = document.getElementById("daily-date-filter");
  const rows = Array.from(document.querySelectorAll("[data-detection-row]"));
  const count = document.getElementById("daily-visible-count");
  const empty = document.getElementById("daily-empty-message");
  const dateFrom = document.getElementById("search-date-from");
  const dateTo = document.getElementById("search-date-to");
  const symbolInput = document.getElementById("search-symbol");
  const starMin = document.getElementById("search-star-min");
  const starMax = document.getElementById("search-star-max");
  const priceMin = document.getElementById("search-price-min");
  const priceMax = document.getElementById("search-price-max");
  const indicatorInputs = Array.from(document.querySelectorAll("[data-indicator-filter]"));
  const reset = document.getElementById("search-reset");
  if (!select || rows.length === 0) return;

  const normalizeSymbol = (value) => String(value || "").replace(/[^0-9A-Za-z]/g, "").toUpperCase();
  const numericValue = (element) => {
    const value = String(element?.value || "").trim();
    if (value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) ? number : null;
  };

  const applyFilter = () => {
    const from = String(dateFrom?.value || "");
    const to = String(dateTo?.value || "");
    const symbol = normalizeSymbol(symbolInput?.value);
    const minStar = numericValue(starMin);
    const maxStar = numericValue(starMax);
    const minPrice = numericValue(priceMin);
    const maxPrice = numericValue(priceMax);
    const requiredConditions = indicatorInputs
      .filter((input) => input.checked)
      .map((input) => input.value);
    let visible = 0;
    rows.forEach((row) => {
      const rowDate = row.dataset.date || "";
      const rowSymbol = normalizeSymbol(row.dataset.symbol);
      const rowStar = Number(row.dataset.star);
      const rowPrice = Number(row.dataset.price);
      const rowConditions = new Set(String(row.dataset.conditions || "").split(/\s+/).filter(Boolean));
      let shouldShow = true;
      if (from && rowDate < from) shouldShow = false;
      if (to && rowDate > to) shouldShow = false;
      if (symbol && !rowSymbol.includes(symbol)) shouldShow = false;
      if (minStar !== null && (!Number.isFinite(rowStar) || rowStar < minStar)) shouldShow = false;
      if (maxStar !== null && (!Number.isFinite(rowStar) || rowStar > maxStar)) shouldShow = false;
      if (minPrice !== null && (!Number.isFinite(rowPrice) || rowPrice < minPrice)) shouldShow = false;
      if (maxPrice !== null && (!Number.isFinite(rowPrice) || rowPrice > maxPrice)) shouldShow = false;
      if (requiredConditions.some((condition) => !rowConditions.has(condition))) shouldShow = false;
      row.classList.toggle("is-hidden", !shouldShow);
      if (shouldShow) visible += 1;
    });
    if (count) count.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  };

  const applySelectedDate = () => {
    if (dateFrom) dateFrom.value = select.value || select.dataset.defaultDate || "";
    if (dateTo) dateTo.value = select.value || select.dataset.defaultDate || "";
    applyFilter();
  };

  select.addEventListener("change", applySelectedDate);
  select.addEventListener("input", applySelectedDate);
  [
    dateFrom,
    dateTo,
    symbolInput,
    starMin,
    starMax,
    priceMin,
    priceMax,
    ...indicatorInputs,
  ].filter(Boolean).forEach((element) => {
    element.addEventListener("change", applyFilter);
    element.addEventListener("input", applyFilter);
  });
  reset?.addEventListener("click", () => {
    const defaultDate = select.dataset.defaultDate || select.value || "";
    select.value = defaultDate;
    if (dateFrom) dateFrom.value = defaultDate;
    if (dateTo) dateTo.value = defaultDate;
    if (symbolInput) symbolInput.value = "";
    if (starMin) starMin.value = "";
    if (starMax) starMax.value = "";
    if (priceMin) priceMin.value = "";
    if (priceMax) priceMax.value = "";
    indicatorInputs.forEach((input) => {
      input.checked = false;
    });
    applyFilter();
  });
  applyFilter();
})();
