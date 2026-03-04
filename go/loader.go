package beval

// LoadCaseFile loads a single YAML case file and returns the parsed content.
//
// Uses typed struct unmarshal with strict field checking to prevent
// unsafe deserialization. Only known fields are accepted.
//
// Will use: gopkg.in/yaml.v3 with Decoder.KnownFields(true)
func LoadCaseFile(path string) (map[string]interface{}, error) {
	// Stub: returns nil.
	// Implementation will use yaml.v3 Decoder with KnownFields(true)
	// for safe, typed deserialization.
	_ = path
	return nil, nil
}

// LoadCaseDirectory loads all YAML case files from a directory.
//
// Searches for *.yaml and *.yml files recursively.
func LoadCaseDirectory(directory string) ([]map[string]interface{}, error) {
	// Stub: returns nil.
	_ = directory
	return nil, nil
}
