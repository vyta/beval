/**
 * JSON Schema validation using shared schemas from spec/.
 *
 * Validates case files, results, and configuration against the canonical
 * JSON Schema definitions. See SPEC.md §12, §13.
 */

import { readFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import Ajv from "ajv";

const __dirname = dirname(fileURLToPath(import.meta.url));

/** Resolve schema directory relative to this package (monorepo layout). */
const SCHEMA_DIR = resolve(__dirname, "..", "..", "spec", "schemas");

const ajv = new Ajv({ allErrors: true });

/**
 * Validate a data structure against a named schema.
 *
 * @param instance - The data to validate.
 * @param schemaName - Schema filename without path (e.g., "case.schema.json").
 * @returns List of validation error messages. Empty array means valid.
 */
export function validate(
  instance: unknown,
  schemaName: string,
): string[] {
  const schemaPath = resolve(SCHEMA_DIR, schemaName);

  let schema: unknown;
  try {
    schema = JSON.parse(readFileSync(schemaPath, "utf-8"));
  } catch {
    return [`Schema file not found: ${schemaName}`];
  }

  const valid = ajv.validate(schema as object, instance);
  if (valid) {
    return [];
  }

  return (ajv.errors ?? []).map((err: { instancePath?: string; message?: string }) => {
    const path = err.instancePath || "/";
    return `${path}: ${err.message ?? "unknown error"}`;
  });
}
