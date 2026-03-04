/**
 * YAML case file loading with safe parsing.
 *
 * Loads evaluation case definitions from YAML files.
 * See SPEC.md §4 (The DSL) for YAML case format.
 *
 * The yaml npm package (v2+) uses safe parsing by default — no
 * custom tags or code execution unless explicitly opted in.
 */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, extname } from "node:path";
import { parse } from "yaml";

/**
 * Load a single YAML case file.
 *
 * Uses `yaml.parse` which is safe by default in yaml v2+.
 */
export function loadCaseFile(path: string): Record<string, unknown> {
  const content = readFileSync(path, "utf-8");
  const data: unknown = parse(content);

  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    throw new Error(
      `Expected a mapping at top level of ${path}, got ${typeof data}`,
    );
  }

  return data as Record<string, unknown>;
}

/**
 * Load all YAML case files from a directory.
 *
 * Searches for `.yaml` and `.yml` files recursively.
 */
export function loadCaseDirectory(directory: string): Record<string, unknown>[] {
  const results: Record<string, unknown>[] = [];
  collectYamlFiles(directory, results);
  return results;
}

function collectYamlFiles(
  dir: string,
  results: Record<string, unknown>[],
): void {
  const entries = readdirSync(dir).sort();
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      collectYamlFiles(fullPath, results);
    } else {
      const ext = extname(entry).toLowerCase();
      if (ext === ".yaml" || ext === ".yml") {
        results.push(loadCaseFile(fullPath));
      }
    }
  }
}
