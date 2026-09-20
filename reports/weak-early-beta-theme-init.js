(() => {
  try {
    if (localStorage.getItem("weakEarlyBetaTheme:v1") === "dark") {
      document.documentElement.dataset.theme = "dark";
    }
  } catch (_error) {}
})();
