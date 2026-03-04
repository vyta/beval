/**
 * beval — Behavioral evaluation framework for AI agents and LLM-powered systems.
 *
 * See SPEC.md §3 for core concepts.
 *
 * @module beval
 */

// Core types
export type {
  CaseResult,
  EvaluationMode,
  Grade,
  GraderLayer,
  MetricCategory,
  RunConfig,
  RunResult,
  RunSummary,
  StageResult,
  Subject,
  TrialResult,
} from "./types.js";

// DSL
export {
  defineCase,
  examples,
  getRegisteredCases,
  CaseBuilder,
} from "./dsl.js";
export type { CaseDefinition } from "./dsl.js";

// Runner
export { Runner } from "./runner.js";
export type { RunnerOptions } from "./runner.js";

// Graders
export {
  registerGrader,
  matchGrader,
  resolveGrade,
  getRegisteredGraders,
} from "./graders/index.js";
export type { GraderHandler, GraderEntry } from "./graders/index.js";

// Judge
export { NullJudge } from "./judge.js";
export type { Judge } from "./judge.js";

// Subject
export { normalizeSubject } from "./subject.js";

// Loader
export { loadCaseFile, loadCaseDirectory } from "./loader.js";

// Schema
export { validate } from "./schema.js";

// Reporter
export { toJson, writeJson } from "./reporter.js";

// Tracing
export { setupTracing, getTracer } from "./tracing.js";
