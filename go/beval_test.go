package beval

import "testing"

func TestGradeZeroValue(t *testing.T) {
	var g Grade
	if g.Score != 0 {
		t.Errorf("expected zero score, got %f", g.Score)
	}
	if g.Passed {
		t.Error("expected passed to be false")
	}
	if g.Skipped {
		t.Error("expected skipped to be false")
	}
}

func TestDefaultRunConfig(t *testing.T) {
	cfg := DefaultRunConfig()
	if cfg.GradePassThreshold != 0.5 {
		t.Errorf("expected grade threshold 0.5, got %f", cfg.GradePassThreshold)
	}
	if cfg.CasePassThreshold != 0.7 {
		t.Errorf("expected case threshold 0.7, got %f", cfg.CasePassThreshold)
	}
}

func TestMetricCategoryValues(t *testing.T) {
	cats := []MetricCategory{
		MetricLatency, MetricCoverage, MetricRelevance,
		MetricGroundedness, MetricCorrectness, MetricQuality,
		MetricSafety, MetricCost,
	}
	if len(cats) != 8 {
		t.Errorf("expected 8 metric categories, got %d", len(cats))
	}
}

func TestCaseDSL(t *testing.T) {
	s := Case("test case", Category("testing"), Tags("unit"))
	if s.def.Name != "test case" {
		t.Errorf("expected name 'test case', got %q", s.def.Name)
	}
	if s.def.Category != "testing" {
		t.Errorf("expected category 'testing', got %q", s.def.Category)
	}
	if len(s.def.Tags) != 1 || s.def.Tags[0] != "unit" {
		t.Errorf("expected tags [unit], got %v", s.def.Tags)
	}

	s.Given("a query", "test query")
	s.When("the agent processes")
	s.Then("the answer should contain", "result")

	if len(s.steps) != 3 {
		t.Errorf("expected 3 steps, got %d", len(s.steps))
	}
}

func TestNullJudge(t *testing.T) {
	j := NullJudge{}
	g := j.Evaluate("test criterion", "some answer", nil)
	if !g.Skipped {
		t.Error("expected NullJudge to return skipped grade")
	}
	if g.Score != 0.0 {
		t.Errorf("expected score 0.0, got %f", g.Score)
	}
}

func TestNormalizeSubject(t *testing.T) {
	s := NormalizeSubject("query", "answer", 1.5,
		WithDocumentsRetrieved(3),
		WithCitationsCount(2),
	)
	if s.Query != "query" {
		t.Errorf("expected query 'query', got %q", s.Query)
	}
	if s.CompletionTime != 1.5 {
		t.Errorf("expected completion time 1.5, got %f", s.CompletionTime)
	}
	if s.DocumentsRetrieved != 3 {
		t.Errorf("expected 3 documents retrieved, got %d", s.DocumentsRetrieved)
	}
}
