(() => {
  document.documentElement.dataset.theme = "dark";
  try {
    let saved = null;
    try { saved = JSON.parse(localStorage.getItem("cloudReportDisplay:v1") || "null"); } catch (_error) {}
    const legacy = localStorage.getItem("weakEarlyBetaTheme:v1");
    const theme = ["light", "dark", "system"].includes(saved?.theme) ? saved.theme : ["light", "dark"].includes(legacy) ? legacy : "dark";
    if (theme === "dark" || theme === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches) document.documentElement.dataset.theme = "dark";
    else document.documentElement.removeAttribute("data-theme");
    if (["small", "standard", "large"].includes(saved?.fontSize)) document.documentElement.dataset.fontSize = saved.fontSize;
  } catch (_error) {}
})();
