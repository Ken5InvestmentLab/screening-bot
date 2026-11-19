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
body[data-cloud-mode=member] [data-member-premium-nav][hidden]{display:none!important}
body[data-cloud-mode=member] .member-dashboard-panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:14px}
body[data-cloud-mode=member] .member-detections{display:grid;gap:8px;list-style:none;padding:0;margin:0}
body[data-cloud-mode=member] .member-detections li{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;padding:8px 0;border-bottom:1px solid var(--line)}
body[data-cloud-mode=member] .member-detections time{color:var(--muted)}
body[data-cloud-mode=member] .member-purchase{display:inline-flex;align-items:center;min-height:44px;padding:8px 14px;border:1px solid var(--blue);border-radius:9px;color:var(--blue);font-weight:700;text-decoration:none}
body[data-cloud-mode=member] .member-purchase:hover{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid))}
body[data-cloud-mode=member] form label{display:block;margin:14px 0}
body[data-cloud-mode=member] form select,body[data-cloud-mode=member] form input{max-width:100%;min-height:44px}
`;

export async function buildNewAMemberFrame(gate, html) {
  const ownerGuard = '<script src="/auth/guard.js" defer></script>';
  const ownerLoader = '<script src="/new-a-assets/owner-loader.js" defer></script>';
  const memberScripts = ['member-presentation', 'member-loader']
    .map(name => '<script src="/new-a-assets/' + name + '.js" defer></script>')
    .join('');
  assert(html.includes(ownerGuard) && html.includes(ownerLoader), 'Owner shell scripts changed');
  const shell = html
    .replace(ownerGuard, '')
    .replace(ownerLoader, '{{MEMBER_SETTINGS_SCRIPT}}' + memberScripts)
    .replace('<body data-page=', '<body data-cloud-mode="member" data-page=')
    .replaceAll(/href="\.\/weak_early_beta_(?:analytics|settings)\.html"/g, '$& data-member-premium-nav hidden')
    .replace('<details class="cloud-more-menu">', '<details class="cloud-more-menu" data-member-premium-nav hidden>')
    .replace('</style>', memberStyles + '</style>');
  const generated = [
    '// Build-only data-free member shell. Do not commit generated files.',
    'const SHELL=' + JSON.stringify(shell) + ';',
    'export function memberFrame(path: string, tier: "premium" | "free" = "premium"): string {',
    '  const page = path === "/weak_early_beta_analytics.html" ? "analytics" : path === "/weak_early_beta_settings.html" ? "settings" : "home";',
    '  const title = page === "analytics" ? "アナリティクス" : page === "settings" ? "設定" : "ダッシュボード";',
    '  const view = \'<p id="member-state" role="status">読込中</p><button id="member-retry" hidden>再試行</button><div id="member-content"></div>\';',
    '  const settings = page === "settings" && tier === "premium" ? \'<script src="/new-a-assets/member-settings.js" defer></script>\' : "";',
    '  return SHELL.replaceAll("{{INITIAL_THEME}}", "dark").replace("{{INITIAL_THEME_SCRIPT}}", "").replaceAll("{{TITLE}}", title).replaceAll("{{PAGE}}", page).replace("{{MEMBER_SETTINGS_SCRIPT}}", settings).replace("{{VIEW}}", view);',
    '}',
    '',
  ].join('\n');
  await fs.mkdir(path.join(gate, 'src'), { recursive: true });
  await fs.writeFile(path.join(gate, 'src/new-a-member-frame.generated.ts'), generated);
}
