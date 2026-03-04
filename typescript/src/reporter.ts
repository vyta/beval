/**
 * Result reporting for the beval framework.
 *
 * Formats and outputs evaluation results to console or JSON.
 * See SPEC.md §12 (Results Schema).
 */

import type { RunResult } from "./types.js";

/** Serialize a RunResult to a JSON string. */
export function toJson(result: RunResult, indent = 2): string {
  return JSON.stringify(result, null, indent);
}

/** Write a RunResult to a JSON file. */
export async function writeJson(result: RunResult, path: string): Promise<void> {
  const { writeFile } = await import("node:fs/promises");
  await writeFile(path, toJson(result), "utf-8");
}
