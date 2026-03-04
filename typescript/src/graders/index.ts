/**
 * Grader registry and base grader interface.
 *
 * See SPEC.md §7 (Graders) for registration model and pattern matching.
 */

import type { EvaluationMode, Grade, GraderLayer, Subject } from "../types.js";

/** Handler function signature for grader implementations. */
export type GraderHandler = (
  criterion: string,
  args: unknown[],
  subject: Subject,
  context: unknown,
) => Grade;

/** A registered grader with its pattern, handler, and options. */
export interface GraderEntry {
  readonly pattern: string;
  readonly handler: GraderHandler;
  readonly layer: GraderLayer;
  readonly metric: string;
}

/** Global grader registry. */
const graderRegistry: GraderEntry[] = [];

/** Register a grader against a pattern. See SPEC §7.1. */
export function registerGrader(
  pattern: string,
  handler: GraderHandler,
  options?: { layer?: GraderLayer; metric?: string },
): void {
  graderRegistry.push({
    pattern: pattern.toLowerCase(),
    handler,
    layer: options?.layer ?? "deterministic",
    metric: options?.metric ?? "quality",
  });
}

/** Find the first grader matching a criterion via prefix match. See SPEC §7.1. */
export function matchGrader(criterion: string): GraderEntry | undefined {
  const lower = criterion.toLowerCase();
  return graderRegistry.find(
    (entry) => lower === entry.pattern || lower.startsWith(entry.pattern),
  );
}

/** Resolve a then-clause to a Grade by matching and invoking a grader. */
export function resolveGrade(
  criterion: string,
  args: unknown[],
  subject: Subject,
  context: unknown,
  mode: EvaluationMode,
): Grade {
  const entry = matchGrader(criterion);

  if (!entry) {
    return {
      criterion,
      score: 0,
      metric: "quality",
      passed: false,
      detail: "No grader found for this criterion.",
      layer: "deterministic",
    };
  }

  // Skip AI-judged graders in dev modes
  if (
    entry.layer === "ai_judged" &&
    (mode === "dev" || mode === "dev+process")
  ) {
    return {
      criterion,
      score: 0,
      metric: entry.metric,
      passed: false,
      detail: "Skipped: AI-judged grader not active in this mode.",
      layer: entry.layer,
      skipped: true,
    };
  }

  // Skip process graders in dev-only mode
  if (entry.layer === "process" && mode === "dev") {
    return {
      criterion,
      score: 0,
      metric: entry.metric,
      passed: false,
      detail: "Skipped: process grader not active in dev mode.",
      layer: entry.layer,
      skipped: true,
    };
  }

  return entry.handler(criterion, args, subject, context);
}

/** Return all registered graders. */
export function getRegisteredGraders(): readonly GraderEntry[] {
  return [...graderRegistry];
}
