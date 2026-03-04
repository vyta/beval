/**
 * DSL implementation for the beval framework.
 *
 * Provides the defineCase function, CaseBuilder, and Given/When/Then
 * fluent interface. See SPEC.md §4 (The DSL).
 *
 * NOTE: `case` is a reserved word in JavaScript/TypeScript.
 * Use `defineCase` as the exported function name.
 */

/** Internal representation of a registered case. */
export interface CaseDefinition {
  id: string;
  name: string;
  category: string;
  tags: string[];
  func: (builder: CaseBuilder) => void;
  examples?: Record<string, unknown>[];
}

/** Global case registry. */
const caseRegistry: CaseDefinition[] = [];

/** Fluent builder for constructing case steps. See SPEC §4.1. */
export class CaseBuilder {
  readonly givens: Map<string, unknown> = new Map();
  readonly whens: string[] = [];
  readonly thens: Array<{ criterion: string; args: unknown[] }> = [];

  /** Set a precondition. See SPEC §4.1. */
  given(name: string, value?: unknown): this {
    this.givens.set(name, value ?? null);
    return this;
  }

  /** Declare the system action. See SPEC §4.1. */
  when(action: string): this {
    this.whens.push(action);
    return this;
  }

  /** Add a grading criterion. See SPEC §4.1. */
  then(criterion: string, ...args: unknown[]): this {
    this.thens.push({ criterion, args });
    return this;
  }
}

/**
 * Register an evaluation case. See SPEC §4.1.
 *
 * @example
 * ```ts
 * defineCase("AI legislation search", { category: "legislation" }, (s) => {
 *   s.given("a query", "What has Congress done on AI?")
 *    .when("the agent researches this query")
 *    .then("the answer should mention", "artificial intelligence");
 * });
 * ```
 */
export function defineCase(
  name: string,
  options: { id?: string; category?: string; tags?: string[] },
  func: (builder: CaseBuilder) => void,
): void {
  const definition: CaseDefinition = {
    id: options.id ?? (func.name || name),
    name,
    category: options.category ?? "",
    tags: options.tags ?? [],
    func,
  };
  caseRegistry.push(definition);
}

/**
 * Attach input parameterization examples to the last registered case.
 * See SPEC §4.3.
 */
export function examples(rows: Record<string, unknown>[]): void {
  const last = caseRegistry[caseRegistry.length - 1];
  if (last) {
    last.examples = rows;
  }
}

/** Return all registered case definitions. */
export function getRegisteredCases(): readonly CaseDefinition[] {
  return [...caseRegistry];
}
