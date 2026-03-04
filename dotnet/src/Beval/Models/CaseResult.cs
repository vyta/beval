namespace Beval.Models;

/// <summary>
/// Per-stage summary for multi-stage cases.
/// </summary>
public record StageResult(
    int Stage,
    string Name,
    double Score,
    bool Passed,
    int GradeCount);

/// <summary>
/// Result of a single trial execution.
/// </summary>
public record TrialResult(
    int Trial,
    double OverallScore,
    bool Passed);

/// <summary>
/// Aggregated evaluation result for a single case. See SPEC §12.
/// </summary>
public class CaseResult
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Category { get; init; }
    public required double OverallScore { get; init; }
    public required bool Passed { get; init; }
    public required double TimeSeconds { get; init; }
    public required Dictionary<string, double> MetricScores { get; init; }
    public string? Error { get; init; }
    public required List<Grade> Grades { get; init; }
    public List<StageResult>? Stages { get; init; }
    public int? Trials { get; init; }
    public List<TrialResult>? PerTrial { get; init; }
    public double? ScoreStddev { get; init; }
    public double? ScoreMin { get; init; }
    public double? ScoreMax { get; init; }
    public string? PassRate { get; init; }
}
