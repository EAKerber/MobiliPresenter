import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { buildCurrentFidelityReport } from "../dist/src/fidelity/report.js";

const output = resolve(process.argv[2] ?? "artifacts/fidelity-report.json");
const report = buildCurrentFidelityReport();
mkdirSync(dirname(output), { recursive: true });
writeFileSync(output, `${JSON.stringify(report, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ output, hardGatesPass: report.hardGatesPass, checks: report.checks.length }, null, 2));
