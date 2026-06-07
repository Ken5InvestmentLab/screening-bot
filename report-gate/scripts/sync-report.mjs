import { copyFile, mkdir, stat } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const reportGateDir = path.resolve(scriptDir, "..");
const repoRoot = path.resolve(reportGateDir, "..");
const source = path.join(repoRoot, "reports", "mega_validation_report_latest.html");
const destinationDir = path.join(reportGateDir, "public");
const destination = path.join(destinationDir, "mega_validation_report_latest.html");

await stat(source);
await mkdir(destinationDir, { recursive: true });
await copyFile(source, destination);
console.log(`synced ${path.relative(repoRoot, source)} -> ${path.relative(repoRoot, destination)}`);
