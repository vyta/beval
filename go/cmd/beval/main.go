// Command beval is the CLI entrypoint for the beval behavioral evaluation
// framework.
//
// Usage:
//
//	beval <command> [flags]
//
// See cli.spec.yaml for the full interface contract.
package main

import (
	"os"

	"github.com/org/beval/go/internal/cli"
)

func main() {
	code := cli.Run(os.Args, os.Stdout)
	os.Exit(code)
}
