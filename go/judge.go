package beval

// Judge is the interface for LLM-based judges. See SPEC §10.
type Judge interface {
	// Evaluate assesses a subject answer against a criterion.
	// Returns a Grade with score, metric, and reasoning detail.
	Evaluate(criterion string, subjectAnswer string, context map[string]interface{}) Grade
}

// NullJudge is a no-op judge that returns a skipped grade.
// Used when no judge is configured.
type NullJudge struct{}

// Evaluate returns a skipped grade indicating no judge is configured.
func (n NullJudge) Evaluate(criterion string, subjectAnswer string, context map[string]interface{}) Grade {
	return Grade{
		Criterion: criterion,
		Score:     0.0,
		Metric:    "quality",
		Passed:    false,
		Detail:    "No judge configured.",
		Layer:     LayerAIJudged,
		Skipped:   true,
	}
}
