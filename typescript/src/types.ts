/**
 * Core type definitions for the beval framework.
 *
 * See SPEC.md §3 (Core Concepts), §6 (Scoring Model), §7.2 (Subject).
 */

/** Named quality dimension for score grouping. See SPEC §6.4. */
export type MetricCategory =
  | "latency"
  | "coverage"
  | "relevance"
  | "groundedness"
  | "correctness"
  | "quality"
  | "safety"
  | "cost";

/** Grader layer classification. See SPEC §5.1. */
export type GraderLayer = "deterministic" | "process" | "ai_judged";

/** Evaluation mode controlling which grader layers are active. See SPEC §8. */
export type EvaluationMode = "dev" | "dev+process" | "validation" | "monitoring";

/** Result of executing one grader against a case. See SPEC §6.2. */
export interface Grade {
  readonly criterion: string;
  readonly score: number;
  readonly metric: string;
  readonly passed: boolean;
  readonly detail: string | null;
  readonly layer: GraderLayer;
  readonly skipped?: boolean;
  readonly stage?: number;
  readonly stageName?: string;
}

/** Normalized system output exposed to graders. See SPEC §7.2. */
export interface Subject {
  readonly query: string;
  readonly answer: string;
  readonly completionTime: number;
  readonly documentsRetrieved?: number;
  readonly citationsCount?: number;
  readonly sourcesUsed?: readonly string[];
  readonly spans?: readonly unknown[];
  readonly metadata?: Readonly<Record<string, unknown>>;
  readonly stage?: number;
  readonly stageName?: string;
  readonly priorSubject?: Subject;
}

/** Per-stage summary for multi-stage cases. */
export interface StageResult {
  readonly stage: number;
  readonly name: string;
  readonly score: number;
  readonly passed: boolean;
  readonly gradeCount: number;
}

/** Result of a single trial execution. */
export interface TrialResult {
  readonly trial: number;
  readonly overallScore: number;
  readonly passed: boolean;
}

/** Aggregated evaluation result for a single case. See SPEC §12. */
export interface CaseResult {
  id: string;
  name: string;
  category: string;
  overallScore: number;
  passed: boolean;
  timeSeconds: number;
  metricScores: Record<string, number>;
  error: string | null;
  grades: Grade[];
  stages?: StageResult[];
  trials?: number;
  perTrial?: TrialResult[];
  scoreStddev?: number | null;
  scoreMin?: number | null;
  scoreMax?: number | null;
  passRate?: string | null;
}

/** Non-sensitive configuration snapshot for a run. */
export interface RunConfig {
  readonly gradePassThreshold?: number;
  readonly casePassThreshold?: number;
}

/** Aggregate summary across all cases in a run. */
export interface RunSummary {
  overallScore: number;
  passed: number;
  failed: number;
  errored: number;
  total: number;
  metrics: Record<string, number>;
}

/** Complete result of an evaluation run. See SPEC §12. */
export interface RunResult {
  label?: string;
  timestamp: string;
  mode: EvaluationMode;
  config: RunConfig;
  summary: RunSummary;
  cases: CaseResult[];
}
