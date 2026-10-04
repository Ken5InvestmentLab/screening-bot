// Pure preference/CSV helpers are also exercised without a browser by Node tests.
const CloudPreferences = (() => {
  const DEFAULT = Object.freeze({ priceCapYen: 1000, exitKey: "d5_close", baseShares: 100, costPercent: 0 });
  const DEFAULT_VIEW = Object.freeze({ yearScope: "all", allocation: "all" });
  const INITIAL = Object.freeze({ priceCapYen: 1000, exitKey: "d6_open", baseShares: 100, costPercent: 0 });
  const normalizeDisplay = value => {
    if (!value || !["light", "dark", "system"].includes(value.theme) || !["small", "standard", "large"].includes(value.fontSize) || ![20, 50, 100].includes(value.pageSize)) throw new Error("表示設定を確認してください。");
    return { theme: value.theme, fontSize: value.fontSize, pageSize: value.pageSize };
  };
  const PRESETS = [1000, 2000, 3000, 5000];
  const parseCap = (value) => {
    if (value === null) return null;
    if (typeof value !== "string" && typeof value !== "number") throw new Error("株価上限は正の数値で入力してください。");
    const text = String(value).trim();
    if (!/^\d+(?:\.\d{1,2})?$/.test(text)) throw new Error("株価上限は正の数値（小数点以下2桁まで）で入力してください。値は丸めません。");
    const [whole, fraction = ""] = text.split(".");
    const cents = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
    if (cents <= 0n || cents > BigInt(Number.MAX_SAFE_INTEGER)) throw new Error("株価上限は正確に扱える正の金額で入力してください。");
    return Number(cents) / 100;
  };
  const normalize = (value) => {
    if (!value || !["d5_close", "d6_open"].includes(value.exitKey)) throw new Error("確定日を選択してください。");
    const shares = value.baseShares ?? 100, cost = value.costPercent ?? 0;
    if (!Number.isInteger(Number(shares)) || Number(shares) < 100 || Number(shares) > 1000000 || Number(shares) % 100) throw new Error("株数は100〜1,000,000株の範囲で、100株ずつ入力してください。");
    if (!/^\d+(?:\.\d{1,2})?$/.test(String(cost)) || Number(cost) > 10) throw new Error("売買コストは0〜10%の範囲で、小数点以下2桁まで入力してください。");
    return { priceCapYen: parseCap(value.priceCapYen), exitKey: value.exitKey, baseShares: Number(shares), costPercent: Number(cost) };
  };
  const normalizeView = (value, payload) => {
    const yearScope = value?.yearScope || "all";
    const allocation = value?.allocation || "all";
    if (!["all", "unique", "stacked"].includes(allocation)) throw new Error("買付方法を選択してください。");
    if (yearScope !== "all") {
      const years = payload?.scopes?.[yearScope]?.years;
      if (!Array.isArray(years) || !years.length || years.some((year) => !Number.isInteger(year) || year === 2022)) {
        throw new Error("このページで利用できる検出年を選択してください。");
      }
    }
    return { yearScope, allocation };
  };
  const variantKey = (payload, prefs, view = DEFAULT_VIEW) => {
    const { yearScope } = normalizeView(view, payload);
    const scope = yearScope === "all" ? payload : payload.scopes[yearScope];
    const prefix = yearScope === "all" ? prefs.exitKey : `${prefs.exitKey}:${yearScope}`;
    if (prefs.priceCapYen === null) return `${prefix}:all`;
    let bound = "empty";
    for (const [index, price] of (scope.priceBreakpoints || []).entries()) {
      if (price <= prefs.priceCapYen) bound = scope.priceBreakpointKeys?.[index] || String(price);
      else break;
    }
    return `${prefix}:${bound}`;
  };
  const selectCsvMetrics = (records, page, allocation) => records.filter((row) => {
    const selected = { unique: "all_conditions_unique", stacked: "all_conditions_stacked" };
    const combined = Object.values(selected).includes(row.selector_id);
    if (!combined) return page !== "analytics";
    return allocation === "all" || row.selector_id === selected[allocation];
  });
  const matchesCap = (actualClose, verified, cap) => cap === null || (
    (verified === true || verified === "true" || verified === "1" || verified === "verified")
    && Number.isFinite(Number(actualClose)) && Number(actualClose) > 0 && Number(actualClose) <= cap
  );
  const csv = (records, columns) => {
    const cell = (value) => {
      let text = value === null || value === undefined ? "" : String(value);
      // Prevent spreadsheet formula execution when opening exported names/text.
      if (/^[=+@\t\r]/.test(text) || (/^-/.test(text) && !/^-[\d.]+$/.test(text))) text = `'${text}`;
      return `"${text.replaceAll('"', '""')}"`;
    };
    return "\uFEFF" + [columns.map(cell).join(","), ...records.map((row) => columns.map((column) => cell(row[column])).join(","))].join("\r\n");
  };
  return { DEFAULT, INITIAL, DEFAULT_VIEW, PRESETS, parseCap, normalize, normalizeView, normalizeDisplay, variantKey, selectCsvMetrics, matchesCap, csv };
})();
if (typeof module !== "undefined" && module.exports) module.exports = CloudPreferences;

