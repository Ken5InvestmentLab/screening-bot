import { copyFile, mkdir, readFile, readdir, unlink } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const gateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(gateDir, "..");
const reports = path.join(repoRoot, "reports");
const publicDir = path.join(gateDir, "public");
const publicAssetsDir = path.join(publicDir, "report-assets");

const pageStems = [
  "weak_early_beta_latest",
  "weak_early_beta_analytics",
  "weak_early_beta_silence",
  "weak_early_beta_dive",
  "weak_early_beta_shadow",
  "weak_early_beta_fusion",
  "weak_early_beta_balance",
  "weak_early_beta_guide",
];
// Validate every referenced bundle before changing public assets. Only the
// generated filename grammar can enter the bundle; private receipts stay out.
const bundleNames = new Set();
const checkedBundles = new Map();
const bundlePattern = /^weak_early_beta_data_(full|free)_(latest|analytics|silence|dive|shadow|fusion|balance|guide)_([a-f0-9]{16})_(\d{4})\.json$/;
for (const stem of pageStems) for (const suffix of ["", "_free"]) {
  const html = await readFile(path.join(reports, `${stem}${suffix}.html`), "utf8");
  const match = /<script id="cloud-analytics-data" type="application\/json">([\s\S]*?)<\/script>/.exec(html);
  if (!match) continue; // guide has no variant payload
  const payload = JSON.parse(match[1]);
  const expectedAudience = suffix ? "free" : "full";
  const expectedPage = stem.replace("weak_early_beta_", "");
  for (const [key, value] of Object.entries(payload.variants)) {
    if (!value.bundle) continue;
    const name = value.bundle.replace(/^\.\//, "");
    const parts = bundlePattern.exec(name);
    const context = payload.bundleContext;
    if (!parts || value.bundle !== `./${name}` || !context || parts[1] !== expectedAudience || parts[2] !== expectedPage || context.audience !== parts[1] || context.page !== parts[2] || context.snapshot !== parts[3]) throw new Error("invalid Cloud bundle reference");
    let bundle = checkedBundles.get(name);
    if (!bundle) {
      const bytes = await readFile(path.join(reports, name));
      if (bytes.length > 1024 * 1024) throw new Error("oversized Cloud bundle");
      bundle = JSON.parse(bytes.toString("utf8"));
      checkedBundles.set(name, bundle);
    }
    if (bundle.version !== 1 || bundle.encoding !== "gzip-base64-json" || bundle.audience !== parts[1] || bundle.page !== parts[2] || bundle.snapshot !== parts[3] || bundle.chunk !== Number(parts[4]) || !bundle.variants || Object.keys(bundle.variants).length > 32 || typeof bundle.variants[key]?.gzip !== "string") throw new Error("invalid Cloud bundle metadata");
    bundleNames.add(name);
  }
}
await mkdir(publicDir, { recursive: true });
await mkdir(publicAssetsDir, { recursive: true });
for (const name of pageStems.flatMap((stem) => [`${stem}.html`, `${stem}_free.html`])) {
  await copyFile(path.join(reports, name), path.join(publicDir, name));
  console.log(`synced reports/${name}`);
}
for (const scriptName of [
  "weak-early-beta-interactions.js",
  "weak-early-beta-scenarios.js",
  "weak-early-beta-theme-init.js",
  "weak-early-beta-push.js",
  "weak-early-beta-service-worker.js",
]) {
  await copyFile(path.join(reports, scriptName), path.join(publicDir, scriptName));
  console.log(`synced reports/${scriptName}`);
}
for (const name of bundleNames) await copyFile(path.join(reports, name), path.join(publicDir, name));
// Stale snapshots are removed only inside this known public directory, after
// the complete source set has passed validation and all current bundles copied.
for (const name of await readdir(publicDir)) {
  if (bundlePattern.test(name) && !bundleNames.has(name)) await unlink(path.join(publicDir, name));
}
for (const assetName of [
  "discord-light.png",
  "discord-dark.png",
  "coconala-light.png",
  "coconala-dark.png",
  "x-light.png",
  "x-dark.png",
  "cloud-logo-light.png",
  "cloud-logo-dark.png",
]) {
  await copyFile(
    path.join(reports, "report-assets", assetName),
    path.join(publicAssetsDir, assetName),
  );
  console.log(`synced reports/report-assets/${assetName}`);
}
