import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';

const memberStyles = `
body[data-cloud-mode=member] .member-purchase{display:inline-flex;align-items:center;min-height:44px;padding:8px 14px;border:1px solid var(--blue);border-radius:9px;color:var(--blue);font-weight:700;text-decoration:none}
body[data-cloud-mode=member] .member-purchase:hover{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid))}
.member-locked-row{border:1px solid var(--line);border-radius:12px;background:var(--panel-solid)}
.member-locked-row summary{display:flex;align-items:center;justify-content:space-between;gap:4px 12px;flex-wrap:wrap;min-height:44px;padding:6px 12px;cursor:pointer;font-weight:650}
.member-locked-row summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:12px}
.member-locked-message{color:var(--muted)}
.member-locked-action{color:var(--blue);white-space:nowrap}
.member-locked-upgrade{padding:0 12px 12px}
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
    .replace(ownerLoader, '{{MEMBER_PAGE_SCRIPTS}}' + memberScripts)
    .replace('<body data-page=', '<body data-cloud-mode="member" data-page=')
    .replace('</style>', memberStyles + '</style>');
  const generated = [
    '// Build-only data-free member shell. Do not commit generated files.',
    'const SHELL=' + JSON.stringify(shell) + ';',
    'const SETTINGS_DIALOG=' + JSON.stringify(settingsModal) + ';',
    'const HELP_DIALOG=' + JSON.stringify(helpModal) + ';',
    'const SETTINGS_TRIGGER=' + JSON.stringify(settingsTrigger) + ';',
    'export function memberFrame(path: string, _tier: "premium" | "free" = "premium"): string {',
    '  const page = path === "/weak_early_beta_analytics.html" ? "analytics" : path === "/weak_early_beta_settings.html" ? "settings" : "home";',
    '  const title = page === "analytics" ? "アナリティクス" : page === "settings" ? "設定" : "ダッシュボード";',
    '  const content = \'<p id="member-state" role="status">読込中</p><button id="member-retry" hidden>再試行</button><div id="member-content"></div>\';',
    '  const view = page === "settings" ? \'<section class="panel cloud-settings" aria-labelledby="cloud-settings-title"><h1 id="cloud-settings-title">設定</h1>\' + content + \'</section>\' : content;',
    '  const pageScript = page === "settings" ? \'<script src="/new-a-assets/member-settings.js" defer></script>\' : page === "analytics" ? \'<script src="/new-a-assets/reference-analytics.js" defer></script>\' : "";',
    '  const selected = "./weak_early_beta_" + (page === "home" ? "latest" : page) + ".html";',
    '  return SHELL.replaceAll("{{INITIAL_THEME}}", "dark").replace("{{INITIAL_THEME_SCRIPT}}", "").replaceAll("{{TITLE}}", title).replaceAll("{{PAGE}}", page).replace("{{MEMBER_PAGE_SCRIPTS}}", pageScript).replace("{{HELP_DIALOG}}", HELP_DIALOG).replace("{{SETTINGS_DIALOG}}", page !== "settings" ? SETTINGS_DIALOG : "").replace("{{SETTINGS_TRIGGER}}", page !== "settings" ? SETTINGS_TRIGGER : "").replace("{{VIEW}}", view).replace(\'class="nav-link" href="\' + selected + \'"\', \'class="nav-link active" aria-current="page" href="\' + selected + \'"\');',
    '}',
    '',
  ].join('\n');
  await fs.mkdir(path.join(gate, 'src'), { recursive: true });
  await fs.writeFile(path.join(gate, 'src/new-a-member-frame.generated.ts'), generated);
}