(() => {
  if (typeof document === "undefined") return;
  const THEME_KEY = "weakEarlyBetaTheme:v1";
  let PAGE_SIZE = 20;
  const DISPLAY_KEY = "cloudReportDisplay:v1";
  let appliedDisplay = { theme: "dark", fontSize: "standard", pageSize: 20 };
  try {
    const legacyTheme = localStorage.getItem(THEME_KEY); if (["dark", "light"].includes(legacyTheme)) appliedDisplay.theme = legacyTheme;
    const saved = localStorage.getItem(DISPLAY_KEY);
    if (saved) appliedDisplay = CloudPreferences.normalizeDisplay(JSON.parse(saved));
  } catch (_error) {}
  PAGE_SIZE = appliedDisplay.pageSize;
  const root = document.documentElement;
  const themeButton = document.getElementById("theme-toggle");

  // Keep the snapshot controls independent of the table/filter handlers.
  const fundamentalPairs = Array.from(document.querySelectorAll(".fundamental-toggle"))
    .map((button) => {
      const detail = button.closest("th")?.querySelector(".fundamental-detail")
        || button.parentElement?.querySelector(".fundamental-detail");
      return detail ? { button, detail } : null;
    }).filter(Boolean);
  const closeFundamental = ({ button, detail }) => {
    if (detail.open) detail.close();
    button.setAttribute("aria-expanded", "false");
    button.textContent = "ファンダ分析";
  };
  for (const pair of fundamentalPairs) {
    pair.detail.addEventListener("close", () => {
      pair.button.setAttribute("aria-expanded", "false");
      pair.button.textContent = "ファンダ分析";
    });
    pair.detail.addEventListener("click", (event) => {
      if (event.target === pair.detail) closeFundamental(pair);
    });
  }
  document.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const closeButton = target.closest(".fundamental-close");
    if (closeButton) {
      const pair = fundamentalPairs.find(({ detail }) => detail === closeButton.closest(".fundamental-detail"));
      if (pair) closeFundamental(pair);
      return;
    }
    const button = target.closest(".fundamental-toggle");
    if (button) {
      const pair = fundamentalPairs.find((item) => item.button === button);
      if (!pair) return;
      const shouldOpen = !pair.detail.open;
      fundamentalPairs.forEach(closeFundamental);
      if (shouldOpen) {
        pair.detail.showModal();
        button.setAttribute("aria-expanded", "true");
        button.textContent = "閉じる";
        pair.detail.querySelector(".fundamental-close")?.focus();
      }
      return;
    }
    if (!target.closest(".fundamental-detail")) fundamentalPairs.forEach(closeFundamental);
  });

  const currentTheme = () => root.dataset.theme === "dark" ? "dark" : "light";
  const applyTheme = (theme, persist = false) => {
    const normalized = theme === "dark" ? "dark" : "light";
    if (normalized === "dark") root.dataset.theme = "dark";
    else root.removeAttribute("data-theme");
    if (themeButton) {
      themeButton.setAttribute("aria-pressed", normalized === "dark" ? "true" : "false");
      themeButton.setAttribute(
        "aria-label",
        normalized === "dark" ? "ライトモードに切り替える" : "ダークモードに切り替える"
      );
      const label = themeButton.querySelector(".theme-toggle-label");
      if (label) label.textContent = normalized === "dark" ? "ライト" : "ダーク";
    }
    if (persist) {
      try { localStorage.setItem(THEME_KEY, normalized); } catch (_error) {}
    }
  };
  applyTheme(currentTheme());
  themeButton?.addEventListener("click", () => {
    applyTheme(currentTheme() === "dark" ? "light" : "dark", true);
  });
  const applyDisplay = (value, persist = false) => {
    const dark = value.theme === "system" ? window.matchMedia?.("(prefers-color-scheme: dark)").matches : value.theme === "dark";
    applyTheme(dark ? "dark" : "light");
    root.dataset.fontSize = value.fontSize;
    if (persist) {
      localStorage.setItem(DISPLAY_KEY, JSON.stringify(value));
      localStorage.setItem(THEME_KEY, dark ? "dark" : "light");
    }
  };
  applyDisplay(appliedDisplay);
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", () => {
    const selected = document.getElementById("cloud-settings-dialog")?.open ? readDisplayControls() : appliedDisplay;
    if (selected.theme === "system") applyDisplay(selected);
  });
  const menuButton = document.getElementById("cloud-menu-toggle"), menu = document.getElementById("cloud-navigation");
  const closeMenu = (restore = false) => {
    if (!menu) return;
    menu.hidden = true; menuButton?.setAttribute("aria-expanded", "false");
    if (restore) menuButton?.focus();
  };
  menuButton?.addEventListener("click", () => {
    const open = menu.hidden; menu.hidden = !open; menuButton.setAttribute("aria-expanded", String(open));
    if (open) menu.querySelector('[aria-current="page"],a')?.focus();
  });
  document.addEventListener("keydown", event => { if (event.key === "Escape" && menu && !menu.hidden) closeMenu(true); });
  document.addEventListener("click", event => { if (menu && !menu.hidden && !menu.contains(event.target) && !menuButton?.contains(event.target)) closeMenu(true); });

  const symbol = document.getElementById("symbol-filter");
  const selector = document.getElementById("selector-filter");
  const dateFrom = document.getElementById("history-date-from");
  const dateTo = document.getElementById("history-date-to");
  const clear = document.getElementById("clear-search");
  const resultCount = document.getElementById("search-result-count");
  const loadMore = document.getElementById("history-load-more");
  const collapse = document.getElementById("history-collapse");
  const historySort = document.getElementById("history-sort");
  // The empty-history message is a table row, but never a detection or CSV row.
  const scenarioRows = document.getElementById("cloud-scenario-rows");
  const rows = Array.from(scenarioRows?.content ? scenarioRows.content.querySelectorAll("tr[data-date]") : document.querySelectorAll("#detection-table tbody tr[data-date]"));
  const normalize = (value) => String(value || "").normalize("NFKC").trim().toLowerCase();
  let visibleLimit = PAGE_SIZE;
  // Only applied preferences may be used by visible rows, endpoint cells or CSV.
  // A requested choice can remain in flight while its aggregate is decompressed.
  let appliedPreferences = { ...CloudPreferences.DEFAULT };
  let requestedPreferences = { ...appliedPreferences };
  let appliedView = { ...CloudPreferences.DEFAULT_VIEW };
  let requestedView = { ...appliedView };
  let appliedYears = null;
  let matchingRows = [];

  const initialQuery = new URLSearchParams(window.location.search).get("q");
  if (symbol && initialQuery) symbol.value = initialQuery;

  const filter = ({ resetLimit = false } = {}) => {
    if (resetLimit) visibleLimit = PAGE_SIZE;
    if (historySort) {
      rows.sort((a,b) => historySort.value === 'symbol' ? String(a.dataset.symbol).localeCompare(String(b.dataset.symbol), 'ja', { numeric: true })
        : historySort.value === 'oldest' ? String(a.dataset.date).localeCompare(String(b.dataset.date)) : String(b.dataset.date).localeCompare(String(a.dataset.date)));
      const tbody = document.querySelector('#detection-table tbody');
      if (tbody) for (const row of rows) tbody.append(row);
    }
    const symbolValue = normalize(symbol?.value);
    const selectorValue = selector?.value || "";
    const fromValue = dateFrom?.value || "";
    const toValue = dateTo?.value || "";
    const matchedRows = rows.filter((row) => {
      const searchTarget = normalize(row.dataset.search || row.dataset.symbol);
      const signalDate = row.dataset.date || "";
      return CloudPreferences.matchesCap(row.dataset.signalActualClose,
        row.dataset.signalPriceVerified || row.dataset.signalActualCloseStatus, appliedPreferences.priceCapYen)
        && (appliedYears === null || appliedYears.includes(Number(signalDate.slice(0, 4))))
        && (!symbolValue || searchTarget.includes(symbolValue))
        && (!selectorValue || (row.dataset.selectors || "").split(" ").includes(selectorValue))
        && (!fromValue || signalDate >= fromValue)
        && (!toValue || signalDate <= toValue);
    });
    matchingRows = matchedRows;
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
    if (loadMore) loadMore.textContent = `次の${PAGE_SIZE}件を表示`;
    if (collapse) collapse.textContent = `最初の${PAGE_SIZE}件に戻す`;
    if (collapse) collapse.hidden = visibleLimit <= PAGE_SIZE || matchedRows.length <= PAGE_SIZE;
  };

  for (const control of [symbol, dateFrom, dateTo]) {
    control?.addEventListener("input", () => filter({ resetLimit: true }));
    control?.addEventListener("change", () => filter({ resetLimit: true }));
  }
  symbol?.addEventListener("search", () => filter({ resetLimit: true }));
  selector?.addEventListener("change", () => filter({ resetLimit: true }));
  historySort?.addEventListener("change", () => filter({ resetLimit: true }));
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

  const initializePagination = (scope = document) => {
  for (const table of scope.querySelectorAll("table[data-paginated-table]")) {
    if (table.dataset.paginationReady) continue;
    table.dataset.paginationReady = "true";
    const tableRows = Array.from(table.querySelectorAll("tbody tr"));
    const pagination = table.closest(".table-wrap")?.nextElementSibling;
    if (!pagination?.classList.contains("table-pagination")) continue;
    const moreButton = pagination.querySelector(".table-load-more");
    const resetButton = pagination.querySelector(".table-collapse");
    const count = pagination.querySelector(".table-result-count");
    if (moreButton) moreButton.textContent = `次の${PAGE_SIZE}件を表示`;
    if (resetButton) resetButton.textContent = `最初の${PAGE_SIZE}件に戻す`;
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
  };
  initializePagination();

  let annualResizeObserver = null;
  const initializeAnnualSummary = (scope) => {
    annualResizeObserver?.disconnect();
    const annual = scope.querySelector('#annual-pl'), payoff = scope.querySelector('#payoff-structure'), toggle = scope.querySelector('#annual-older-toggle');
    if (!annual || !payoff || !toggle) return;
    const yearRows = Array.from(annual.querySelectorAll('.cloud-bar-row'));
    let expanded = false, scheduled = false;
    const arrange = () => {
      scheduled = false;
      payoff.style.minHeight = ''; annual.style.minHeight = '';
      yearRows.forEach(row => { row.hidden = false; });
      toggle.hidden = false;
      const target = payoff.getBoundingClientRect().height;
      const count = Math.min(3, yearRows.length);
      const overflow = count < yearRows.length;
      yearRows.forEach((row,index) => { row.hidden = !expanded && index >= count; });
      const values = yearRows.filter(row => !row.hidden).flatMap(row => Array.from(row.querySelectorAll('[data-bar-value]')).map(item => Number(item.dataset.barValue)));
      const minimum = Math.min(0, ...values), maximum = Math.max(0, ...values), span = maximum - minimum || 1;
      const zero = -minimum / span * 100;
      annual.dataset.axisMin = String(minimum); annual.dataset.axisMax = String(maximum);
      for (const row of yearRows) for (const item of row.querySelectorAll('[data-bar-value]')) {
        const value = Number(item.dataset.barValue), track = item.querySelector('.cloud-bar-track'), bar = track.querySelector('i');
        track.style.setProperty('--bar-zero', `${zero}%`);
        bar.style.width = `${Math.abs(value) / span * 100}%`;
        bar.style.marginLeft = `${value < 0 ? zero - Math.abs(value) / span * 100 : zero}%`;
      }
      let axis = annual.querySelector('.annual-bar-axis');
      if (!axis) { axis = document.createElement('p'); axis.className = 'note annual-bar-axis'; annual.querySelector('#annual-year-bars').after(axis); }
      axis.textContent = `目盛り: ${CloudScenario.yen(minimum)} 〜 ${CloudScenario.yen(maximum)}（0が基準）`;

      toggle.hidden = !overflow;
      toggle.textContent = expanded ? '新しい年だけに戻す' : '過去の年を表示';
      toggle.setAttribute('aria-expanded', String(expanded));
      if (expanded) annual.style.minHeight = `${target}px`;
      else {
        // Three complete years remain readable at narrow widths and large
        // fonts. Grow the shorter card instead of cutting off a chart row.
        const balanced = Math.max(target, annual.getBoundingClientRect().height);
        annual.style.minHeight = `${balanced}px`; payoff.style.minHeight = `${balanced}px`;
      }
    };
    toggle.addEventListener('click', () => { expanded = !expanded; arrange(); });
    if (typeof ResizeObserver !== 'undefined') {
      annualResizeObserver = new ResizeObserver(() => { if (!scheduled) { scheduled = true; requestAnimationFrame(arrange); } });
      annualResizeObserver.observe(payoff);
    }
    arrange();
  };

  const settings = document.getElementById("cloud-price-preset");
  const customPrice = document.getElementById("cloud-price-custom");
  const customPriceField = document.getElementById("cloud-price-custom-field");
  const endpoint = document.getElementById("cloud-exit-endpoint");
  const yearScope = document.getElementById("cloud-year-scope");
  const allocation = document.getElementById("cloud-allocation");
  const baseShares = document.getElementById("cloud-base-shares");
  const costPercent = document.getElementById("cloud-cost-percent");
  const settingsDialog = document.getElementById("cloud-settings-dialog"), settingsOpen = document.getElementById("cloud-settings-open");
  const displayTheme = document.getElementById("cloud-theme"), displayFont = document.getElementById("cloud-font-size"), displayPage = document.getElementById("cloud-page-size");
  let settingsSnapshot = null;
  const researchReset = document.getElementById("cloud-research-reset");
  const saveButton = document.getElementById("cloud-settings-save");
  const status = document.getElementById("cloud-settings-status");
  const payloadElement = document.getElementById("cloud-analytics-data");
  const content = document.getElementById("cloud-analytics-content");
  const storageKey = "cloudReportPreferences:v1";
  const viewStorageKey = "cloudReportView:v1";
  let payload = null;
  let currentVariant = null;
  let renderRevision = 0;
  let preferencesPending = false;
  let saving = false;
  const exportButton = document.getElementById("cloud-export-csv");
  const historyExportButton = document.getElementById("cloud-history-export-csv");
  const decodedVariants = new Map();
  const bundles = new Map();
  let accessLost = false;
  let edited = false;
  let editRevision = 0;
  let storageFailed = false;
  let serverAvailable = false;
  let notifications = { new_detection: false, reminder: false };
  const notifyInputs = {};
  const notifyLabels = {};
  let notifyMembershipPaid = false;
  const syncNotificationControls = () => {
    for (const [key, input] of Object.entries(notifyInputs)) {
      input.checked = notifications[key];
      input.disabled = accessLost || !serverAvailable || (!notifyMembershipPaid && !notifications[key]);
      notifyLabels[key].textContent = notifications[key] ? 'ON' : 'OFF';
    }
  };
  const notificationReadiness = membership => {
    const output = document.getElementById('cloud-notification-readiness');
    if (!output) return;
    const entitlement = membership === 'paid' ? '有料会員資格を確認済み' : membership === 'unknown' ? '会員資格は未確認' : '有効な有料会員資格が必要';
    const permission = typeof Notification === 'undefined' ? 'このブラウザのプッシュは未対応' : Notification.permission === 'granted' ? '端末の通知権限あり' : Notification.permission === 'denied' ? '端末の通知権限なし' : '端末の通知許可は未設定';
    output.textContent = `${entitlement}。${permission}。ブラウザの通知許可と端末登録は別の状態です。`;
  };
  notificationReadiness('unknown');
  const setStatus = (message, invalid = false) => {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = invalid ? "error" : "info";
  };
  try { if (payloadElement) payload = JSON.parse(payloadElement.textContent); }
  catch (_error) { setStatus("表示用データを読み込めません。ページを再読込してください。", true); }

  if (settings && endpoint) {
    const host = document.createElement(settingsDialog ? "div" : "details");
    host.className = "cloud-notification-settings";
    host.innerHTML = (settingsDialog ? '' : '<summary>プッシュ通知の設定</summary>') + '<p>ON／OFFで通知を一時停止・再開します。「設定を保存」で反映し、OFFでも端末登録は残ります。初期設定はすべてOFFです。</p>';
    for (const [key, label] of Object.entries({ new_detection: "新しい検出", reminder: "売却予定日の朝8時（日本時間）" })) {
      const element = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.setAttribute('role', 'switch');
      checkbox.id = `cloud-notify-${key}`;
      checkbox.checked = false;
      checkbox.disabled = true;
      const state = document.createElement('span'); state.textContent = 'OFF';
      element.append(checkbox, document.createTextNode(` ${label}：`), state);
      host.append(element);
      notifyInputs[key] = checkbox;
      notifyLabels[key] = state;
      checkbox.addEventListener("change", () => {
        edited = true;
        editRevision += 1;
        notifications[key] = checkbox.checked;
        syncNotificationControls();
        setStatus("通知設定は未保存です。「設定を保存」で会員設定を更新します。");
      });
    }
    const note = document.createElement("p");
    note.textContent = "朝8時に「今日は売却予定日」とお知らせします。その日の始値・終値はまだ出ていません。";
    host.append(note);
    (document.getElementById("cloud-notification-settings") || document.getElementById("cloud-preferences") || saveButton?.parentElement || settings.parentElement).append(host);
  }

  const syncControls = (preferences = requestedPreferences) => {
    if (!settings || !endpoint) return;
    settings.value = preferences.priceCapYen === null ? "unlimited" : (
      CloudPreferences.PRESETS.includes(preferences.priceCapYen) ? String(preferences.priceCapYen) : "custom"
    );
    if (customPrice) {
      customPrice.hidden = settings.value !== "custom";
      if (customPriceField) customPriceField.hidden = settings.value !== "custom";
      customPrice.disabled = settings.value !== "custom";
      customPrice.value = preferences.priceCapYen === null ? "" : String(preferences.priceCapYen);
      customPrice.setAttribute("aria-invalid", "false");
    }
    endpoint.value = preferences.exitKey;
    if (baseShares) baseShares.value = String(preferences.baseShares);
    if (costPercent) costPercent.value = String(preferences.costPercent);
    if (yearScope) yearScope.value = requestedView.yearScope;
    if (allocation) allocation.value = requestedView.allocation;
  };
  const decodeVariant = async (key) => {
    if (accessLost) throw new Error("access lost");
    if (decodedVariants.has(key)) return decodedVariants.get(key);
    let packed = payload.variants[key];
    if (!packed) throw new Error("missing variant");
    if (typeof packed.bundle === "string") {
      const match = /^\.\/weak_early_beta_data_(full|free)_(latest|analytics|silence|dive|shadow|fusion|balance|guide)_([a-f0-9]{16})_(\d{4})\.json$/.exec(packed.bundle);
      const context = payload.bundleContext;
      if (!match || !context || match[1] !== context.audience || match[2] !== context.page || match[3] !== context.snapshot) throw new Error("invalid bundle reference");
      const url = new URL(packed.bundle, window.location.href);
      if (url.origin !== window.location.origin) throw new Error("invalid bundle origin");
      let bundle = bundles.get(packed.bundle);
      if (!bundle) {
        const response = await fetch(url.href, { credentials: "same-origin", cache: "no-store", redirect: "error" });
        if (response.status === 401 || response.status === 403) {
          // Even a superseded request's denial invalidates paid cached content.
          accessLost = true;
          renderRevision += 1;
          decodedVariants.clear(); bundles.clear(); currentVariant = null;
          for (const pair of fundamentalPairs) {
            closeFundamental(pair);
            pair.detail.innerHTML = "";
            pair.detail.remove();
          }
          fundamentalPairs.length = 0;
          rows.forEach((row) => row.remove()); rows.length = 0; matchingRows = [];
          content.innerHTML = "";
          payloadElement.textContent = "";
          payload = null;
          for (const element of document.querySelectorAll("[data-fundamental], .fundamental-detail")) element.remove();
          syncActionAvailability();
          setStatus("閲覧資格を再確認します。ページを読み直しています。", true);
          window.location.reload();
          throw new Error("access lost");
        }
        if (!response.ok) throw new Error("bundle unavailable");
        if (Number(response.headers.get("content-length")) > 1024 * 1024) throw new Error("oversized bundle");
        const text = await response.text();
        if (new TextEncoder().encode(text).length > 1024 * 1024) throw new Error("oversized bundle");
        bundle = JSON.parse(text);
        if (accessLost) throw new Error("access lost");
        if (bundle.version !== 1 || bundle.encoding !== "gzip-base64-json" || bundle.audience !== context.audience || bundle.page !== context.page || bundle.snapshot !== context.snapshot || bundle.chunk !== Number(match[4]) || !bundle.variants || Array.isArray(bundle.variants) || Object.keys(bundle.variants).length > 32) throw new Error("invalid bundle context");
        if (bundles.size >= 2) bundles.delete(bundles.keys().next().value);
        bundles.set(packed.bundle, bundle);
      }
      packed = bundle.variants[key];
      if (!packed || typeof packed.gzip !== "string") throw new Error("missing bundle variant");
    }
    let variant = packed;
    if (typeof packed.gzip === "string") {
      if (typeof DecompressionStream === "undefined") throw new Error("decompression unavailable");
      const bytes = Uint8Array.from(atob(packed.gzip), (character) => character.charCodeAt(0));
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      variant = await new Response(stream).json();
    }
    if (typeof variant.html !== "string" || !Array.isArray(variant.metrics) || !Array.isArray(variant.monthlyMetrics)) throw new Error("invalid variant");
    variant.html = variant.html.replace(/<!--cloud-shared:([a-z0-9_-]+)-->/g, (_token, fragmentKey) => {
      const fragment = payload.sharedHtml?.[fragmentKey];
      if (typeof fragment !== "string" || fragment.includes("<!--cloud-shared:")) throw new Error("invalid shared HTML");
      return fragment;
    });
    if (accessLost) throw new Error("access lost");
    // Retain only two decoded choices; compressed histories can remain compact
    // on mobile even when many exact nominal-price boundaries are available.
    if (decodedVariants.size >= 2) decodedVariants.delete(decodedVariants.keys().next().value);
    decodedVariants.set(key, variant);
    return variant;
  };
  const savedControlAvailability = new Map();
  const syncActionAvailability = () => {
    // A save commits one complete draft. Prevent edits or reset during its PUT.
    if (settingsDialog) for (const control of settingsDialog.querySelectorAll('input, select, button')) {
      if (saving) { if (!savedControlAvailability.has(control)) savedControlAvailability.set(control, control.disabled); control.disabled = true; }
      else if (savedControlAvailability.has(control)) { control.disabled = savedControlAvailability.get(control); savedControlAvailability.delete(control); }
    }
    if (exportButton) exportButton.disabled = accessLost || preferencesPending || !currentVariant;
    if (historyExportButton) historyExportButton.disabled = accessLost || preferencesPending;
    if (saveButton) saveButton.disabled = accessLost || preferencesPending || saving;
    content?.setAttribute("aria-busy", preferencesPending ? "true" : "false");
  };
  const applyPreferences = async ({ persist = false } = {}) => {
    if (accessLost) return false;
    const revision = ++renderRevision;
    const requested = { ...requestedPreferences };
    const nextView = { ...requestedView };
    preferencesPending = true;
    syncActionAvailability();
    let nextVariant = currentVariant;
    if (payloadElement && content) {
      try {
        if (!payload) throw new Error("analytics payload unavailable");
        if (payload.version === 2) {
          const data = CloudScenario.calculate(rows.map(row => row.dataset), requested, nextView, payload);
          nextVariant = { html: CloudScenario.render(data, requested, nextView, payload), metrics: [], monthlyMetrics: [], scenario: data };
        } else nextVariant = await decodeVariant(CloudPreferences.variantKey(payload, requested, nextView));
        if (accessLost || revision !== renderRevision) return false;
      } catch (_error) {
        if (accessLost || revision !== renderRevision) return false;
        // Keep the last complete view and its CSV usable; failed requests are
        // neither persisted locally nor sent as the current member preference.
        requestedPreferences = { ...appliedPreferences };
        requestedView = { ...appliedView };
        syncControls(appliedPreferences);
        preferencesPending = false;
        syncActionAvailability();
        setStatus("この条件の集計を読み込めません。直前の表示に戻しました。変更は保存していません。", true);
        return false;
      }
    }
    // No await inside this commit: aggregates, history, endpoint cells and the
    // parameters used by both exports change together within one browser task.
    if (payload && content) {
      content.innerHTML = nextVariant.html;
      initializePagination(content);
      initializeAnnualSummary(content);
    }
    if (payload?.version === 2) {
      for (const label of document.querySelectorAll('[data-guide-base-shares]')) label.textContent = requested.baseShares.toLocaleString('ja-JP');
      for (const label of document.querySelectorAll('[data-guide-stacked-shares]')) label.textContent = (requested.baseShares * 3).toLocaleString('ja-JP');
      for (const label of document.querySelectorAll('[data-scenario-endpoint-label]')) label.textContent = requested.exitKey === 'd5_close' ? '5営業日後 終値' : '6営業日後 始値';
      for (const row of rows) {
        const t = CloudScenario.trade(row.dataset, requested);
        const pl = row.querySelector('[data-scenario-pl]'), ret = row.querySelector('[data-scenario-return]'), shares = row.querySelector('[data-scenario-shares]'), cost = row.querySelector('[data-scenario-cost]');
        const methods = requestedView.allocation === 'all' ? ['unique', 'stacked'] : [requestedView.allocation];
        const units = method => method === 'stacked' ? t.selectors.length : 1;
        const label = method => method === 'stacked' ? '条件数比例' : '一律';
        if (pl) pl.innerHTML = methods.map(method => `<span class="history-method ${t.pl>0?'positive':t.pl<0?'negative':''}" data-method="${method}"><small>${label(method)}</small>${CloudScenario.yen(t.pl === null ? null : t.pl * units(method), true)}</span>`).join('');
        if (ret) ret.textContent = CloudScenario.pct(t.returnPct, true) + (requestedView.allocation === 'all' && t.returnPct !== null ? '（両方式共通）' : '');
        if (shares) shares.innerHTML = methods.map(method => `<span data-method="${method}">${label(method)} ${(requested.baseShares * units(method)).toLocaleString('ja-JP')}株${t.pl !== null && t.exitShares !== null && Math.abs(t.exitShares - requested.baseShares) > 1e-9 ? `（売却 ${(t.exitShares * units(method)).toLocaleString('ja-JP')}株）` : ''}</span>`).join(' / ');
        if (cost) cost.innerHTML = methods.map(method => `<span data-method="${method}">${label(method)} ${CloudScenario.yen(t.cost === null ? null : t.cost * units(method))}</span>`).join('');
      }
      const summary = document.getElementById('cloud-applied-summary');
      if (summary) summary.textContent = `表示中: 終値 ${requested.priceCapYen === null ? '上限なし' : requested.priceCapYen.toLocaleString('ja-JP')+'円以下'} / 確定日 ${endpoint.options[endpoint.selectedIndex].text} / 基準となる株数 ${requested.baseShares.toLocaleString('ja-JP')}株 / 片道${requested.costPercent}% / ${payload.scopes[nextView.yearScope].label} / ${nextView.allocation === 'stacked' ? '条件数比例' : nextView.allocation === 'unique' ? '一律' : '両方式を比較'}`;
    }
    currentVariant = nextVariant;
    appliedPreferences = requested;
    appliedView = nextView;
    appliedYears = appliedView.yearScope === "all" ? null : [...payload.scopes[appliedView.yearScope].years];
    for (const element of document.querySelectorAll("[data-exit-key]")) {
      element.hidden = element.dataset.exitKey !== appliedPreferences.exitKey;
    }
    for (const element of document.querySelectorAll("[data-cloud-allocation]")) {
      // SVG series do not reflect an HTMLElement.hidden property. The shared
      // [hidden] CSS rule applies to this explicit attribute on either element.
      if (appliedView.allocation !== "all" && element.dataset.cloudAllocation !== appliedView.allocation) element.setAttribute("hidden", "");
      else element.removeAttribute("hidden");
    }
    filter({ resetLimit: true });
    if (persist) {
      try {
        localStorage.setItem(storageKey, JSON.stringify(appliedPreferences));
        localStorage.setItem(viewStorageKey, JSON.stringify(appliedView));
        storageFailed = false;
      }
      catch (_error) { storageFailed = true; }
    }
    preferencesPending = false;
    syncActionAvailability();
    return true;
  };
  const readControls = () => CloudPreferences.normalize({
    priceCapYen: settings.value === "unlimited" ? null : (settings.value === "custom" ? customPrice?.value : settings.value),
    exitKey: endpoint.value,
    baseShares: baseShares?.value ?? 100, costPercent: costPercent?.value ?? 0,
  });
  const readViewControls = () => CloudPreferences.normalizeView({
    yearScope: yearScope?.value || "all", allocation: allocation?.value || "all",
  }, payload);
  const readDisplayControls = () => CloudPreferences.normalizeDisplay({ theme: displayTheme?.value || appliedDisplay.theme, fontSize: displayFont?.value || appliedDisplay.fontSize, pageSize: Number(displayPage?.value || appliedDisplay.pageSize) });
  const syncDisplayControls = () => {
    if (displayTheme) displayTheme.value = appliedDisplay.theme;
    if (displayFont) displayFont.value = appliedDisplay.fontSize;
    if (displayPage) displayPage.value = String(appliedDisplay.pageSize);
  };
  const cancelSettings = () => {
    if (!settingsSnapshot || saving) return;
    notifications = { ...settingsSnapshot.notifications }; edited = settingsSnapshot.edited;
    requestedPreferences = { ...appliedPreferences }; requestedView = { ...appliedView };
    syncControls(); syncDisplayControls(); applyDisplay(appliedDisplay);
    syncNotificationControls();
    settingsDialog.close();
  };
  if (settingsDialog && settingsOpen) {
    settingsOpen.addEventListener('click', () => {
      closeMenu(); requestedPreferences = { ...appliedPreferences }; requestedView = { ...appliedView };
      settingsSnapshot = { notifications: { ...notifications }, edited };
      syncControls(); syncDisplayControls(); edited = true;
      settingsDialog.showModal(); root.style.overflow = 'hidden';
      settingsDialog.querySelector('[role="tab"][aria-selected="true"]')?.focus();
    });
    document.getElementById('cloud-settings-close')?.addEventListener('click', cancelSettings);
    document.getElementById('cloud-settings-cancel')?.addEventListener('click', cancelSettings);
    settingsDialog.addEventListener('cancel', event => { event.preventDefault(); cancelSettings(); });
    settingsDialog.addEventListener('close', () => { root.style.overflow = ''; settingsOpen.focus(); settingsSnapshot = null; });
    settingsDialog.addEventListener('click', event => {
      if (event.target !== settingsDialog) return;
      const r = settingsDialog.getBoundingClientRect();
      if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) cancelSettings();
    });
    const tabs = Array.from(settingsDialog.querySelectorAll('[role="tab"]'));
    const activate = button => { if (researchReset) researchReset.textContent = ({'settings-tab-trial':'試算方法をリセット','settings-tab-notifications':'通知をリセット','settings-tab-display':'表示をリセット'})[button.id]; tabs.forEach(tab => {
      const selected = tab === button; tab.setAttribute('aria-selected', String(selected)); tab.tabIndex = selected ? 0 : -1;
      document.getElementById(tab.getAttribute('aria-controls')).hidden = !selected;
    }); };
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => activate(tab));
      tab.addEventListener('keydown', event => {
        const next = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
        if (next !== null) { event.preventDefault(); activate(tabs[next]); tabs[next].focus(); }
      });
    });
    for (const input of [displayTheme, displayFont, displayPage]) input?.addEventListener('change', () => { edited = true; editRevision += 1; applyDisplay(readDisplayControls()); setStatus('未保存の表示を確認中です。「設定を保存」で残し、「キャンセル」で元に戻ります。'); });
  }
  const commitSettingsDraft = async () => {
    if (accessLost || preferencesPending || saving) return;
    let prefs, view, display;
    try { prefs = readControls(); view = readViewControls(); display = readDisplayControls(); }
    catch (error) { setStatus(error.message, true); return; }
    saving = true; syncActionAvailability();
    try {
      if (serverAvailable) {
        const response = await fetch('/api/cloud/preferences', { method: 'PUT', credentials: 'same-origin', cache: 'no-store', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ max_price: prefs.priceCapYen, exit_endpoint: prefs.exitKey, base_shares: prefs.baseShares, cost_percent: prefs.costPercent, notifications }) });
        if (!response.ok) throw new Error('会員設定を保存できませんでした。入力は残しています。接続を確認して再度お試しください。');
      }
      requestedPreferences = prefs; requestedView = view; appliedDisplay = display; PAGE_SIZE = display.pageSize;
      if (!await applyPreferences({ persist: true })) throw new Error('表示に反映できませんでした。再度お試しください。');
      try { applyDisplay(display, true); } catch (_error) { storageFailed = true; }
      edited = false;
      const message = storageFailed ? '表示に適用しました。端末の保存は利用できません。' : serverAvailable ? '会員設定と端末の表示設定を保存しました。' : 'この端末に設定を保存しました。会員設定の連携前です。';
      setStatus(message); const feedback = document.getElementById('cloud-settings-feedback'); if (feedback) feedback.textContent = message;
      settingsDialog.close();
    } catch (error) { setStatus(error.message, true); }
    finally { saving = false; syncActionAvailability(); }
  };
  const updateFromControls = async () => {
    edited = true;
    editRevision += 1;
    const editAtChange = editRevision;
    if (customPrice) {
      customPrice.hidden = settings.value !== "custom";
      if (customPriceField) customPriceField.hidden = settings.value !== "custom";
      customPrice.disabled = settings.value !== "custom";
    }
    if (settingsDialog) {
      try { readControls(); readViewControls(); setStatus('未保存です。「設定を保存」で表示・試算へ反映します。'); }
      catch (error) { setStatus(error.message, true); }
      return;
    }
    try {
      const next = readControls();
      const nextView = readViewControls();
      requestedPreferences = next;
      requestedView = nextView;
      customPrice?.setAttribute("aria-invalid", "false");
      setStatus("表示条件を反映しています。しばらくお待ちください。");
      if (await applyPreferences({ persist: true }) && editRevision === editAtChange) setStatus(storageFailed
        ? "表示に適用しました。この端末では補助保存できません。株価上限・確定日は会員設定へ保存できます。"
        : "表示に適用しました。今の条件を会員設定に残すには「設定を保存」を押してください。検出年・買付方法はこの端末に保存します。");
    } catch (error) {
      // An invalid newer edit must also cancel an older decompression request.
      renderRevision += 1;
      requestedPreferences = { ...appliedPreferences };
      requestedView = { ...appliedView };
      preferencesPending = false;
      syncActionAvailability();
      customPrice?.setAttribute("aria-invalid", "true");
      setStatus(`${error.message} 前の有効な設定を表示しています。`, true);
    }
  };
  if (settings && endpoint) {
    if (payload?.version === 2) requestedPreferences = { ...CloudPreferences.INITIAL };
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) requestedPreferences = CloudPreferences.normalize(JSON.parse(saved));
      const savedView = localStorage.getItem(viewStorageKey);
      if (savedView) {
        // A free page may expose fewer years than the paid page. Never reuse an
        // unavailable scope, or invent hidden source-year metadata for it.
        try { requestedView = CloudPreferences.normalizeView(JSON.parse(savedView), payload); }
        catch (_error) { requestedView = { ...CloudPreferences.DEFAULT_VIEW }; }
      }
    } catch (_error) { storageFailed = true; }
    syncControls();
    syncDisplayControls();
    applyPreferences();
    settings.addEventListener("change", updateFromControls);
    endpoint.addEventListener("change", updateFromControls);
    yearScope?.addEventListener("change", updateFromControls);
    allocation?.addEventListener("change", updateFromControls);
    baseShares?.addEventListener("change", updateFromControls);
    costPercent?.addEventListener("change", updateFromControls);
    customPrice?.addEventListener("input", updateFromControls);
    researchReset?.addEventListener("click", () => {
      if (settingsDialog) {
        const active = settingsDialog.querySelector('[role="tab"][aria-selected="true"]')?.id;
        if (active === 'settings-tab-trial') { requestedPreferences = { ...CloudPreferences.INITIAL }; requestedView = { ...CloudPreferences.DEFAULT_VIEW }; syncControls(); }
        if (active === 'settings-tab-notifications') { notifications = { new_detection: false, reminder: false }; syncNotificationControls(); }
        if (active === 'settings-tab-display') { displayTheme.value = 'dark'; displayFont.value = 'standard'; displayPage.value = '20'; applyDisplay(readDisplayControls()); }
        edited = true; editRevision += 1;
        setStatus('このタブを初期値に戻しました。「設定を保存」で反映し、「キャンセル」で元に戻ります。'); return;
      }
      requestedPreferences = { ...CloudPreferences.DEFAULT }; requestedView = { ...CloudPreferences.DEFAULT_VIEW }; syncControls();
      if (symbol) symbol.value = "";
      if (selector) selector.value = "";
      if (dateFrom) dateFrom.value = "";
      if (dateTo) dateTo.value = "";
      filter({ resetLimit: true });
      return updateFromControls();
    });
    saveButton?.addEventListener("click", async () => {
      if (settingsDialog) return commitSettingsDraft();
      if (accessLost || preferencesPending || saving) return;
      let selected;
      try { selected = readControls(); }
      catch (error) { setStatus(error.message, true); return; }
      if (selected.priceCapYen !== appliedPreferences.priceCapYen || selected.exitKey !== appliedPreferences.exitKey || selected.baseShares !== appliedPreferences.baseShares || selected.costPercent !== appliedPreferences.costPercent) {
        setStatus("選択した条件はまだ表示に反映されていません。条件を選び直し、反映後に保存してください。", true);
        return;
      }
      const preferencesToSave = { ...appliedPreferences };
      const editAtSave = editRevision;
      edited = true;
      saving = true;
      syncActionAvailability();
      try {
        const response = await fetch("/api/cloud/preferences", {
          method: "PUT", credentials: "same-origin", cache: "no-store",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ max_price: preferencesToSave.priceCapYen, exit_endpoint: preferencesToSave.exitKey, base_shares: preferencesToSave.baseShares, cost_percent: preferencesToSave.costPercent, notifications }),
        });
        if (!response.ok) throw new Error(`status:${response.status}`);
        if (editRevision !== editAtSave) {
          setStatus("保存中に表示条件が変更されました。前の設定は保存済みです。今の条件を保存するにはもう一度押してください。");
          return;
        }
        edited = false;
        setStatus(storageFailed ? "会員設定を保存しました。端末の保存は利用できません。" : "会員設定を保存しました。通知の実送信はまだ行いません。");
      } catch (_error) {
        setStatus("会員設定を保存できませんでした。ログイン・会員連携・接続を確認してください。現在の表示は利用できます。", true);
      } finally { saving = false; syncActionAvailability(); }
    });
    // Server preferences are authoritative. Do not overwrite an edit made while loading.
    fetch("/api/cloud/preferences", { credentials: "same-origin", cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("settings-unavailable");
      const data = await response.json();
      const saved = data.preferences || data;
      const serverPreferences = CloudPreferences.normalize({ priceCapYen: saved.max_price, exitKey: saved.exit_endpoint, baseShares: saved.base_shares ?? 100, costPercent: saved.cost_percent ?? 0 });
      const paidMembership = data.membership?.status === "paid";
      notifyMembershipPaid = paidMembership;
      notificationReadiness(data.membership?.status || 'unknown');
      serverAvailable = true;
      let serverApplied = false;
      if (!edited) {
        requestedPreferences = serverPreferences;
        notifications = Object.fromEntries(Object.keys(notifications).map((key) => [key, saved.notifications?.[key] === true]));
        syncControls();
        serverApplied = await applyPreferences({ persist: true });
        if (serverApplied && !edited) {
          syncNotificationControls();
          setStatus(storageFailed ? "会員設定を反映しました。端末の保存は利用できません。" : "会員設定を反映しました。");
        }
      }
      syncNotificationControls();
      if (!paidMembership && !edited && serverApplied) setStatus("表示条件の会員設定を反映しました。通知の利用には有効な有料会員資格が必要です。通知解除は行えます。");
    }).catch(() => {
      if (!edited) setStatus(storageFailed
        ? "会員設定と端末保存を利用できません。この画面で条件を選択できます。"
        : "会員設定の連携前です。表示条件はこの端末の設定を使います。");
    });
  }

  window.addEventListener?.('storage', async event => {
    if (![storageKey, viewStorageKey, DISPLAY_KEY].includes(event.key)) return;
    if (settingsDialog?.open || saving) { setStatus('他のページで保存された設定があります。現在の入力は保持しています。'); return; }
    try {
      const pref = localStorage.getItem(storageKey), view = localStorage.getItem(viewStorageKey), display = localStorage.getItem(DISPLAY_KEY);
      if (pref) requestedPreferences = CloudPreferences.normalize(JSON.parse(pref));
      if (view) { try { requestedView = CloudPreferences.normalizeView(JSON.parse(view), payload); } catch (_error) { requestedView = { ...CloudPreferences.DEFAULT_VIEW }; } }
      if (display) { appliedDisplay = CloudPreferences.normalizeDisplay(JSON.parse(display)); PAGE_SIZE = appliedDisplay.pageSize; applyDisplay(appliedDisplay); }
      syncControls(); syncDisplayControls(); await applyPreferences();
    } catch (_error) { setStatus('他のページの設定を読み込めません。現在の表示を維持します。', true); }
  });

  const downloadCSV = (text, filename) => {
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = filename;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  document.getElementById("cloud-export-csv")?.addEventListener("click", () => {
    if (accessLost || preferencesPending || !currentVariant) return;
    const preferences = appliedPreferences;
    if (payload?.version === 2) {
      const records = CloudScenario.csvMetrics(currentVariant.scenario, preferences, appliedView);
      downloadCSV(CloudPreferences.csv(records, Object.keys(records[0] || {})), `Cloud_集計_${preferences.exitKey}.csv`);
      return;
    }
    const metrics = CloudPreferences.selectCsvMetrics(
      [...(currentVariant.metrics || []), ...(currentVariant.monthlyMetrics || [])], payload?.page, appliedView.allocation);
    const records = metrics.map((row) => ({
      exit_endpoint: preferences.exitKey,
      detection_actual_close_cap_yen: preferences.priceCapYen === null ? "上限なし" : preferences.priceCapYen,
      ...(yearScope ? { signal_year_scope: appliedView.yearScope, allocation: appliedView.allocation } : {}),
      ...row,
    }));
    const columns = records.length ? Object.keys(records[0]) : ["exit_endpoint", "detection_actual_close_cap_yen", ...(yearScope ? ["signal_year_scope", "allocation"] : []), "period", "n"];
    downloadCSV(CloudPreferences.csv(records, columns), `Cloud_集計_${preferences.exitKey}.csv`);
  });
  document.getElementById("cloud-history-export-csv")?.addEventListener("click", () => {
    if (accessLost || preferencesPending) return;
    const preferences = appliedPreferences;
    const records = matchingRows.flatMap((row) => (appliedView.allocation === 'all' ? ['unique', 'stacked'] : [appliedView.allocation]).map(allocation => {
      const t = typeof CloudScenario === 'undefined' ? null : CloudScenario.trade(row.dataset, preferences);
      const units = allocation === 'stacked' ? (row.dataset.selectors || '').split(' ').filter(Boolean).length : 1;
      return {
        "検出日": row.dataset.date || "", "銘柄コード": row.dataset.symbol || "", "銘柄名": row.dataset.name || "",
        "買付方法": allocation === 'stacked' ? '条件数に応じた株数' : '同じ株数',
        "一致した条件": (row.dataset.selectors || '').split(' ').map(key => payload?.modeNames?.[key] || key).join(' / '),
        "検出日 終値": row.dataset.signalActualClose || "", "基本株数": preferences.baseShares, "買付株数": preferences.baseShares * units,
        "片道コスト%": preferences.costPercent, "終値の上限": preferences.priceCapYen ?? '上限なし',
        "買付日": (preferences.exitKey === "d6_open" ? row.dataset.d6EntryDate : row.dataset.entryDate) || "",
        "買付始値": (preferences.exitKey === "d6_open" ? row.dataset.d6EntryOpen : row.dataset.entryOpen) || "",
        "売却価格の選択": preferences.exitKey === "d5_close" ? "5営業日後 終値" : "6営業日後 始値",
        "売却予定日": preferences.exitKey === "d5_close" ? (row.dataset.d5Date || "") : (row.dataset.d6Date || ""),
        "売却価格": preferences.exitKey === "d5_close" ? (row.dataset.d5Close || "") : (row.dataset.d6Open || ""),
        "売却株数": t?.exitShares === null || !t ? '' : t.exitShares * units,
        "買付額円": t?.grossCost === null || !t ? '' : t.grossCost * units,
        "売却額円": t?.grossProceeds === null || !t ? '' : t.grossProceeds * units,
        "買付コスト円": t?.entryFee === null || !t ? '' : t.entryFee * units,
        "売却コスト円": t?.exitFee === null || !t ? '' : t.exitFee * units,
        "損益円": t?.pl === null || !t ? '' : t.pl * units,
        "騰落率%": t ? t.returnPct : (preferences.exitKey === "d5_close" ? row.dataset.d5Return : row.dataset.d6Return) || '',
        "参考値・集計対象外": row.dataset.reference === 'true' ? 'はい' : 'いいえ',
        "6営業日後 始値の取得状況": row.dataset.d6Status || "",
      };
    }));
    const columns = records.length ? Object.keys(records[0]) : ['検出日','銘柄コード','銘柄名','検出日 終値','買付日','売却予定日','売却価格','損益円','騰落率%'];
    downloadCSV(CloudPreferences.csv(records, columns), `Cloud_検出履歴_${preferences.exitKey}.csv`);
  });

})();
