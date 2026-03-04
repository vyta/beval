// Package cli provides the internal CLI implementation for beval.
//
// This package is internal and cannot be imported by external modules.
// It implements subcommand dispatch using the stdlib flag package,
// matching the interface defined in cli.spec.yaml.
package cli

import (
	"flag"
	"fmt"
	"io"
)

const version = "0.1.0"
const specVersion = "0.2.0"

// Run is the main CLI entrypoint. It parses os.Args and dispatches
// to the appropriate subcommand.
func Run(args []string, stdout io.Writer) int {
	if len(args) < 2 {
		printUsage(stdout)
		return 2
	}

	cmd := args[1]
	switch cmd {
	case "run":
		return cmdRun(args[2:], stdout)
	case "validate":
		return cmdValidate(args[2:], stdout)
	case "compare":
		return cmdCompare(args[2:], stdout)
	case "baseline":
		return cmdBaseline(args[2:], stdout)
	case "cache":
		return cmdCache(args[2:], stdout)
	case "init":
		return cmdInit(args[2:], stdout)
	case "version":
		return cmdVersion(stdout)
	case "--help", "-h", "help":
		printUsage(stdout)
		return 0
	default:
		fmt.Fprintf(stdout, "unknown command: %s\n", cmd)
		printUsage(stdout)
		return 2
	}
}

func printUsage(w io.Writer) {
	fmt.Fprintln(w, "Usage: beval <command> [flags]")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "Commands:")
	fmt.Fprintln(w, "  run        Execute evaluation cases")
	fmt.Fprintln(w, "  validate   Validate case files, configuration, and schemas")
	fmt.Fprintln(w, "  compare    Compare results across runs")
	fmt.Fprintln(w, "  baseline   Manage baseline snapshots")
	fmt.Fprintln(w, "  cache      Manage the response cache")
	fmt.Fprintln(w, "  init       Initialize a new beval project")
	fmt.Fprintln(w, "  version    Print version and build information")
	fmt.Fprintln(w)
	fmt.Fprintln(w, "Global flags:")
	fmt.Fprintln(w, "  -c, --config    Path to eval.config.yaml")
	fmt.Fprintln(w, "  --verbose       Enable verbose output")
	fmt.Fprintln(w, "  -q, --quiet     Suppress non-essential output")
	fmt.Fprintln(w, "  --no-color      Disable colored output")
	fmt.Fprintln(w, "  --json          Output results as JSON")
	fmt.Fprintln(w, "  -h, --help      Show help")
}

func cmdRun(args []string, w io.Writer) int {
	fs := flag.NewFlagSet("run", flag.ContinueOnError)
	fs.SetOutput(w)
	_ = fs.String("m", "dev", "Evaluation mode")
	_ = fs.String("mode", "dev", "Evaluation mode")
	_ = fs.String("l", "", "Run label for traceability")
	_ = fs.String("label", "", "Run label for traceability")
	_ = fs.String("cases", "", "Path to case YAML file or directory of case files")
	_ = fs.String("subject", "", "Path to a JSON file containing canned system output (Subject)")
	_ = fs.String("case", "", "Filter by case ID")
	_ = fs.String("category", "", "Filter by category")
	_ = fs.String("t", "", "Include only matching tags")
	_ = fs.String("tag", "", "Include only matching tags")
	_ = fs.String("exclude-tag", "", "Exclude matching tags")
	_ = fs.Int("trials", 1, "Number of trial executions per case")
	_ = fs.String("trial-aggregation", "mean", "Strategy for aggregating trial scores")
	_ = fs.String("o", "", "Results output path")
	_ = fs.String("output", "", "Results output path")
	_ = fs.String("format", "json", "Results output format (json, jsonl)")
	_ = fs.Bool("use-cache", false, "Use cached outputs")
	_ = fs.Bool("score-only", false, "Re-score cached outputs")
	_ = fs.Bool("no-cache", false, "Disable caching for this run")
	_ = fs.Bool("save-baseline", false, "Save results as baseline")
	_ = fs.Bool("compare-baseline", false, "Compare results against baseline")
	_ = fs.Float64("regression-threshold", 0.05, "Fail if any metric drops more than this value from baseline")
	_ = fs.Bool("scrub", true, "Scrub sensitive values from output")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	// Stub: run subcommand not yet implemented.
	fmt.Fprintln(w, "run: not yet implemented")
	return 0
}

func cmdValidate(args []string, w io.Writer) int {
	fs := flag.NewFlagSet("validate", flag.ContinueOnError)
	fs.SetOutput(w)
	_ = fs.String("cases", "", "Path to case files or directory")
	_ = fs.String("config", "", "Path to configuration file")
	_ = fs.String("schema", "", "Path to schema file")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	// Stub: validate subcommand not yet implemented.
	fmt.Fprintln(w, "validate: not yet implemented")
	return 0
}

func cmdCompare(args []string, w io.Writer) int {
	fs := flag.NewFlagSet("compare", flag.ContinueOnError)
	fs.SetOutput(w)
	if err := fs.Parse(args); err != nil {
		return 2
	}
	// Stub: compare subcommand not yet implemented.
	fmt.Fprintln(w, "compare: not yet implemented")
	return 0
}

func cmdBaseline(args []string, w io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(w, "Usage: beval baseline <save|show|clear>")
		return 2
	}
	sub := args[0]
	switch sub {
	case "save":
		fmt.Fprintln(w, "baseline save: not yet implemented")
	case "show":
		fmt.Fprintln(w, "baseline show: not yet implemented")
	case "clear":
		fmt.Fprintln(w, "baseline clear: not yet implemented")
	default:
		fmt.Fprintf(w, "unknown baseline subcommand: %s\n", sub)
		return 2
	}
	return 0
}

func cmdCache(args []string, w io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(w, "Usage: beval cache <show|clear>")
		return 2
	}
	sub := args[0]
	switch sub {
	case "show":
		fmt.Fprintln(w, "cache show: not yet implemented")
	case "clear":
		fmt.Fprintln(w, "cache clear: not yet implemented")
	default:
		fmt.Fprintf(w, "unknown cache subcommand: %s\n", sub)
		return 2
	}
	return 0
}

func cmdInit(args []string, w io.Writer) int {
	fs := flag.NewFlagSet("init", flag.ContinueOnError)
	fs.SetOutput(w)
	_ = fs.String("dir", ".", "Target directory")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	// Stub: init subcommand not yet implemented.
	fmt.Fprintln(w, "init: not yet implemented")
	return 0
}

func cmdVersion(w io.Writer) int {
	fmt.Fprintf(w, "beval %s (spec %s)\n", version, specVersion)
	return 0
}
