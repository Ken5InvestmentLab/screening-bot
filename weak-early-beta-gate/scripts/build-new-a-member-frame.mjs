import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';

const memberStyles = `
body[data-cloud-mode=member]{min-width:0;overflow-wrap:anywhere}
body[data-cloud-mode=member] main,body[data-cloud-mode=member] #member-content{width:100%;min-width:0;max-width:1440px}
body[data-cloud-mode=member] .panel,body[data-cloud-mode=member] .kpi{min-width:0;max-width:100%}
body[data-cloud-mode=member] .research-chart{min-width:0}
body[data-cloud-mode=member] .page-heading{flex-wrap:wrap}
body[data-cloud-mode=member] .nav{display:flex;flex-wrap:wrap}
body[data-cloud-mode=member] .cloud-main-nav,body[data-cloud-mode=member] .cloud-primary-nav{min-width:0;max-width:100%;display:flex;flex-wrap:wrap}
body[data-cloud-mode=member] .cloud-primary-nav a{min-width:0}
body[data-cloud-mode=member] form label{display:block;margin:14px 0}
body[data-cloud-mode=member] form select,body[data-cloud-mode=member] form input{max-width:100%;min-height:44px}
`;

export async function buildNewAMemberFrame(gate, html) {
  const ownerGuard = '<script src="/auth/guard.js" defer></script>';
  const ownerLoader = '<script src="/new-a-assets/owner-loader.js" defer></script>';
  const memberScripts = ['member-presentation', 'member-settings', 'member-loader']
    .map(name => '<script src="/new-a-assets/' + name + '.js" defer></script>')
    .join('');
  assert(html.includes(ownerGuard) && html.includes(ownerLoader), 'Owner shell scripts changed');
  const shell = html
    .replace(ownerGuard, '')
    .replace(ownerLoader, memberScripts)
    .replace('<body data-page=', '<body data-cloud-mode="member" data-page=')
    .replace('</style>', memberStyles + '</style>');
  const generated = [
    '// Build-only data-free member shell. Do not commit generated files.',
    'const SHELL=' + JSON.stringify(shell) + ';',
    'export function memberFrame(path: string): string {',
    '  const page = path === "/weak_early_beta_analytics.html" ? "analytics" : path === "/weak_early_beta_settings.html" ? "settings" : "home";',
    '  const title = page === "analytics" ? "アナリティクス" : page === "settings" ? "設定" : "ダッシュボード";',
    '  const view = \'<p id="member-state" role="status">読込中</p><button id="member-retry" hidden>再試行</button><div id="member-content"></div>\';',
    '  return SHELL.replaceAll("{{INITIAL_THEME}}", "dark").replace("{{INITIAL_THEME_SCRIPT}}", "").replaceAll("{{TITLE}}", title).replaceAll("{{PAGE}}", page).replace("{{VIEW}}", view);',
    '}',
    '',
  ].join('\n');
  await fs.mkdir(path.join(gate, 'src'), { recursive: true });
  await fs.writeFile(path.join(gate, 'src/new-a-member-frame.generated.ts'), generated);
}
