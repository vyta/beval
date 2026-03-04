#!/usr/bin/env node

/**
 * CLI implementation for the beval framework.
 *
 * Maps the cli.spec.yaml interface contract to commander subcommands.
 * See SPEC.md §11 (Runner) and spec/cli.spec.yaml.
 */

import { Command } from "commander";

const VERSION = "0.1.0";
const SPEC_VERSION = "0.2.0";

function buildProgram(): Command {
  const program = new Command();

  program
    .name("beval")
    .description(
      "Behavioral evaluation framework for AI agents and LLM-powered systems.",
    )
    .option("-c, --config <path>", "Path to eval.config.yaml configuration file")
    .option("--verbose", "Enable verbose output", false)
    .option("-q, --quiet", "Suppress non-essential output", false)
    .option("--no-color", "Disable colored output")
    .option("--json", "Output results as JSON", false);

  // --- run ---
  program
    .command("run")
    .description("Execute evaluation cases.")
    .option(
      "-m, --mode <mode>",
      "Evaluation mode",
      "dev",
    )
    .option("-l, --label <label>", "Run label for traceability")
    .option(
      "--cases <path>",
      "Path to case YAML file or directory of case files",
    )
    .option(
      "--subject <path>",
      "Path to a JSON file containing canned system output (Subject). " +
        "When provided, the runner uses this instead of invoking the live system.",
    )
    .option("--case <id>", "Filter by case ID")
    .option("--category <category>", "Filter by category")
    .option("-t, --tag <tags...>", "Include only matching tags")
    .option("--exclude-tag <tags...>", "Exclude matching tags")
    .option("--trials <n>", "Number of trial executions per case", "1")
    .option(
      "--trial-aggregation <strategy>",
      "Trial score aggregation strategy",
      "mean",
    )
    .option("-o, --output <dir>", "Results output directory")
    .option("--format <format>", "Results output format", "json")
    .option("--use-cache", "Use cached outputs", false)
    .option("--score-only", "Re-score cached outputs", false)
    .option("--no-cache", "Disable caching for this run")
    .option("--save-baseline", "Save results as baseline after run", false)
    .option("--compare-baseline", "Compare results against baseline", false)
    .option(
      "--regression-threshold <n>",
      "Fail if any metric drops more than this value from baseline",
      "0.05",
    )
    .option("--scrub", "Scrub sensitive values from output", true)
    .action((_options) => {
      // Stub: full implementation will invoke the Runner
      if (!program.opts().quiet) {
        console.log("Running evaluations...");
      }
    });

  // --- validate ---
  program
    .command("validate")
    .description("Validate case files, configuration, and schemas.")
    .option("--cases <path>", "Path to case files or directory")
    .option("--config <path>", "Path to config file to validate")
    .option("--schema <path>", "Path to schema file for validation")
    .action((_options) => {
      console.log("Validating...");
    });

  // --- compare ---
  program
    .command("compare")
    .description("Compare results across runs.")
    .option("--results <paths...>", "Paths to result files or directories")
    .option("-o, --output <path>", "Path for comparison output file")
    .option("--format <format>", "Output format for comparison results", "table")
    .action((_options) => {
      console.log("Comparing results...");
    });

  // --- baseline ---
  const baseline = program
    .command("baseline")
    .description("Manage baseline snapshots.");

  baseline
    .command("save")
    .description("Save the most recent results as the baseline.")
    .action(() => {
      console.log("Saving baseline...");
    });

  baseline
    .command("show")
    .description("Display the current baseline.")
    .action(() => {
      console.log("Showing baseline...");
    });

  baseline
    .command("clear")
    .description("Remove the saved baseline.")
    .action(() => {
      console.log("Clearing baseline...");
    });

  // --- cache ---
  const cache = program
    .command("cache")
    .description("Manage the response cache.");

  cache
    .command("show")
    .description("Display cache statistics.")
    .action(() => {
      console.log("Showing cache statistics...");
    });

  cache
    .command("clear")
    .description("Clear all cached responses.")
    .action(() => {
      console.log("Clearing cache...");
    });

  // --- init ---
  program
    .command("init")
    .description(
      "Initialize a new beval project with default configuration and example cases.",
    )
    .option("--dir <path>", "Target directory for project initialization", ".")
    .action((_options) => {
      console.log("Initializing project...");
    });

  // --- version ---
  program
    .command("version")
    .description("Print version and build information.")
    .action(() => {
      console.log(`beval v${VERSION} (spec v${SPEC_VERSION})`);
    });

  return program;
}

/** Apply BEVAL_* environment variable overrides. */
function applyEnvOverrides(): void {
  // NO_COLOR support (clig.dev standard)
  if (process.env["NO_COLOR"] !== undefined) {
    process.argv.push("--no-color");
  }
}

export function main(argv?: string[]): void {
  applyEnvOverrides();
  const program = buildProgram();
  program.parse(argv ?? process.argv);
}

// Direct execution
main();
