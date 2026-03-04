// Package graders provides the grader registry and interface for beval.
//
// See SPEC.md §7 (Graders) for the registration model and pattern matching.
package graders

// GraderFunc is the function signature for grader handlers.
// Parameters: criterion, args, subjectAnswer, context.
// Returns: score (0.0–1.0), passed, detail.
type GraderFunc func(criterion string, args []interface{}, subjectAnswer string, context interface{}) (float64, bool, string)

// Entry is a registered grader with its pattern, handler, and metadata.
type Entry struct {
	Pattern string
	Handler GraderFunc
	Layer   string
	Metric  string
}

// registry holds all registered graders.
var registry []Entry

// Register adds a grader to the global registry. See SPEC §7.1.
func Register(pattern string, handler GraderFunc, layer string, metric string) {
	registry = append(registry, Entry{
		Pattern: pattern,
		Handler: handler,
		Layer:   layer,
		Metric:  metric,
	})
}

// Match finds the first grader matching a criterion via prefix match.
// See SPEC §7.1. Returns nil if no grader matches.
func Match(criterion string) *Entry {
	for i := range registry {
		if len(criterion) >= len(registry[i].Pattern) &&
			criterion[:len(registry[i].Pattern)] == registry[i].Pattern {
			return &registry[i]
		}
	}
	return nil
}

// All returns all registered grader entries.
func All() []Entry {
	return registry
}
