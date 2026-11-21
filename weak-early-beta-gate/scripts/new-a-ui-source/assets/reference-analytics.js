/* Controls for verified shared analytics. Only aggregate simulation values are supplied. */
(function (global) {
  'use strict';

  const pageSize = 50;
  const number = value => value === null ? '未確定' : value.toLocaleString('ja-JP', { maximumFractionDigits: 2 });
  const yen = value => value === null ? '未確定' : number(value) + '円';
  const status = unresolved => unresolved ? '保留' : '確定';
  const format = [value => value, yen, yen, yen, number, status];
  const date = /^\d{4}-\d{2}-\d{2}$/;

  function isDailyRow(row) {
    return Array.isArray(row) && row.length === 6 && typeof row[0] === 'string' && date.test(row[0])
      && row.slice(1, 4).every(value => value === null || Number.isFinite(value))
      && (row[4] === null || (Number.isSafeInteger(row[4]) && row[4] >= 0))
      && typeof row[5] === 'boolean';
  }

  function dailyValues(text) {
    const { daily } = JSON.parse(text);
    if (!Array.isArray(daily) || !daily.every(isDailyRow)) {
      throw Error('invalid_reference_analytics');
    }
    return daily;
  }

  function mount(root, loadDaily) {
    root.querySelector('section[aria-labelledby="analytics-export"]')?.remove();
    const source = root.querySelector('#new-a-reference-daily-values');
    const table = root.querySelector('#new-a-daily-table table');
    const more = root.querySelector('#new-a-daily-more');
    if (!table?.tBodies[0] || !more) return;
    const labels = Array.from(table.tHead?.rows[0]?.cells ?? [], cell => cell.textContent);
    if (labels.length !== format.length) return;

    const body = table.tBodies[0];
    let daily = source?.content ? dailyValues(source.content.textContent) : null;
    source?.remove();
    function appendPage() {
      if (!daily) return;
      const shown = body.rows.length;
      const fragment = document.createDocumentFragment();
      for (const row of daily.slice(shown, shown + pageSize)) {
        const entry = document.createElement('tr');
        format.forEach((transform, index) => {
          const cell = document.createElement('td');
          cell.dataset.label = labels[index];
          cell.textContent = transform(row[index]);
          entry.append(cell);
        });
        fragment.append(entry);
      }
      body.append(fragment);
      more.hidden = body.rows.length >= daily.length;
    }
    more.addEventListener('click', appendPage);
    if (daily || !loadDaily) return;

    const details = table.closest('details');
    if (!details) return;
    more.hidden = true;
    const message = document.createElement('p');
    message.setAttribute('role', 'status');
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'settings-secondary';
    retry.textContent = '再試行';
    retry.hidden = true;
    details.append(message, retry);

    let pending = false;
    async function openDaily() {
      if (!details.open || pending || daily) return;
      pending = true;
      message.textContent = '日次表を読み込み中…';
      retry.hidden = true;
      try {
        const text = await loadDaily();
        if (text === null) return;
        daily = dailyValues(text);
        appendPage();
        message.remove();
        retry.remove();
      } catch {
        message.textContent = '日次表を読み込めませんでした。';
        retry.hidden = false;
      } finally {
        pending = false;
      }
    }
    details.addEventListener('toggle', openDaily);
    retry.addEventListener('click', openDaily);
    if (details.open) void openDaily();
  }

  global.NewAReferenceAnalytics = { mount };
})(globalThis);
