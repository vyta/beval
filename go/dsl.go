package beval

// CaseDefinition is the internal representation of a registered case.
type CaseDefinition struct {
	ID       string
	Name     string
	Category string
	Tags     []string
}

// CaseBuilder provides a fluent interface for constructing case steps.
// See SPEC §4.1.
type CaseBuilder struct {
	def   CaseDefinition
	steps []step
}

type step struct {
	kind  string // "given", "when", "then"
	key   string
	value interface{}
}

// CaseOption configures optional fields on a CaseDefinition.
type CaseOption func(*CaseDefinition)

// Category returns a CaseOption that sets the case category.
func Category(c string) CaseOption {
	return func(d *CaseDefinition) {
		d.Category = c
	}
}

// Tags returns a CaseOption that sets the case tags.
func Tags(tags ...string) CaseOption {
	return func(d *CaseDefinition) {
		d.Tags = tags
	}
}

// Case creates a new CaseBuilder for defining an evaluation case.
// See SPEC §4.1.
//
//	s := beval.Case("AI legislation search", beval.Category("legislation"))
//	s.Given("a query", "What actions has Congress taken on AI policy?")
//	s.When("the agent researches this query")
//	s.Then("the answer should mention", "artificial intelligence")
func Case(name string, opts ...CaseOption) *CaseBuilder {
	def := CaseDefinition{
		ID:   name,
		Name: name,
	}
	for _, opt := range opts {
		opt(&def)
	}
	return &CaseBuilder{def: def}
}

// Given sets a precondition on the case. See SPEC §4.1.
func (s *CaseBuilder) Given(key string, value interface{}) *CaseBuilder {
	s.steps = append(s.steps, step{kind: "given", key: key, value: value})
	return s
}

// When declares the system action. See SPEC §4.1.
func (s *CaseBuilder) When(action string) *CaseBuilder {
	s.steps = append(s.steps, step{kind: "when", key: action})
	return s
}

// Then adds a grading criterion. See SPEC §4.1.
func (s *CaseBuilder) Then(criterion string, args ...interface{}) *CaseBuilder {
	s.steps = append(s.steps, step{kind: "then", key: criterion, value: args})
	return s
}

// Definition returns the underlying CaseDefinition.
func (s *CaseBuilder) Definition() CaseDefinition {
	return s.def
}

// caseRegistry holds all registered cases.
var caseRegistry []*CaseBuilder

// Register adds a case to the global case registry.
func Register(s *CaseBuilder) {
	caseRegistry = append(caseRegistry, s)
}

// RegisteredCases returns all registered cases.
func RegisteredCases() []*CaseBuilder {
	return caseRegistry
}
