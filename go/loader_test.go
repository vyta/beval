package beval

import "testing"

func TestLoadCaseFileStub(t *testing.T) {
	result, err := LoadCaseFile("nonexistent.yaml")
	if err != nil {
		t.Errorf("stub should not return error, got %v", err)
	}
	if result != nil {
		t.Errorf("stub should return nil, got %v", result)
	}
}

func TestLoadCaseDirectoryStub(t *testing.T) {
	results, err := LoadCaseDirectory("nonexistent/")
	if err != nil {
		t.Errorf("stub should not return error, got %v", err)
	}
	if results != nil {
		t.Errorf("stub should return nil, got %v", results)
	}
}
