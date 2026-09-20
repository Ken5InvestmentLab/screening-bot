(() => {
  const root = document.documentElement;
  const saved = localStorage.getItem("weakEarlyBetaTheme");
  if (saved === "dark") root.dataset.theme = "dark";
  document.getElementById("theme-toggle")?.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    root.dataset.theme = next;
    localStorage.setItem("weakEarlyBetaTheme", next);
  });

  const symbol = document.getElementById("symbol-filter");
  const selector = document.getElementById("selector-filter");
  const clear = document.getElementById("clear-search");
  const resultCount = document.getElementById("search-result-count");
  const normalize = (value) => String(value || "").normalize("NFKC").trim().toLowerCase();
  const initialQuery = new URLSearchParams(window.location.search).get("q");
  if (symbol && initialQuery) symbol.value = initialQuery;
  const filter = () => {
    const rows = Array.from(document.querySelectorAll("#detection-table tbody tr"));
    const symbolValue = normalize(symbol?.value);
    const selectorValue = selector?.value || "";
    let visible = 0;
    for (const row of rows) {
      const searchTarget = normalize(row.dataset.search || row.dataset.symbol);
      const symbolMatch = !symbolValue || searchTarget.includes(symbolValue);
      const selectorMatch = !selectorValue || (row.dataset.selectors || "").split(" ").includes(selectorValue);
      const matched = symbolMatch && selectorMatch;
      row.hidden = !matched;
      row.style.display = matched ? "" : "none";
      if (matched) visible += 1;
    }
    if (resultCount) resultCount.textContent = `${visible.toLocaleString("ja-JP")}件を表示`;
    if (clear) clear.disabled = !symbolValue && !selectorValue;
  };
  symbol?.addEventListener("input", filter);
  symbol?.addEventListener("search", filter);
  selector?.addEventListener("change", filter);
  clear?.addEventListener("click", () => {
    if (symbol) symbol.value = "";
    if (selector) selector.value = "";
    filter();
    symbol?.focus();
  });
  filter();

  for (const button of document.querySelectorAll(".fundamental-toggle")) {
    button.addEventListener("click", () => {
      const detail = button.parentElement?.querySelector(".fundamental-detail");
      if (!detail) return;
      detail.hidden = !detail.hidden;
      button.textContent = detail.hidden ? "ファンダ分析" : "閉じる";
    });
  }
})();
