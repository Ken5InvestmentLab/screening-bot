(() => {
  const root = document.documentElement;
  if (root.dataset.initialTheme === 'system') {
    root.dataset.theme = window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
})();
