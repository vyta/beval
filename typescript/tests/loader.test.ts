/**
 * Tests for beval YAML case loading.
 */

import { describe, it, expect } from "vitest";
import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { loadCaseFile, loadCaseDirectory } from "../src/loader.js";

function createTempDir(): string {
  return mkdtempSync(join(tmpdir(), "beval-test-"));
}

describe("loadCaseFile", () => {
  it("loads valid YAML", () => {
    const dir = createTempDir();
    const path = join(dir, "test.yaml");
    writeFileSync(
      path,
      'cases:\n  - name: "test case"\n    when: action\n    then:\n      - check: 1\n',
      "utf-8",
    );

    const result = loadCaseFile(path);
    const cases = result["cases"] as Array<Record<string, unknown>>;
    expect(cases[0]["name"]).toBe("test case");
  });

  it("rejects non-mapping top level", () => {
    const dir = createTempDir();
    const path = join(dir, "bad.yaml");
    writeFileSync(path, "- item1\n- item2\n", "utf-8");

    expect(() => loadCaseFile(path)).toThrow("Expected a mapping");
  });
});

describe("loadCaseDirectory", () => {
  it("loads multiple files", () => {
    const dir = createTempDir();
    writeFileSync(join(dir, "a.yaml"), "cases: []\n", "utf-8");
    writeFileSync(join(dir, "b.yml"), "cases: []\n", "utf-8");

    const results = loadCaseDirectory(dir);
    expect(results).toHaveLength(2);
  });

  it("returns empty for empty directory", () => {
    const dir = createTempDir();
    const results = loadCaseDirectory(dir);
    expect(results).toEqual([]);
  });
});
