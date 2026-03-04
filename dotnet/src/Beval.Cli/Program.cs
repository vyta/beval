using System.CommandLine;

const string Version = "0.1.0";
const string SpecVersion = "0.1.0";

var rootCommand = new RootCommand("Behavioral evaluation framework for AI agents and LLM-powered systems.")
{
    BuildRunCommand(),
    BuildValidateCommand(),
    BuildCompareCommand(),
    BuildBaselineCommand(),
    BuildCacheCommand(),
    BuildInitCommand(),
    BuildVersionCommand(),
};

// Global options
var configOption = new Option<string?>(["--config", "-c"], "Path to eval.config.yaml configuration file.");
var verboseOption = new Option<bool>("--verbose", "Enable verbose output.");
var quietOption = new Option<bool>(["--quiet", "-q"], "Suppress non-essential output.");
var noColorOption = new Option<bool>("--no-color", "Disable colored output.");
var jsonOption = new Option<bool>("--json", "Output results as JSON.");

rootCommand.AddGlobalOption(configOption);
rootCommand.AddGlobalOption(verboseOption);
rootCommand.AddGlobalOption(quietOption);
rootCommand.AddGlobalOption(noColorOption);
rootCommand.AddGlobalOption(jsonOption);

return await rootCommand.InvokeAsync(args);

// --- Subcommand builders ---

static Command BuildRunCommand()
{
    var command = new Command("run", "Execute evaluation cases.");
    command.AddOption(new Option<string>(["--mode", "-m"], () => "dev", "Evaluation mode (dev, dev+process, validation, monitoring)."));
    var labelOption = new Option<string?>(["--label", "-l"], "Run label for traceability.");
    command.AddOption(labelOption);
    command.AddOption(new Option<string?>("--cases", "Path to case YAML file or directory of case files."));
    command.AddOption(new Option<string?>("--subject", "Path to a JSON file containing canned system output (Subject). When provided, the runner uses this instead of invoking the live system."));
    command.AddOption(new Option<string?>("--case", "Filter by case ID."));
    command.AddOption(new Option<string?>("--category", "Filter by category."));
    command.AddOption(new Option<string[]>(["--tag", "-t"], "Include only cases matching these tags."));
    command.AddOption(new Option<string[]>("--exclude-tag", "Exclude cases matching these tags."));
    command.AddOption(new Option<int>("--trials", () => 1, "Number of trial executions per case."));
    command.AddOption(new Option<string>("--trial-aggregation", () => "mean", "Strategy for aggregating trial scores."));
    command.AddOption(new Option<string?>(["--output", "-o"], "Results output directory."));
    command.AddOption(new Option<string>("--format", () => "json", "Results output format (json, jsonl)."));
    command.AddOption(new Option<bool>("--use-cache", "Use cached outputs."));
    command.AddOption(new Option<bool>("--score-only", "Re-score cached outputs."));
    command.AddOption(new Option<bool>("--no-cache", "Disable caching for this run."));
    command.AddOption(new Option<bool>("--save-baseline", "Save results as the baseline snapshot."));
    command.AddOption(new Option<bool>("--compare-baseline", "Compare results against the saved baseline."));
    command.AddOption(new Option<double>("--regression-threshold", () => 0.05, "Fail if any metric drops more than this value from baseline."));
    command.AddOption(new Option<bool>("--scrub", () => true, "Scrub sensitive values from results output."));

    command.SetHandler(() =>
    {
        Console.Error.WriteLine("beval run: not yet implemented");
        Environment.ExitCode = 2;
    });

    return command;
}

static Command BuildValidateCommand()
{
    var command = new Command("validate", "Validate case files, configuration, and schemas.");
    command.AddOption(new Option<string?>("--cases", "Path to case files or directory to validate."));
    command.AddOption(new Option<string?>("--config", "Path to configuration file to validate."));
    command.AddOption(new Option<string?>("--schema", "Path to schema file for validation."));

    command.SetHandler(() =>
    {
        Console.Error.WriteLine("beval validate: not yet implemented");
        Environment.ExitCode = 2;
    });

    return command;
}

static Command BuildCompareCommand()
{
    var command = new Command("compare", "Compare results across runs.");
    command.AddOption(new Option<string[]>("--results", "Paths to result files or directories to compare."));
    command.AddOption(new Option<string?>(["--output", "-o"], "Path for comparison output file."));
    command.AddOption(new Option<string>("--format", () => "table", "Output format (json, table)."));

    command.SetHandler(() =>
    {
        Console.Error.WriteLine("beval compare: not yet implemented");
        Environment.ExitCode = 2;
    });

    return command;
}

static Command BuildBaselineCommand()
{
    var command = new Command("baseline", "Manage baseline snapshots.");
    command.AddCommand(new Command("save", "Save the most recent results as the baseline."));
    command.AddCommand(new Command("show", "Display the current baseline."));
    command.AddCommand(new Command("clear", "Remove the saved baseline."));

    return command;
}

static Command BuildCacheCommand()
{
    var command = new Command("cache", "Manage the response cache.");
    command.AddCommand(new Command("show", "Display cache statistics."));
    command.AddCommand(new Command("clear", "Clear all cached responses."));

    return command;
}

static Command BuildInitCommand()
{
    var command = new Command("init", "Initialize a new beval project with default configuration and example cases.");
    command.AddOption(new Option<string>("--dir", () => ".", "Target directory for project initialization."));

    command.SetHandler(() =>
    {
        Console.Error.WriteLine("beval init: not yet implemented");
        Environment.ExitCode = 2;
    });

    return command;
}

static Command BuildVersionCommand()
{
    var command = new Command("version", "Print version and build information.");

    command.SetHandler(() =>
    {
        Console.WriteLine($"beval {Version} (spec {SpecVersion})");
        Console.WriteLine($"runtime: .NET {Environment.Version}");
    });

    return command;
}
