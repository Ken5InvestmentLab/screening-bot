// Pure preference/CSV helpers are also exercised without a browser by Node tests.
const CloudPreferences = (() => {
  const DEFAULT = Object.freeze({ priceCapYen: 1000, exitKey: "d5_close" });
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
    return { priceCapYen: parseCap(value.priceCapYen), exitKey: value.exitKey };
  };
  const variantKey = (payload, prefs) => {
    if (prefs.priceCapYen === null) return `${prefs.exitKey}:all`;
    let bound = "empty";
    for (const [index, price] of (payload.priceBreakpoints || []).entries()) {
      if (price <= prefs.priceCapYen) bound = payload.priceBreakpointKeys?.[index] || String(price);
      else break;
    }
    return `${prefs.exitKey}:${bound}`;
  };
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
  return { DEFAULT, PRESETS, parseCap, normalize, variantKey, matchesCap, csv };
})();
if (typeof module !== "undefined" && module.exports) module.exports = CloudPreferences;

(() => {
  if (typeof document === "undefined") return;
  const THEME_KEY = "weakEarlyBetaTheme:v1";
  const PAGE_SIZE = 20;
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

  const symbol = document.getElementById("symbol-filter");
  const selector = document.getElementById("selector-filter");
  const dateFrom = document.getElementById("history-date-from");
  const dateTo = document.getElementById("history-date-to");
  const clear = document.getElementById("clear-search");
  const resultCount = document.getElementById("search-result-count");
  const loadMore = document.getElementById("history-load-more");
  const collapse = document.getElementById("history-collapse");
  // The empty-history message is a table row, but never a detection or CSV row.
  const rows = Array.from(document.querySelectorAll("#detection-table tbody tr[data-date]"));
  const normalize = (value) => String(value || "").normalize("NFKC").trim().toLowerCase();
  let visibleLimit = PAGE_SIZE;
  // Only applied preferences may be used by visible rows, endpoint cells or CSV.
  // A requested choice can remain in flight while its aggregate is decompressed.
  let appliedPreferences = { ...CloudPreferences.DEFAULT };
  let requestedPreferences = { ...appliedPreferences };
  let matchingRows = [];

  const initialQuery = new URLSearchParams(window.location.search).get("q");
  if (symbol && initialQuery) symbol.value = initialQuery;

  const filter = ({ resetLimit = false } = {}) => {
    if (resetLimit) visibleLimit = PAGE_SIZE;
    const symbolValue = normalize(symbol?.value);
    const selectorValue = selector?.value || "";
    const fromValue = dateFrom?.value || "";
    const toValue = dateTo?.value || "";
    const matchedRows = rows.filter((row) => {
      const searchTarget = normalize(row.dataset.search || row.dataset.symbol);
      const signalDate = row.dataset.date || "";
      return CloudPreferences.matchesCap(row.dataset.signalActualClose,
        row.dataset.signalPriceVerified || row.dataset.signalActualCloseStatus, appliedPreferences.priceCapYen)
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
    if (collapse) collapse.hidden = visibleLimit <= PAGE_SIZE || matchedRows.length <= PAGE_SIZE;
  };

  for (const control of [symbol, dateFrom, dateTo]) {
    control?.addEventListener("input", () => filter({ resetLimit: true }));
    control?.addEventListener("change", () => filter({ resetLimit: true }));
  }
  symbol?.addEventListener("search", () => filter({ resetLimit: true }));
  selector?.addEventListener("change", () => filter({ resetLimit: true }));
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

  const settings = document.getElementById("cloud-price-preset");
  const customPrice = document.getElementById("cloud-price-custom");
  const customPriceField = document.getElementById("cloud-price-custom-field");
  const endpoint = document.getElementById("cloud-exit-endpoint");
  const saveButton = document.getElementById("cloud-settings-save");
  const status = document.getElementById("cloud-settings-status");
  const payloadElement = document.getElementById("cloud-analytics-data");
  const content = document.getElementById("cloud-analytics-content");
  const storageKey = "cloudReportPreferences:v1";
  let payload = null;
  let currentVariant = null;
  let renderRevision = 0;
  let preferencesPending = false;
  let saving = false;
  const exportButton = document.getElementById("cloud-export-csv");
  const historyExportButton = document.getElementById("cloud-history-export-csv");
  const decodedVariants = new Map();
  let edited = false;
  let editRevision = 0;
  let storageFailed = false;
  let serverAvailable = false;
  let notifications = { new_detection: false, reminder: false, result: false };
  const notifyInputs = {};
  const setStatus = (message, invalid = false) => {
    if (!status) return;
    status.textContent = message;
    status.dataset.state = invalid ? "error" : "info";
  };
  try { if (payloadElement) payload = JSON.parse(payloadElement.textContent); }
  catch (_error) { setStatus("表示用データを読み込めません。ページを再読込してください。", true); }

  if (settings && endpoint) {
    const host = document.createElement("details");
    host.className = "cloud-notification-settings";
    host.innerHTML = '<summary>プッシュ通知の設定</summary><p>通知は準備中です。この設定の保存では通知を送信しません。初期設定はすべてOFFです。</p>';
    for (const [key, label] of Object.entries({ new_detection: "新しい検出", reminder: "選択した確定日の朝8時（日本時間）", result: "選択した実価格の取得・確定後の結果" })) {
      const element = document.createElement("label");
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.id = `cloud-notify-${key}`;
      checkbox.checked = false;
      checkbox.disabled = true;
      element.append(checkbox, document.createTextNode(` ${label}`));
      host.append(element);
      notifyInputs[key] = checkbox;
      checkbox.addEventListener("change", () => {
        edited = true;
        editRevision += 1;
        notifications[key] = checkbox.checked;
        setStatus("通知設定は未保存です。「設定を保存」で会員設定を更新します。");
      });
    }
    const note = document.createElement("p");
    note.textContent = "朝8時は「今日は確定日」のお知らせです。始値・終値や結果が確定したという通知ではありません。";
    host.append(note);
    const unsubscribe = document.createElement("button");
    unsubscribe.type = "button";
    unsubscribe.id = "cloud-notifications-off";
    unsubscribe.textContent = "通知をすべてOFF・購読解除";
    unsubscribe.disabled = true;
    host.append(unsubscribe);
    (document.getElementById("cloud-notification-settings") || document.getElementById("cloud-preferences") || saveButton?.parentElement || settings.parentElement).append(host);
    unsubscribe.addEventListener("click", async () => {
      unsubscribe.disabled = true;
      try {
        const response = await fetch("/api/cloud/push-subscriptions", { method: "DELETE", credentials: "same-origin", cache: "no-store" });
        if (!response.ok) throw new Error("unsubscribe");
        notifications = { new_detection: false, reminder: false, result: false };
        for (const input of Object.values(notifyInputs)) input.checked = false;
        setStatus("通知をすべてOFFにして、購読を解除しました。");
      } catch (_error) { setStatus("解除を確認できません。接続を確認してもう一度お試しください。", true); }
      finally { unsubscribe.disabled = !serverAvailable; }
    });
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
  };
  const decodeVariant = async (key) => {
    if (decodedVariants.has(key)) return decodedVariants.get(key);
    const packed = payload.variants[key];
    if (!packed) throw new Error("missing variant");
    let variant = packed;
    if (typeof packed.gzip === "string") {
      if (typeof DecompressionStream === "undefined") throw new Error("decompression unavailable");
      const bytes = Uint8Array.from(atob(packed.gzip), (character) => character.charCodeAt(0));
      const stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream("gzip"));
      variant = await new Response(stream).json();
    }
    if (typeof variant.html !== "string" || !Array.isArray(variant.metrics) || !Array.isArray(variant.monthlyMetrics)) throw new Error("invalid variant");
    // Retain only two decoded choices; compressed histories can remain compact
    // on mobile even when many exact nominal-price boundaries are available.
    if (decodedVariants.size >= 2) decodedVariants.delete(decodedVariants.keys().next().value);
    decodedVariants.set(key, variant);
    return variant;
  };
  const syncActionAvailability = () => {
    if (exportButton) exportButton.disabled = preferencesPending || !currentVariant;
    if (historyExportButton) historyExportButton.disabled = preferencesPending;
    if (saveButton) saveButton.disabled = preferencesPending || saving;
    content?.setAttribute("aria-busy", preferencesPending ? "true" : "false");
  };
  const applyPreferences = async ({ persist = false } = {}) => {
    const revision = ++renderRevision;
    const requested = { ...requestedPreferences };
    preferencesPending = true;
    syncActionAvailability();
    let nextVariant = currentVariant;
    if (payloadElement && content) {
      try {
        if (!payload) throw new Error("analytics payload unavailable");
        nextVariant = await decodeVariant(CloudPreferences.variantKey(payload, requested));
        if (revision !== renderRevision) return false;
      } catch (_error) {
        if (revision !== renderRevision) return false;
        // Keep the last complete view and its CSV usable; failed requests are
        // neither persisted locally nor sent as the current member preference.
        requestedPreferences = { ...appliedPreferences };
        syncControls(appliedPreferences);
        preferencesPending = false;
        syncActionAvailability();
        setStatus("この条件の集計を読み込めません。表示・CSV・選択欄を直前に表示できた条件へ戻しました。この変更は保存していません。", true);
        return false;
      }
    }
    // No await inside this commit: aggregates, history, endpoint cells and the
    // parameters used by both exports change together within one browser task.
    if (payload && content) {
      content.innerHTML = nextVariant.html;
      initializePagination(content);
    }
    currentVariant = nextVariant;
    appliedPreferences = requested;
    for (const element of document.querySelectorAll("[data-exit-key]")) {
      element.hidden = element.dataset.exitKey !== appliedPreferences.exitKey;
    }
    filter({ resetLimit: true });
    if (persist) {
      try { localStorage.setItem(storageKey, JSON.stringify(appliedPreferences)); storageFailed = false; }
      catch (_error) { storageFailed = true; }
    }
    preferencesPending = false;
    syncActionAvailability();
    return true;
  };
  const readControls = () => CloudPreferences.normalize({
    priceCapYen: settings.value === "unlimited" ? null : (settings.value === "custom" ? customPrice?.value : settings.value),
    exitKey: endpoint.value,
  });
  const updateFromControls = async () => {
    edited = true;
    editRevision += 1;
    const editAtChange = editRevision;
    if (customPrice) {
      customPrice.hidden = settings.value !== "custom";
      if (customPriceField) customPriceField.hidden = settings.value !== "custom";
      customPrice.disabled = settings.value !== "custom";
    }
    try {
      const next = readControls();
      requestedPreferences = next;
      customPrice?.setAttribute("aria-invalid", "false");
      setStatus("表示条件を反映しています。反映が終わるまでCSV出力と会員設定の保存はできません。");
      if (await applyPreferences({ persist: true }) && editRevision === editAtChange) setStatus(storageFailed
        ? "表示に適用しました。この端末では保存できません。会員設定の保存をお試しください。"
        : "表示に適用しました。会員設定に残すには「設定を保存」を押してください。");
    } catch (error) {
      // An invalid newer edit must also cancel an older decompression request.
      renderRevision += 1;
      requestedPreferences = { ...appliedPreferences };
      preferencesPending = false;
      syncActionAvailability();
      customPrice?.setAttribute("aria-invalid", "true");
      setStatus(`${error.message} 前の有効な設定を表示しています。`, true);
    }
  };
  if (settings && endpoint) {
    try {
      const saved = localStorage.getItem(storageKey);
      if (saved) requestedPreferences = CloudPreferences.normalize(JSON.parse(saved));
    } catch (_error) { storageFailed = true; }
    syncControls();
    applyPreferences();
    settings.addEventListener("change", updateFromControls);
    endpoint.addEventListener("change", updateFromControls);
    customPrice?.addEventListener("input", updateFromControls);
    saveButton?.addEventListener("click", async () => {
      if (preferencesPending || saving) return;
      let selected;
      try { selected = readControls(); }
      catch (error) { setStatus(error.message, true); return; }
      if (selected.priceCapYen !== appliedPreferences.priceCapYen || selected.exitKey !== appliedPreferences.exitKey) {
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
          body: JSON.stringify({ max_price: preferencesToSave.priceCapYen, exit_endpoint: preferencesToSave.exitKey, notifications }),
        });
        if (!response.ok) throw new Error(`status:${response.status}`);
        if (editRevision !== editAtSave) {
          setStatus("保存中に表示条件が変更されました。前の設定は保存済みです。今の条件を保存するにはもう一度押してください。");
          return;
        }
        edited = false;
        setStatus(storageFailed ? "会員設定を保存しました。端末内の補助保存は利用できません。" : "会員設定を保存しました。通知の実送信はまだ行いません。");
      } catch (_error) {
        setStatus("会員設定を保存できませんでした。ログイン・会員連携・接続を確認してください。現在の表示は利用できます。", true);
      } finally { saving = false; syncActionAvailability(); }
    });
    // Server preferences are authoritative. Do not overwrite an edit made while loading.
    fetch("/api/cloud/preferences", { credentials: "same-origin", cache: "no-store" }).then(async (response) => {
      if (!response.ok) throw new Error("settings-unavailable");
      const data = await response.json();
      const saved = data.preferences || data;
      const serverPreferences = CloudPreferences.normalize({ priceCapYen: saved.max_price, exitKey: saved.exit_endpoint });
      const paidMembership = data.membership?.status === "paid";
      serverAvailable = true;
      let serverApplied = false;
      if (!edited) {
        requestedPreferences = serverPreferences;
        notifications = Object.fromEntries(Object.keys(notifications).map((key) => [key, saved.notifications?.[key] === true]));
        syncControls();
        serverApplied = await applyPreferences({ persist: true });
        if (serverApplied && !edited) {
          for (const [key, input] of Object.entries(notifyInputs)) input.checked = notifications[key];
          setStatus(storageFailed ? "会員設定を反映しました。端末内の補助保存は利用できません。" : "会員設定を反映しました。");
        }
      }
      for (const input of Object.values(notifyInputs)) input.disabled = !paidMembership;
      const off = document.getElementById("cloud-notifications-off");
      if (off) off.disabled = false;
      if (!paidMembership && !edited && serverApplied) setStatus("表示条件の会員設定を反映しました。通知の利用には有効な有料会員資格が必要です。通知解除は行えます。");
    }).catch(() => {
      if (!edited) setStatus(storageFailed
        ? "会員設定と端末保存を利用できません。この画面で条件を選択できます。"
        : "会員設定の連携前です。表示条件はこの端末の補助設定を使用します。");
    });
  }

  const downloadCSV = (text, filename) => {
    const url = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url; link.download = filename;
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  document.getElementById("cloud-export-csv")?.addEventListener("click", () => {
    if (preferencesPending || !currentVariant) return;
    const preferences = appliedPreferences;
    const records = [...(currentVariant.metrics || []), ...(currentVariant.monthlyMetrics || [])].map((row) => ({
      exit_endpoint: preferences.exitKey,
      detection_actual_close_cap_yen: preferences.priceCapYen === null ? "上限なし" : preferences.priceCapYen,
      ...row,
    }));
    const columns = records.length ? Object.keys(records[0]) : ["exit_endpoint", "detection_actual_close_cap_yen", "period", "n"];
    downloadCSV(CloudPreferences.csv(records, columns), `Cloud_集計_${preferences.exitKey}.csv`);
  });
  document.getElementById("cloud-history-export-csv")?.addEventListener("click", () => {
    if (preferencesPending) return;
    const preferences = appliedPreferences;
    const records = matchingRows.map((row) => ({
      "検出日": row.dataset.date || "",
      "銘柄コード": row.dataset.symbol || "",
      "モード": row.dataset.selectors || "",
      "検出日の実終値": row.dataset.signalActualClose || "",
      "入口日": (preferences.exitKey === "d6_open" ? row.dataset.d6EntryDate : row.dataset.entryDate) || "",
      "入口価格（D5過去履歴は調整参考値を含む）": (preferences.exitKey === "d6_open" ? row.dataset.d6EntryOpen : row.dataset.entryOpen) || "",
      "確定日選択": preferences.exitKey === "d5_close" ? "検出から5営業日後 終値" : "検出から6営業日後 始値",
      "確定予定日": preferences.exitKey === "d5_close" ? (row.dataset.d5Date || "") : (row.dataset.d6Date || ""),
      "確定価格": preferences.exitKey === "d5_close" ? (row.dataset.d5Close || "") : (row.dataset.d6Open || ""),
      "騰落率": preferences.exitKey === "d5_close" ? (row.dataset.d5Return || "") : (row.dataset.d6Return || ""),
      "6営業日後始値の状態": row.dataset.d6Status || "",
    }));
    const columns = ["検出日", "銘柄コード", "モード", "検出日の実終値", "入口日", "入口価格（D5過去履歴は調整参考値を含む）", "確定日選択", "確定予定日", "確定価格", "騰落率", "6営業日後始値の状態"];
    downloadCSV(CloudPreferences.csv(records, columns), `Cloud_検出履歴_${preferences.exitKey}.csv`);
  });

})();
