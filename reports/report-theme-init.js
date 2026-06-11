(() => {
  const STORAGE_KEY = "megaReportTheme:v1";
  try {
    const theme = window.localStorage.getItem(STORAGE_KEY);
    if (theme === "dark") {
      document.documentElement.dataset.theme = "dark";
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
  } catch (_error) {
    document.documentElement.removeAttribute("data-theme");
  }
})();
