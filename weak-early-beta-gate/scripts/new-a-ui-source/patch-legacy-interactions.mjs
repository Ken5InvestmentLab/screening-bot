import assert from 'node:assert/strict';

const patches = [
  ['if (settings && endpoint) {', 'if (settings && endpoint && !window.AFiniteUI) {'],
  ['const applyPreferences = async ({ persist = false } = {}) => {', 'const applyPreferences = async ({ persist = false } = {}) => {\n    if (window.AFiniteUI) return false;'],
  ["window.addEventListener?.('storage', async event => {", "window.addEventListener?.('storage', async event => {\n    if (window.AFiniteUI) return;"],
  ['    const legacyTheme = localStorage.getItem(THEME_KEY);', '    if (window.AFiniteUI) throw Error("account_display_preference");\n    const legacyTheme = localStorage.getItem(THEME_KEY);'],
  ['    if (resetLimit) visibleLimit = PAGE_SIZE;', '    if (window.AFiniteRevoked) return;\n    if (resetLimit) visibleLimit = PAGE_SIZE;'],
  ['    if (clear) clear.disabled = !symbolValue', '    const empty = document.getElementById("new-a-history-empty");\n    if (empty) empty.hidden = matchedRows.length > 0;\n    if (clear) clear.disabled = !symbolValue'],
];

const hook = `
  if (window.AFiniteUI) window.AFiniteLegacy = {
    applySelection(p) {
      appliedPreferences = {priceCapYen:p.price_cap_yen,exitKey:p.exit_endpoint,baseShares:p.base_shares,costPercent:p.cost_percent};
      appliedView = {yearScope:p.year_scope,allocation:p.allocation};
      appliedYears = p.year_scope==='all'?null:[Number(p.year_scope)];
      filter({resetLimit:true});
    },
    matchingIdentities() {return matchingRows.map(r=>r.dataset.aIdentity);},
    initialDisplay() {return {theme:'dark',fontSize:defaultFontSize,pageSize:20};},
    applyAccountDisplay(view) {
      appliedDisplay = view ? {theme:view.theme,fontSize:view.font_size,pageSize:view.page_size} : this.initialDisplay();
      PAGE_SIZE = appliedDisplay.pageSize;
      applyDisplay(appliedDisplay);
      syncDisplayControls();
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
