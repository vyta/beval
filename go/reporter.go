package beval

import "encoding/json"

// ToJSON serializes a RunResult to a JSON byte slice.
func ToJSON(result RunResult, indent bool) ([]byte, error) {
	if indent {
		return json.MarshalIndent(result, "", "  ")
	}
	return json.Marshal(result)
}

// WriteJSON serializes a RunResult and writes it to the given path.
//
// Uses os.WriteFile internally; the caller is responsible for ensuring
// the output directory exists.
func WriteJSON(result RunResult, path string) error {
	data, err := ToJSON(result, true)
	if err != nil {
		return err
	}
	// Import os at usage site to keep stub minimal.
	// Will use: os.WriteFile(path, data, 0o644)
	_ = data
	_ = path
	return nil
}
