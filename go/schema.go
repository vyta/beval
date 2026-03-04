package beval

// Validate checks a data structure against a named JSON Schema.
//
// Returns a list of validation error messages. An empty slice means valid.
//
// Will use: github.com/santhosh-tekuri/jsonschema/v6
func Validate(instance interface{}, schemaName string) []string {
	// Stub: returns no errors.
	_ = instance
	_ = schemaName
	return nil
}
