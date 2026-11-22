import test from "node:test";
import assert from "node:assert/strict";
import { parsePairingQr } from "../src/qr.ts";
import { fuzzyFilter } from "../src/fuzzy.ts";
import { diffLines } from "../src/diff.ts";
import { basename, dirname, join, projectOf, withinProject } from "../src/paths.ts";

test("parsePairingQr parses valid VibeBuilder QR JSON", () => {
  const got = parsePairingQr('{"vb":1,"u":"https://ide.example.com","c":"ab12cd"}');
  assert.deepEqual(got, { server: "https://ide.example.com", code: "AB1-2CD" });
});

test("parsePairingQr rejects invalid payloads", () => {
  assert.equal(parsePairingQr("not json"), null);
  assert.equal(parsePairingQr('{"vb":2,"u":"https://x","c":"123456"}'), null);
  assert.equal(parsePairingQr('{"vb":1,"u":"","c":"123456"}'), null);
  assert.equal(parsePairingQr('{"vb":1,"u":"https://x","c":"123"}'), null);
});

test("fuzzyFilter ranks exact filename hits ahead of scattered matches", () => {
  const hits = fuzzyFilter("ed", ["src/nested/deep_thing.ts", "src/Editor.svelte"]);
  assert.equal(hits[0]?.item, "src/Editor.svelte");
});

test("diffLines computes added/removed counts and hunks", () => {
  const d = diffLines("a\nb\nc", "a\nx\nc\nd");
  assert.equal(d.added, 2);
  assert.equal(d.removed, 1);
  assert.equal(d.hunks.length, 1);
});

test("path helpers normalize workspace paths", () => {
  assert.equal(join("proj", "src/", "/app.ts"), "proj/src/app.ts");
  assert.equal(dirname("proj/src/app.ts"), "proj/src");
  assert.equal(basename("proj/src/app.ts"), "app.ts");
  assert.equal(projectOf("proj/src/app.ts"), "proj");
  assert.equal(projectOf("GitHub/my-repo/src/app.ts"), "GitHub/my-repo");
  assert.equal(withinProject("proj/src/app.ts"), "src/app.ts");
  assert.equal(withinProject("GitHub/my-repo/src/app.ts"), "src/app.ts");
});
