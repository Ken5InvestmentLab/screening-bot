(() => {
  const select = document.getElementById("daily-date-filter");
  const rows = Array.from(document.querySelectorAll("[data-detection-row]"));
  const count = document.getElementById("daily-visible-count");
  const empty = document.getElementById("daily-empty-message");
  if (!select || rows.length === 0) return;

  const applyFilter = () => {
    const selectedDate = select.value || select.dataset.defaultDate;
    let visible = 0;
    rows.forEach((row) => {
      const shouldShow = row.dataset.date === selectedDate;
      row.classList.toggle("is-hidden", !shouldShow);
      if (shouldShow) visible += 1;
    });
    if (count) count.textContent = String(visible);
    if (empty) empty.hidden = visible !== 0;
  };

  select.addEventListener("change", applyFilter);
  select.addEventListener("input", applyFilter);
  applyFilter();
})();
