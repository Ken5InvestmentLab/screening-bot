(() => {
  const THEME_KEY = "weakEarlyBetaTheme:v1";
  const PAGE_SIZE = 20;
  const root = document.documentElement;
  const themeButton = document.getElementById("theme-toggle");

  const currentTheme = () => root.dataset.theme === "dark" ? "dark" : "light";
  const applyTheme = (theme, persist = false) => {
    const normalized = theme === "dark" ? "dark" : "light";
    if (normalized === "dark") root.dataset.theme = "dark";
    else root.removeAttribute("data-theme");
    if (themeButton) {
      themeButton.textContent = normalized === "dark" ? "ライトモード" : "ダークモード";
      themeButton.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
    }
    if (persist) {
      try { localStorage.setItem(THEME_KEY, normalized); } catch (_error) {}
    }
  };
  applyTheme(currentTheme());
  themeButton?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark", true);
  });

  const symbol = document.getElementById("symbol-filter");
  const selector = document.getElementById("selector-filter");
  const dateFrom = document.getElementById("history-date-from");
  const dateTo = document.getElementById("history-date-to");
  const clear = document.getElementById("clear-search");
  const resultCount = document.getElementById("search-result-count");
  const loadMore = document.getElementById("history-load-more");
  const collapse = document.getElementById("history-collapse");
  const rows = Array.from(document.querySelectorAll("#detection-table tbody tr"));
  const normalize = (value) => String(value || "").normalize("NFKC").trim().toLowerCase();
  let visibleLimit = PAGE_SIZE;

  const initialQuery = new URLSearchParams(window.location.search).get("q");
  if (symbol && initialQuery) symbol.value = initialQuery;

  const filter = ({ resetLimit = false } = {}) => {
    if (resetLimit) visibleLimit = PAGE_SIZE;
    const symbolValue = normalize(symbol?.value);
    const selectorValue = selector?.value || "";
    const fromValue = dateFrom?.value || "";
    const toValue = dateTo?.value || "";
    const matchedRows = rows.filter((row) => {
      const searchTarget = normalize(row.dataset.search || row.dataset.symbol);
      const signalDate = row.dataset.date || "";
      return (!symbolValue || searchTarget.includes(symbolValue))
        && (!selectorValue || (row.dataset.selectors || "").split(" ").includes(selectorValue))
        && (!fromValue || signalDate >= fromValue)
        && (!toValue || signalDate <= toValue);
    });
    const matched = new Set(matchedRows);
    const shown = Math.min(visibleLimit, matchedRows.length);
    let shownIndex = 0;
    for (const row of rows) {
      const display = matched.has(row) && shownIndex < shown;
      if (matched.has(row)) shownIndex += 1;
      row.hidden = !display;
    }
    if (resultCount) {
      resultCount.textContent = matchedRows.length > shown
        ? `${shown.toLocaleString("ja-JP")} / ${matchedRows.length.toLocaleString("ja-JP")}件を表示`
        : `${matchedRows.length.toLocaleString("ja-JP")}件を表示`;
    }
    if (clear) clear.disabled = !symbolValue && !selectorValue && !fromValue && !toValue;
    if (loadMore) loadMore.hidden = shown >= matchedRows.length;
    if (collapse) collapse.hidden = visibleLimit <= PAGE_SIZE || matchedRows.length <= PAGE_SIZE;
  };

  for (const control of [symbol, dateFrom, dateTo]) {
    control?.addEventListener("input", () => filter({ resetLimit: true }));
    control?.addEventListener("change", () => filter({ resetLimit: true }));
  }
  symbol?.addEventListener("search", () => filter({ resetLimit: true }));
  selector?.addEventListener("change", () => filter({ resetLimit: true }));
  clear?.addEventListener("click", () => {
    if (symbol) symbol.value = "";
    if (selector) selector.value = "";
    if (dateFrom) dateFrom.value = "";
    if (dateTo) dateTo.value = "";
    filter({ resetLimit: true });
    symbol?.focus();
  });
  loadMore?.addEventListener("click", () => {
    visibleLimit += PAGE_SIZE;
    filter();
  });
  collapse?.addEventListener("click", () => {
    visibleLimit = PAGE_SIZE;
    filter();
    document.querySelector(".history-details")?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
  filter();

  for (const table of document.querySelectorAll("table[data-paginated-table]")) {
    const tableRows = Array.from(table.querySelectorAll("tbody tr"));
    const pagination = table.closest(".table-wrap")?.nextElementSibling;
    if (!pagination?.classList.contains("table-pagination")) continue;
    const moreButton = pagination.querySelector(".table-load-more");
    const resetButton = pagination.querySelector(".table-collapse");
    const count = pagination.querySelector(".table-result-count");
    let limit = PAGE_SIZE;
    const renderPage = () => {
      tableRows.forEach((row, index) => { row.hidden = index >= limit; });
      const shown = Math.min(limit, tableRows.length);
      if (count) count.textContent = `${shown.toLocaleString("ja-JP")} / ${tableRows.length.toLocaleString("ja-JP")}件を表示`;
      if (moreButton) moreButton.hidden = shown >= tableRows.length;
      if (resetButton) resetButton.hidden = limit <= PAGE_SIZE || tableRows.length <= PAGE_SIZE;
    };
    moreButton?.addEventListener("click", () => { limit += PAGE_SIZE; renderPage(); });
    resetButton?.addEventListener("click", () => { limit = PAGE_SIZE; renderPage(); });
    renderPage();
  }

  for (const button of document.querySelectorAll(".fundamental-toggle")) {
    button.addEventListener("click", () => {
      const detail = button.parentElement?.querySelector(".fundamental-detail");
      if (!detail) return;
      detail.hidden = !detail.hidden;
      button.textContent = detail.hidden ? "ファンダ分析" : "閉じる";
    });
  }
})();
