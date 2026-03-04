namespace Beval.Models;

/// <summary>
/// Non-sensitive configuration snapshot for a run.
/// </summary>
public record RunConfig(
    double GradePassThreshold = 0.5,
    double CasePassThreshold = 0.7);

/// <summary>
/// Aggregate summary across all cases in a run.
/// </summary>
public class RunSummary
{
    public required double OverallScore { get; init; }
    public required int Passed { get; init; }
    public required int Failed { get; init; }
    public required int Errored { get; init; }
    public required int Total { get; init; }
    public required Dictionary<string, double> Metrics { get; init; }
}

/// <summary>
/// Complete result of an evaluation run. See SPEC §12.
/// </summary>
public class RunResult
{
    [System.Text.Json.Serialization.JsonPropertyName("label")]
    public string? Label { get; init; }
    public required string Timestamp { get; init; }
    public required EvaluationMode Mode { get; init; }
    public required RunConfig Config { get; init; }
    public required RunSummary Summary { get; init; }
    public required List<CaseResult> Cases { get; init; }
}
