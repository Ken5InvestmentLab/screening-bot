import assert from 'node:assert/strict';

const patches = [
  ['if (settings && endpoint) {', 'if (settings && endpoint && !window.AFiniteUI) {'],
  ['const applyPreferences = async ({ persist = false } = {}) => {', 'const applyPreferences = async ({ persist = false } = {}) => {\n    if (window.AFiniteUI) return false;'],
  ["window.addEventListener?.('storage', async event => {", "window.addEventListener?.('storage', async event => {\n    if (window.AFiniteUI) return;"],
  ['  let appliedDisplay = { theme: "dark", fontSize: defaultFontSize, pageSize: 20 };',
    '  const initialTheme = window.AFiniteUI ? document.documentElement.dataset.initialTheme : null;\n  let appliedDisplay = { theme: ["light", "dark", "system"].includes(initialTheme) ? initialTheme : "dark", fontSize: defaultFontSize, pageSize: 20 };'],
  ['    const legacyTheme = localStorage.getItem(THEME_KEY);', '    if (window.AFiniteUI) throw Error("account_display_preference");\n    const legacyTheme = localStorage.getItem(THEME_KEY);'],
  ['  const filter = ({ resetLimit = false } = {}) => {', '  let lastHistorySort;\n  const filter = ({ resetLimit = false } = {}) => {'],
  ['    if (historySort) {', '    if (historySort && lastHistorySort !== historySort.value) {\n      lastHistorySort = historySort.value;'],
  ['      row.hidden = !display;', '      if (row.hidden === display) row.hidden = !display;'],
  ['    if (resetLimit) visibleLimit = PAGE_SIZE;', '    if (window.AFiniteRevoked) return;\n    if (resetLimit) visibleLimit = PAGE_SIZE;'],
  ['      return (row.dataset.masked === "true" || CloudPreferences.matchesCap(row.dataset.signalActualClose,\n        row.dataset.signalPriceVerified || row.dataset.signalActualCloseStatus, appliedPreferences.priceCapYen))\n        && (appliedYears === null || appliedYears.includes(Number(signalDate.slice(0, 4))))',
    '      return (window.AFiniteUI || ((row.dataset.masked === "true" || CloudPreferences.matchesCap(row.dataset.signalActualClose,\n        row.dataset.signalPriceVerified || row.dataset.signalActualCloseStatus, appliedPreferences.priceCapYen))\n        && (appliedYears === null || appliedYears.includes(Number(signalDate.slice(0, 4))))))'],
  ['    if (clear) clear.disabled = !symbolValue', '    const empty = document.getElementById("new-a-history-empty");\n    if (empty) empty.hidden = matchedRows.length > 0;\n    if (clear) clear.disabled = !symbolValue'],
];

const hook = `
  if (window.AFiniteUI) window.AFiniteLegacy = {
    matchingIdentities() {return matchingRows.map(r=>r.dataset.aIdentity);},
    initialDisplay() {return {theme:'dark',fontSize:defaultFontSize,pageSize:20};},
    applyAccountDisplay(view) {
      appliedDisplay = view ? {theme:view.theme,fontSize:view.font_size,pageSize:view.page_size} : this.initialDisplay();
      PAGE_SIZE = appliedDisplay.pageSize;
      applyDisplay(appliedDisplay);
      syncDisplayControls();
      filter({resetLimit:true});
    },
    clearHistory() {
      for (const row of rows) {
        for (const key of Object.keys(row.dataset)) delete row.dataset[key];
        row.replaceChildren();
        row.remove();
      }
      rows.length=0;
      matchingRows=[];
    },
  };
`;
export function patchLegacy(raw){
  for(const [before,after] of patches){
    assert.equal(raw.split(before).length,2,'Pinned legacy hook anchor');
    raw=raw.replace(before,after);
  }
  return raw.replace(/\}\)\(\);\s*$/,hook+'})();\n');
}
