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

  function mount(root) {
    root.querySelector('section[aria-labelledby="analytics-export"]')?.remove();
    const source = root.querySelector('#new-a-reference-daily-values');
    const table = root.querySelector('#new-a-daily-table table');
    const more = root.querySelector('#new-a-daily-more');
    if (!source?.content || !table?.tBodies[0] || !more) return;
    const labels = Array.from(table.tHead?.rows[0]?.cells ?? [], cell => cell.textContent);
    if (labels.length !== format.length) return;

    const { daily } = JSON.parse(source.content.textContent);
    if (!Array.isArray(daily) || !daily.every(isDailyRow)) {
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
  }

  global.NewAReferenceAnalytics = { mount };
})(globalThis);
