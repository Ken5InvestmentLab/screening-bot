import { copyFile, mkdir, readdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const reportGateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(reportGateDir, "..");
const sourceDir = path.join(repoRoot, "reports");
const destinationDir = path.join(reportGateDir, "public");
const reportAssetDirName = "report-assets";
const reportHtmlFilePattern = /^mega_validation_report(?:_[a-z0-9_]+)?\.html$/;
const reportFilePattern = /^(?:mega_validation_report(?:_[a-z0-9_]+)?\.html|report-interactions\.js)$/;
const reportAssetFilePattern = /^[a-z0-9-]+\.png$/;

await mkdir(destinationDir, { recursive: true });

const files = (await readdir(sourceDir)).filter((name) => reportFilePattern.test(name)).sort();
if (!files.some((name) => reportHtmlFilePattern.test(name))) {
  throw new Error(`No mega report HTML files found in ${path.relative(repoRoot, sourceDir)}`);
}

for (const file of files) {
  const source = path.join(sourceDir, file);
  const destination = path.join(destinationDir, file);
  await stat(source);
  await copyFile(source, destination);
  console.log(`synced ${path.relative(repoRoot, source)} -> ${path.relative(repoRoot, destination)}`);
}

const sourceAssetDir = path.join(sourceDir, reportAssetDirName);
const destinationAssetDir = path.join(destinationDir, reportAssetDirName);
const assetFiles = (await readdir(sourceAssetDir)).filter((name) => reportAssetFilePattern.test(name)).sort();
if (assetFiles.length === 0) {
  throw new Error(`No report logo assets found in ${path.relative(repoRoot, sourceAssetDir)}`);
}

await mkdir(destinationAssetDir, { recursive: true });
for (const file of assetFiles) {
  const source = path.join(sourceAssetDir, file);
  const destination = path.join(destinationAssetDir, file);
  await stat(source);
  await copyFile(source, destination);
  console.log(`synced ${path.relative(repoRoot, source)} -> ${path.relative(repoRoot, destination)}`);
}
