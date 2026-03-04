package beval

// NormalizeSubject creates a normalized Subject from system output. See SPEC §7.2.
//
// The returned Subject provides a consistent interface for graders regardless
// of the underlying system implementation.
func NormalizeSubject(
	query string,
	answer string,
	completionTime float64,
	opts ...SubjectOption,
) Subject {
	s := Subject{
		Query:          query,
		Answer:         answer,
		CompletionTime: completionTime,
		SourcesUsed:    []string{},
		Spans:          []interface{}{},
		Metadata:       map[string]interface{}{},
	}
	for _, opt := range opts {
		opt(&s)
	}
	return s
}

// SubjectOption configures optional fields on a Subject.
type SubjectOption func(*Subject)

// WithDocumentsRetrieved sets the documents retrieved count.
func WithDocumentsRetrieved(n int) SubjectOption {
	return func(s *Subject) {
		s.DocumentsRetrieved = n
	}
}

// WithCitationsCount sets the citations count.
func WithCitationsCount(n int) SubjectOption {
	return func(s *Subject) {
		s.CitationsCount = n
	}
}

// WithSourcesUsed sets the sources used list.
func WithSourcesUsed(sources []string) SubjectOption {
	return func(s *Subject) {
		s.SourcesUsed = sources
	}
}

// WithMetadata sets additional metadata on the subject.
func WithMetadata(meta map[string]interface{}) SubjectOption {
	return func(s *Subject) {
		s.Metadata = meta
	}
}
