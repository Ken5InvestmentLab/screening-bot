import { copyFile, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import crypto from "node:crypto";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const gateDir = path.resolve(scriptDir, "..");
const source = path.resolve(gateDir, "..", "report-gate", "src", "index.ts");
const destination = path.join(gateDir, "src", "shared-report-gate.ts");

await copyFile(source, destination);
const bytes = await readFile(destination);
const sha256 = crypto.createHash("sha256").update(bytes).digest("hex");
await writeFile(
  path.join(gateDir, "src", "shared-report-gate.sha256"),
  `${sha256}  report-gate/src/index.ts\n`,
  "utf8",
);
console.log(`synced report-gate/src/index.ts (${sha256})`);
