import { copyFile, mkdir, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const reportGateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(reportGateDir, "..");
const sourceDir = path.join(repoRoot, "reports");
const destinationDir = path.join(reportGateDir, "public");
const reportFilePattern = /^mega_validation_report(?:_[a-z0-9_]+)?\.html$/;

await mkdir(destinationDir, { recursive: true });

const files = (await readdir(sourceDir)).filter((name) => reportFilePattern.test(name)).sort();
if (files.length === 0) {
  throw new Error(`No mega report HTML files found in ${path.relative(repoRoot, sourceDir)}`);
}

for (const file of files) {
  const source = path.join(sourceDir, file);
  const destination = path.join(destinationDir, file);
  await stat(source);
  await copyFile(source, destination);
  console.log(`synced ${path.relative(repoRoot, source)} -> ${path.relative(repoRoot, destination)}`);
}
