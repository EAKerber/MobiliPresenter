import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const indexHtml = await readFile(new URL("../index.html", import.meta.url), "utf8");
const enhancements = await readFile(new URL("../src/ui/editorial-enhancements.ts", import.meta.url), "utf8");
const overrides = await readFile(new URL("../src/ui/editorial-overrides.css", import.meta.url), "utf8");

test("product-facing title does not expose the internal codename", () => {
  assert.match(indexHtml, /<title>Apresentação de Ambiente — Vista Fixa<\/title>/);
  assert.doesNotMatch(indexHtml, /MobiliPresenter|>MP</i);
  assert.match(enhancements, /viewer-shell__mark/);
  assert.match(enhancements, /\.remove\(\)/);
});

test("editorial layer marks current technical art as schematic", () => {
  assert.match(enhancements, /ESQUEMA DIMENSIONAL/);
  assert.match(enhancements, /Representação dimensional esquemática\./);
  assert.match(enhancements, /technicalFidelity = "schematic"/);
});

test("semantic iconography includes the authored electrical outlet", () => {
  assert.match(enhancements, /module02\/component\/outlet-20a/);
  assert.match(enhancements, /case "module02\/component\/outlet-20a": return "outlet"/);
  assert.match(enhancements, /outlet: svg/);
});

test("interactive controls are flattened instead of visually raised", () => {
  assert.match(overrides, /box-shadow:\s*none\s*!important/);
  assert.match(overrides, /viewer-finish-option\[aria-pressed="true"\]/);
  assert.match(overrides, /viewer-technical-gallery__option\[aria-pressed="true"\]/);
  assert.doesNotMatch(overrides, /linear-gradient\(/);
});
