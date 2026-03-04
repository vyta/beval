/**
 * Tests for beval core types.
 */

import { describe, it, expect } from "vitest";
import type {
  CaseResult,
  EvaluationMode,
  Grade,
  GraderLayer,
  MetricCategory,
  RunConfig,
  RunSummary,
  Subject,
} from "../src/types.js";

describe("Grade", () => {
  it("creates a grade with required fields", () => {
    const grade: Grade = {
      criterion: "test criterion",
      score: 0.8,
      metric: "relevance",
      passed: true,
      detail: "Test detail",
      layer: "deterministic",
    };
    expect(grade.score).toBe(0.8);
    expect(grade.passed).toBe(true);
    expect(grade.layer).toBe("deterministic");
  });

  it("supports optional fields", () => {
    const grade: Grade = {
      criterion: "test",
      score: 1.0,
      metric: "quality",
      passed: true,
      detail: null,
      layer: "deterministic",
      skipped: false,
      stage: 1,
      stageName: "research",
    };
    expect(grade.skipped).toBe(false);
    expect(grade.stage).toBe(1);
    expect(grade.stageName).toBe("research");
  });
});

describe("Subject", () => {
  it("creates a subject with required fields", () => {
    const subject: Subject = {
      query: "q",
      answer: "a",
      completionTime: 1.0,
    };
    expect(subject.query).toBe("q");
    expect(subject.answer).toBe("a");
    expect(subject.completionTime).toBe(1.0);
  });

  it("supports optional fields with defaults", () => {
    const subject: Subject = {
      query: "q",
      answer: "a",
      completionTime: 1.0,
      documentsRetrieved: 0,
      sourcesUsed: [],
      metadata: {},
    };
    expect(subject.documentsRetrieved).toBe(0);
    expect(subject.sourcesUsed).toEqual([]);
    expect(subject.metadata).toEqual({});
  });
});

describe("MetricCategory", () => {
  it("includes all expected categories", () => {
    const expected: MetricCategory[] = [
      "latency",
      "coverage",
      "relevance",
      "groundedness",
      "correctness",
      "quality",
      "safety",
      "cost",
    ];
    // MetricCategory is a type alias — verify the values compile
    for (const category of expected) {
      const value: MetricCategory = category;
      expect(value).toBe(category);
    }
  });
});

describe("GraderLayer", () => {
  it("includes all expected layers", () => {
    const layers: GraderLayer[] = ["deterministic", "process", "ai_judged"];
    expect(layers).toHaveLength(3);
  });
});

describe("EvaluationMode", () => {
  it("includes all expected modes", () => {
    const modes: EvaluationMode[] = [
      "dev",
      "dev+process",
      "validation",
      "monitoring",
    ];
    expect(modes).toHaveLength(4);
  });
});

describe("CaseResult", () => {
  it("creates a case result", () => {
    const result: CaseResult = {
      id: "test-1",
      name: "Test case",
      category: "test",
      overallScore: 0.85,
      passed: true,
      timeSeconds: 1.2,
      metricScores: { relevance: 0.9 },
      error: null,
      grades: [],
    };
    expect(result.overallScore).toBe(0.85);
    expect(result.passed).toBe(true);
  });
});

describe("RunConfig", () => {
  it("supports optional threshold fields", () => {
    const config: RunConfig = {
      gradePassThreshold: 0.5,
      casePassThreshold: 0.7,
    };
    expect(config.gradePassThreshold).toBe(0.5);
  });

  it("allows empty config", () => {
    const config: RunConfig = {};
    expect(config.gradePassThreshold).toBeUndefined();
  });
});
