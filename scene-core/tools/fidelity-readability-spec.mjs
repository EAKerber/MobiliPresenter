import { writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { currentProjectedReadabilityProbes } from "../dist/src/fidelity/readability.js";

const output = resolve(process.argv[2] ?? "/tmp/mobilipresenter-readability-spec.json");
const payload = {
  schemaVersion: "ReadabilityProbeSet 1.0",
  canonicalViewportPx: [1865, 967],
  supersampleFactor: 4,
  probes: currentProjectedReadabilityProbes()
};
writeFileSync(output, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
console.log(JSON.stringify({ output, probes: payload.probes.length }, null, 2));
