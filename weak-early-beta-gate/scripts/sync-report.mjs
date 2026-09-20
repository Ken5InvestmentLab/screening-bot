import { copyFile, mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const gateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(gateDir, "..");
const reports = path.join(repoRoot, "reports");
const publicDir = path.join(gateDir, "public");

await mkdir(publicDir, { recursive: true });
const pageStems = [
  "weak_early_beta_latest",
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
