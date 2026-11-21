/* Controls for verified shared analytics. Only aggregate simulation values are supplied. */
(function (global) {
  'use strict';

  const pageSize = 50;
  const number = value => value === null ? '未確定' : value.toLocaleString('ja-JP', { maximumFractionDigits: 2 });
  const yen = value => value === null ? '未確定' : number(value) + '円';
  const status = unresolved => unresolved ? '保留' : '確定';
  const format = [value => value, yen, yen, yen, number, status];
  const date = /^\d{4}-\d{2}-\d{2}$/;
  const scalar = value => value === null || typeof value === 'string' || Number.isFinite(value);

  function isDailyRow(row) {
    return Array.isArray(row) && row.length === 6 && typeof row[0] === 'string' && date.test(row[0])
      && row.slice(1, 4).every(value => value === null || Number.isFinite(value))
      && (row[4] === null || (Number.isSafeInteger(row[4]) && row[4] >= 0))
      && typeof row[5] === 'boolean';
  }

  function csvCell(value) {
    const text = value === null ? '' : String(value);
    const prefix = typeof value === 'string' && /^[=+@\-\t\r]/.test(text) ? "'" : '';
    return '"' + prefix + text.replaceAll('"', '""') + '"';
  }

  function download(name, rows) {
    const csv = '\ufeff' + rows.map(row => row.map(csvCell).join(',')).join('\r\n') + '\r\n';
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Cloud2_A_' + name + '.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function mount(root) {
    const source = root.querySelector('#new-a-reference-daily-values');
    const table = root.querySelector('#new-a-daily-table table');
    const more = root.querySelector('#new-a-daily-more');
    const summaryButton = root.querySelector('#new-a-export-summary');
    const dailyButton = root.querySelector('#new-a-export-daily');
    if (!source?.content || !table?.tBodies[0] || !more || !summaryButton || !dailyButton) return;
    const labels = Array.from(table.tHead?.rows[0]?.cells ?? [], cell => cell.textContent);
    if (labels.length !== format.length) return;

    const { daily, summary } = JSON.parse(source.content.textContent);
    if (!Array.isArray(daily) || !daily.every(isDailyRow) || !Array.isArray(summary)
      || !summary.every(row => Array.isArray(row) && row.length === 2 && typeof row[0] === 'string' && scalar(row[1]))) {
      throw Error('invalid_reference_analytics');
    }

    source.remove();
    const body = table.tBodies[0];
    let shown = body.rows.length;
    more.addEventListener('click', () => {
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
      shown = body.rows.length;
      more.hidden = shown >= daily.length;
    });
    summaryButton.addEventListener('click', () => download('summary', [['項目', '値'], ...summary]));
    dailyButton.addEventListener('click', () => {
      download('daily', [labels, ...daily.map(row => [...row.slice(0, -1), status(row.at(-1))])]);
    });
  }

  global.NewAReferenceAnalytics = { mount };
})(globalThis);
