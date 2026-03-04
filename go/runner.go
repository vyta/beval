package beval

import "time"

// Runner orchestrates case execution. See SPEC §11.
type Runner struct {
	Mode       EvaluationMode
	Config     RunConfig
	Handler interface{}
}

// NewRunner creates a Runner with the given options.
func NewRunner(opts ...RunnerOption) *Runner {
	r := &Runner{
		Mode:   ModeDev,
		Config: DefaultRunConfig(),
	}
	for _, opt := range opts {
		opt(r)
	}
	return r
}

// RunnerOption configures a Runner.
type RunnerOption func(*Runner)

// WithMode sets the evaluation mode.
func WithMode(mode EvaluationMode) RunnerOption {
	return func(r *Runner) {
		r.Mode = mode
	}
}

// WithConfig sets the run configuration.
func WithConfig(cfg RunConfig) RunnerOption {
	return func(r *Runner) {
		r.Config = cfg
	}
}

// Run executes evaluation cases and returns aggregated results.
func (r *Runner) Run(cases []*CaseBuilder, label string) RunResult {
	// Stub: returns an empty result.
	return RunResult{
		Label:     label,
		Timestamp: time.Now().UTC().Format(time.RFC3339),
		Mode:      r.Mode,
		Config:    r.Config,
		Summary:   RunSummary{},
		Cases:     nil,
	}
}
