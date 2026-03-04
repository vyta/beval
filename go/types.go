package beval

// MetricCategory is a named quality dimension for score grouping.
// See SPEC §6.4.
type MetricCategory string

const (
	MetricLatency      MetricCategory = "latency"
	MetricCoverage     MetricCategory = "coverage"
	MetricRelevance    MetricCategory = "relevance"
	MetricGroundedness MetricCategory = "groundedness"
	MetricCorrectness  MetricCategory = "correctness"
	MetricQuality      MetricCategory = "quality"
	MetricSafety       MetricCategory = "safety"
	MetricCost         MetricCategory = "cost"
)

// GraderLayer classifies the grader type. See SPEC §5.1.
type GraderLayer string

const (
	LayerDeterministic GraderLayer = "deterministic"
	LayerProcess       GraderLayer = "process"
	LayerAIJudged      GraderLayer = "ai_judged"
)

// EvaluationMode controls which grader layers are active. See SPEC §8.
type EvaluationMode string

const (
	ModeDev        EvaluationMode = "dev"
	ModeDevProcess EvaluationMode = "dev+process"
	ModeValidation EvaluationMode = "validation"
	ModeMonitoring EvaluationMode = "monitoring"
)

// Grade is the result of executing one grader against a case. See SPEC §6.2.
type Grade struct {
	Criterion string      `json:"criterion"`
	Score     float64     `json:"score"`
	Metric    string      `json:"metric"`
	Passed    bool        `json:"passed"`
	Detail    string      `json:"detail,omitempty"`
	Layer     GraderLayer `json:"layer"`
	Skipped   bool        `json:"skipped,omitempty"`
	Stage     *int        `json:"stage,omitempty"`
	StageName string      `json:"stage_name,omitempty"`
}

// Subject is the normalized system output exposed to graders. See SPEC §7.2.
type Subject struct {
	Query              string                 `json:"query"`
	Answer             string                 `json:"answer"`
	CompletionTime     float64                `json:"completion_time"`
	DocumentsRetrieved int                    `json:"documents_retrieved"`
	CitationsCount     int                    `json:"citations_count"`
	SourcesUsed        []string               `json:"sources_used"`
	Spans              []interface{}          `json:"spans"`
	Metadata           map[string]interface{} `json:"metadata"`
	Stage              *int                   `json:"stage,omitempty"`
	StageName          string                 `json:"stage_name,omitempty"`
	PriorSubject       *Subject               `json:"prior_subject,omitempty"`
}

// CaseResult is the aggregated evaluation result for a single case.
// See SPEC §12.
type CaseResult struct {
	ID           string             `json:"id"`
	Name         string             `json:"name"`
	Category     string             `json:"category"`
	OverallScore float64            `json:"overall_score"`
	Passed       bool               `json:"passed"`
	TimeSeconds  float64            `json:"time_seconds"`
	MetricScores map[string]float64 `json:"metric_scores"`
	Error        string             `json:"error,omitempty"`
	Grades       []Grade            `json:"grades"`
	Stages       []StageResult      `json:"stages,omitempty"`
	Trials       *int               `json:"trials,omitempty"`
	PerTrial     []TrialResult      `json:"per_trial,omitempty"`
	ScoreStddev  *float64           `json:"score_stddev,omitempty"`
	ScoreMin     *float64           `json:"score_min,omitempty"`
	ScoreMax     *float64           `json:"score_max,omitempty"`
	PassRate     *string            `json:"pass_rate,omitempty"`
}

// StageResult is the per-stage summary for multi-stage cases.
type StageResult struct {
	Stage      int     `json:"stage"`
	Name       string  `json:"name"`
	Score      float64 `json:"score"`
	Passed     bool    `json:"passed"`
	GradeCount int     `json:"grade_count"`
}

// TrialResult is the result of a single trial execution.
type TrialResult struct {
	Trial        int     `json:"trial"`
	OverallScore float64 `json:"overall_score"`
	Passed       bool    `json:"passed"`
}

// RunResult is the complete result of an evaluation run. See SPEC §12.
type RunResult struct {
	Label     string         `json:"label,omitempty"`
	Timestamp string         `json:"timestamp"`
	Mode      EvaluationMode `json:"mode"`
	Config    RunConfig      `json:"config"`
	Summary   RunSummary     `json:"summary"`
	Cases     []CaseResult   `json:"cases"`
}

// RunConfig holds non-sensitive configuration for a run.
type RunConfig struct {
	GradePassThreshold float64 `json:"grade_pass_threshold"`
	CasePassThreshold  float64 `json:"case_pass_threshold"`
}

// DefaultRunConfig returns a RunConfig with default threshold values.
func DefaultRunConfig() RunConfig {
	return RunConfig{
		GradePassThreshold: 0.5,
		CasePassThreshold:  0.7,
	}
}

// RunSummary holds aggregate statistics across all cases in a run.
type RunSummary struct {
	OverallScore float64            `json:"overall_score"`
	Passed       int                `json:"passed"`
	Failed       int                `json:"failed"`
	Errored      int                `json:"errored"`
	Total        int                `json:"total"`
	Metrics      map[string]float64 `json:"metrics"`
}
