/**
 * Subject normalization for the beval framework.
 *
 * Wraps system output into the normalized Subject interface.
 * See SPEC.md §7.2 (The Subject).
 */

import type { Subject } from "./types.js";

/** Options for creating a normalized Subject. */
export interface NormalizeSubjectOptions {
  query: string;
  answer: string;
  completionTime: number;
  documentsRetrieved?: number;
  citationsCount?: number;
  sourcesUsed?: string[];
  spans?: unknown[];
  metadata?: Record<string, unknown>;
}

/**
 * Create a normalized Subject from system output. See SPEC §7.2.
 *
 * The returned Subject is a frozen object to prevent graders from
 * modifying shared state.
 */
export function normalizeSubject(options: NormalizeSubjectOptions): Readonly<Subject> {
  return Object.freeze({
    query: options.query,
    answer: options.answer,
    completionTime: options.completionTime,
    documentsRetrieved: options.documentsRetrieved ?? 0,
    citationsCount: options.citationsCount ?? 0,
    sourcesUsed: Object.freeze([...(options.sourcesUsed ?? [])]),
    spans: Object.freeze([...(options.spans ?? [])]),
    metadata: Object.freeze({ ...(options.metadata ?? {}) }),
  });
}
