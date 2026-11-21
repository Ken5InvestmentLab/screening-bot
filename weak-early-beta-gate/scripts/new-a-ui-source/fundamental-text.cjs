const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]);
const linkedFields = new Set(['ファンダ分析', 'ファンダ要点', '開示リンク', '出典', 'Sources']);
const linkLine = /^[ \t]*(?:・[ \t]*)?\[(.+)\]\((https:\/\/[^\s()<>\\\x00-\x1f\x7f]+)\)[ \t]*$/u;
// A title may contain escaped Markdown brackets or a balanced pair in a document name.
const titlePattern = /^(?:\\[\[\]]|\\(?![\[\]])|[^[\]\\]|\[(?:\\[\[\]]|\\(?![\[\]])|[^[\]\\])+\])+$/u;

module.exports = function fundamentalText({ label, text }) {
  return String(text ?? '').split(/\r\n?|\n/u).map(line => {
    const match = linkedFields.has(label) && linkLine.exec(line);
    if (!match || !titlePattern.test(match[1])) return escapeHtml(line);
    const title = match[1].replace(/\\([\[\]])/gu, '$1').trim();
    if (!title || /^(?:https?:\/\/|www\.)/iu.test(title)) return escapeHtml(line);

    let address;
    try { address = new URL(match[2]); } catch { return escapeHtml(line); }
    if (address.protocol !== 'https:' || !address.hostname || address.username || address.password) {
      return escapeHtml(line);
    }
    return '・<a href="' + escapeHtml(address.href) + '" target="_blank" rel="noopener noreferrer">'
      + escapeHtml(title) + '</a>';
  }).join('<br>');
};
