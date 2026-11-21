import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';

const memberStyles = `
body[data-cloud-mode=member] [data-member-premium-nav][hidden]{display:none!important}
body[data-cloud-mode=member] .member-purchase{display:inline-flex;align-items:center;min-height:44px;padding:8px 14px;border:1px solid var(--blue);border-radius:9px;color:var(--blue);font-weight:700;text-decoration:none}
body[data-cloud-mode=member] .member-purchase:hover{background:color-mix(in srgb,var(--blue) 12%,var(--panel-solid))}
.member-locked-preview{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:12px;margin-bottom:20px}
.member-locked-preview .member-locked-card{margin:0;padding:16px;min-width:0}
.member-locked-card h2{font-size:1.1em;margin:0}
.member-locked-mask{display:flex;align-items:center;gap:10px;margin-top:12px}
.member-locked-mask span{display:block;height:18px;border-radius:4px;background:conic-gradient(var(--line) 25%,color-mix(in srgb,var(--muted) 46%,var(--panel-solid)) 0 50%,var(--line) 0 75%,color-mix(in srgb,var(--muted) 46%,var(--panel-solid)) 0) 0 0 / 12px 12px}
.member-locked-mask span:first-child{width:48px;flex:none}
.member-locked-mask span:last-child{width:min(11rem,60%)}
.member-locked-card details p{margin:0 0 8px}
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
    .replace('class="nav-link" href="./weak_early_beta_latest.html"', '$& id="member-home-nav"')
    .replace('href="./weak_early_beta_settings.html"', '$& data-member-premium-nav hidden')
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
    '  const homeTitle = tier === "free" ? "検出履歴" : "ダッシュボード";',
    '  const title = page === "analytics" ? "アナリティクス" : page === "settings" ? "設定" : homeTitle;',
    '  const content = \'<p id="member-state" role="status">読込中</p><button id="member-retry" hidden>再試行</button><div id="member-content"></div>\';',
    '  const view = page === "settings" && tier === "premium" ? \'<section class="panel cloud-settings" aria-labelledby="cloud-settings-title"><h1 id="cloud-settings-title">設定</h1>\' + content + \'</section>\' : content;',
    '  const pageScript = page === "settings" && tier === "premium" ? \'<script src="/new-a-assets/member-settings.js" defer></script>\' : page === "analytics" ? \'<script src="/new-a-assets/reference-analytics.js" defer></script>\' : "";',
    '  const selected = "./weak_early_beta_" + (page === "home" ? "latest" : page) + ".html";',
    '  return SHELL.replace(">ダッシュボード</a>", ">" + homeTitle + "</a>").replace(" ダッシュボードへ", " " + homeTitle + "へ").replaceAll("{{INITIAL_THEME}}", "dark").replace("{{INITIAL_THEME_SCRIPT}}", "").replaceAll("{{TITLE}}", title).replaceAll("{{PAGE}}", page).replace("{{MEMBER_PAGE_SCRIPTS}}", pageScript).replace("{{HELP_DIALOG}}", HELP_DIALOG).replace("{{SETTINGS_DIALOG}}", page !== "settings" && tier === "premium" ? SETTINGS_DIALOG : "").replace("{{SETTINGS_TRIGGER}}", page !== "settings" && tier === "premium" ? SETTINGS_TRIGGER : "").replace("{{VIEW}}", view).replace(\'class="nav-link" href="\' + selected + \'"\', \'class="nav-link active" aria-current="page" href="\' + selected + \'"\');',
    '}',
    '',
  ].join('\n');
  await fs.mkdir(path.join(gate, 'src'), { recursive: true });
  await fs.writeFile(path.join(gate, 'src/new-a-member-frame.generated.ts'), generated);
}
