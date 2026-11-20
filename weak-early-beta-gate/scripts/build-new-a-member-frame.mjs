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
body[data-cloud-mode=member] .member-level{min-inline-size:0;max-width:100%;margin:0 0 8px;padding:0;border:0}
body[data-cloud-mode=member] .member-level legend{padding:0;margin-bottom:5px;color:var(--muted);font-size:13px}
body[data-cloud-mode=member] .member-level-options{display:inline-flex;max-width:100%;flex-wrap:wrap;gap:4px;padding:3px;border:1px solid var(--line);border-radius:24px;background:var(--panel-solid)}
body[data-cloud-mode=member] .member-level-options label{position:relative;cursor:pointer;display:block}
body[data-cloud-mode=member] .member-level-options input{position:absolute;inline-size:1px;block-size:1px;clip-path:inset(50%);overflow:hidden}
body[data-cloud-mode=member] .member-level-options span{display:flex;align-items:center;justify-content:center;min-height:44px;padding:0 13px;border:1px solid transparent;border-radius:20px;color:var(--muted);font-weight:650}
body[data-cloud-mode=member] .member-level-options input:checked + span{background:color-mix(in srgb,var(--blue) 16%,var(--panel-solid));border-color:var(--blue);color:var(--ink)}
body[data-cloud-mode=member] .member-level-options input:focus-visible + span{outline:2px solid var(--blue);outline-offset:2px}
body[data-cloud-mode=member] .member-purchase{display:inline-flex;align-items:center;min-height:44px;padding:8px 14px;border:1px solid var(--blue);border-radius:9px;color:var(--blue);font-weight:700;text-decoration:none}
body[data-cloud-mode=member] .member-purchase:hover{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid))}
body[data-cloud-mode=member] form label{display:block;margin:14px 0}
body[data-cloud-mode=member] form select,body[data-cloud-mode=member] form input{max-width:100%;min-height:44px}
`;

export async function buildNewAMemberFrame(gate, html, settingsModal, settingsTrigger, helpModal) {
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
    .replace('id="cloud-help-open"', 'id="cloud-help-open" data-member-premium-nav hidden')
    .replace('</style>', memberStyles + '</style>');
  const generated = [
    '// Build-only data-free member shell. Do not commit generated files.',
    'const SHELL=' + JSON.stringify(shell) + ';',
    'const SETTINGS_DIALOG=' + JSON.stringify(settingsModal) + ';',
    'const HELP_DIALOG=' + JSON.stringify(helpModal) + ';',
    'const SETTINGS_TRIGGER=' + JSON.stringify(settingsTrigger) + ';',
    'export function memberFrame(path: string, tier: "premium" | "free" = "premium"): string {',
    '  const page = path === "/weak_early_beta_analytics.html" ? "analytics" : path === "/weak_early_beta_settings.html" ? "settings" : "home";',
    '  const title = page === "analytics" ? "アナリティクス" : page === "settings" ? "設定" : "ダッシュボード";',
    '  const content = \'<p id="member-state" role="status">読込中</p><button id="member-retry" hidden>再試行</button><div id="member-content"></div>\';',
    '  const view = page === "settings" && tier === "premium" ? \'<section class="panel cloud-settings" aria-labelledby="cloud-settings-title"><h1 id="cloud-settings-title">設定</h1>\' + content + \'</section>\' : content;',
    '  const settings = page === "settings" && tier === "premium" ? \'<script src="/new-a-assets/member-settings.js" defer></script>\' : "";',
    '  return SHELL.replaceAll("{{INITIAL_THEME}}", "dark").replace("{{INITIAL_THEME_SCRIPT}}", "").replaceAll("{{TITLE}}", title).replaceAll("{{PAGE}}", page).replace("{{MEMBER_SETTINGS_SCRIPT}}", settings).replace("{{HELP_DIALOG}}", HELP_DIALOG).replace("{{SETTINGS_DIALOG}}", page !== "settings" && tier === "premium" ? SETTINGS_DIALOG : "").replace("{{SETTINGS_TRIGGER}}", page !== "settings" && tier === "premium" ? SETTINGS_TRIGGER : "").replace("{{VIEW}}", view);',
    '}',
    '',
  ].join('\n');
  await fs.mkdir(path.join(gate, 'src'), { recursive: true });
  await fs.writeFile(path.join(gate, 'src/new-a-member-frame.generated.ts'), generated);
}
