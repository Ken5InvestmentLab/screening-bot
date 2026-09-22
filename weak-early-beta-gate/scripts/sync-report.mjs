import { copyFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const gateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(gateDir, "..");
const reports = path.join(repoRoot, "reports");
const publicDir = path.join(gateDir, "public");
const publicAssetsDir = path.join(publicDir, "report-assets");

await mkdir(publicDir, { recursive: true });
await mkdir(publicAssetsDir, { recursive: true });
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
for (const name of pageStems.flatMap((stem) => [`${stem}.html`, `${stem}_free.html`])) {
  await copyFile(path.join(reports, name), path.join(publicDir, name));
  console.log(`synced reports/${name}`);
}
for (const scriptName of [
  "weak-early-beta-interactions.js",
  "weak-early-beta-theme-init.js",
]) {
  await copyFile(path.join(reports, scriptName), path.join(publicDir, scriptName));
  console.log(`synced reports/${scriptName}`);
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
