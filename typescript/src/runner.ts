/**
 * Runner orchestration for the beval framework.
 *
 * Executes cases against a system, dispatches to graders, and collects results.
 * See SPEC.md §11 (Runner).
 */

import { getRegisteredCases, CaseBuilder } from "./dsl.js";
import type { CaseDefinition } from "./dsl.js";
import { resolveGrade } from "./graders/index.js";
import type {
  CaseResult,
  EvaluationMode,
  RunConfig,
  RunResult,
  RunSummary,
  Subject,
} from "./types.js";

/** Options for creating a Runner instance. */
export interface RunnerOptions {
  mode?: EvaluationMode;
  config?: RunConfig;
  handler?: (builder: CaseBuilder) => Subject | Promise<Subject>;
}

/** Orchestrates case execution. See SPEC §11. */
export class Runner {
  readonly mode: EvaluationMode;
  readonly config: RunConfig;
  private readonly handler:
    | ((builder: CaseBuilder) => Subject | Promise<Subject>)
    | undefined;

  constructor(options?: RunnerOptions) {
    this.mode = options?.mode ?? "dev";
    this.config = options?.config ?? {};
    this.handler = options?.handler;
  }

  /** Execute evaluation cases and return aggregated results. */
  async run(
    cases?: CaseDefinition[],
    options?: { label?: string },
  ): Promise<RunResult> {
    const caseDefs = cases ?? getRegisteredCases();
    const caseResults: CaseResult[] = [];

    for (const caseDef of caseDefs) {
      const result = await this.runCase(caseDef);
      caseResults.push(result);
    }

    const summary = this.buildSummary(caseResults);

    return {
      label: options?.label,
      timestamp: new Date().toISOString(),
      mode: this.mode,
      config: this.config,
      summary,
      cases: caseResults,
    };
  }

  private async runCase(caseDef: CaseDefinition): Promise<CaseResult> {
    const start = Date.now();
    const builder = new CaseBuilder();

    try {
      caseDef.func(builder);
    } catch (err) {
      const elapsed = (Date.now() - start) / 1000;
      return {
        id: caseDef.id,
        name: caseDef.name,
        category: caseDef.category,
        overallScore: 0,
        passed: false,
        timeSeconds: elapsed,
        metricScores: {},
        error: err instanceof Error ? err.message : String(err),
        grades: [],
      };
    }

    // Stub: in a full implementation, invoke the handler and grade
    const elapsed = (Date.now() - start) / 1000;

    return {
      id: caseDef.id,
      name: caseDef.name,
      category: caseDef.category,
      overallScore: 0,
      passed: false,
      timeSeconds: elapsed,
      metricScores: {},
      error: null,
      grades: [],
    };
  }

  private buildSummary(cases: CaseResult[]): RunSummary {
    const total = cases.length;
    const passed = cases.filter((c) => c.passed).length;
    const errored = cases.filter((c) => c.error !== null).length;
    const failed = total - passed - errored;
    const overallScore =
      total > 0
        ? cases.reduce((sum, c) => sum + c.overallScore, 0) / total
        : 0;

    return { overallScore, passed, failed, errored, total, metrics: {} };
  }
}
