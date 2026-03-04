using Beval.Dsl;
using Beval.Models;

namespace Beval;

/// <summary>
/// Orchestrates case execution. See SPEC §11.
/// </summary>
public class Runner
{
    private readonly EvaluationMode _mode;
    private readonly RunConfig _config;

    public Runner(EvaluationMode mode = EvaluationMode.Dev, RunConfig? config = null)
    {
        _mode = mode;
        _config = config ?? new RunConfig();
    }

    /// <summary>
    /// Execute evaluation cases and return aggregated results.
    /// </summary>
    public RunResult Run(IReadOnlyList<CaseDefinition>? cases = null, string? label = null)
    {
        var caseDefs = cases ?? CaseRegistry.GetRegisteredCases();
        var caseResults = new List<CaseResult>();

        foreach (var caseDef in caseDefs)
        {
            var result = RunCase(caseDef);
            caseResults.Add(result);
        }

        var summary = BuildSummary(caseResults);

        return new RunResult
        {
            Label = label,
            Timestamp = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
            Mode = _mode,
            Config = _config,
            Summary = summary,
            Cases = caseResults,
        };
    }

    private CaseResult RunCase(CaseDefinition caseDef)
    {
        // Stub — throw NotImplementedException until grader pipeline is wired.
        throw new NotImplementedException("Runner.RunCase is not yet implemented.");
    }

    private static RunSummary BuildSummary(List<CaseResult> results)
    {
        // Stub — throw NotImplementedException until scoring is wired.
        throw new NotImplementedException("Runner.BuildSummary is not yet implemented.");
    }
}
