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
  const rows = Array.from(document.querySelectorAll("#detection-table tbody tr"));
  const filter = () => {
    const symbolValue = (symbol?.value || "").trim();
    const selectorValue = selector?.value || "";
    for (const row of rows) {
      const symbolMatch = !symbolValue || (row.dataset.symbol || "").includes(symbolValue);
      const selectorMatch = !selectorValue || (row.dataset.selectors || "").split(" ").includes(selectorValue);
      row.hidden = !(symbolMatch && selectorMatch);
    }
  };
  symbol?.addEventListener("input", filter);
  selector?.addEventListener("change", filter);

  for (const button of document.querySelectorAll(".fundamental-toggle")) {
    button.addEventListener("click", () => {
      const detail = button.parentElement?.querySelector(".fundamental-detail");
      if (!detail) return;
      detail.hidden = !detail.hidden;
      button.textContent = detail.hidden ? "ファンダ分析" : "閉じる";
    });
  }
})();
