import { copyFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const gateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(gateDir, "..");
const reports = path.join(repoRoot, "reports");
const publicDir = path.join(gateDir, "public");

await mkdir(publicDir, { recursive: true });
for (const name of ["weak_early_beta_latest.html", "weak_early_beta_latest_free.html"]) {
  await copyFile(path.join(reports, name), path.join(publicDir, name));
  console.log(`synced reports/${name}`);
}
await copyFile(
  path.join(reports, "weak-early-beta-interactions.js"),
  path.join(publicDir, "report-interactions.js"),
);
// The shared gate exposes this stable path.  The beta report does not need an
// early inline theme script, so a no-op asset keeps the route deterministic.
await writeFile(path.join(publicDir, "report-theme-init.js"), "// beta no-op\n", "utf8");
