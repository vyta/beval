/**
 * LLM judge interface for AI-judged graders.
 *
 * Provides a pluggable judge abstraction for subjective quality assessment.
 * See SPEC.md §10 (Pluggable Judges).
 */

import type { Grade } from "./types.js";

/** Base interface for LLM-based judges. See SPEC §10. */
export interface Judge {
  /** Evaluate a subject answer against a criterion. */
  evaluate(
    criterion: string,
    subjectAnswer: string,
    context?: Record<string, unknown>,
  ): Grade | Promise<Grade>;
}

/** A no-op judge that returns a skipped grade. Used when no judge is configured. */
export class NullJudge implements Judge {
  evaluate(
    criterion: string,
    _subjectAnswer: string,
    _context?: Record<string, unknown>,
  ): Grade {
    return {
      criterion,
      score: 0,
      metric: "quality",
      passed: false,
      detail: "No judge configured.",
      layer: "ai_judged",
      skipped: true,
    };
  }
}
