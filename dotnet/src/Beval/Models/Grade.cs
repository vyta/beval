namespace Beval.Models;

/// <summary>
/// Result of executing one grader against a case. See SPEC §6.2.
/// </summary>
/// <param name="Criterion">The grader criterion text.</param>
/// <param name="Score">Score from 0.0 to 1.0.</param>
/// <param name="Metric">Metric category name.</param>
/// <param name="Passed">Whether the grade meets the pass threshold.</param>
/// <param name="Detail">Optional detail or reasoning.</param>
/// <param name="Layer">Which grader layer produced this grade.</param>
/// <param name="Skipped">Whether the grader was skipped.</param>
/// <param name="Stage">Stage index for multi-stage cases.</param>
/// <param name="StageName">Stage name for multi-stage cases.</param>
public record Grade(
    string Criterion,
    double Score,
    string Metric,
    bool Passed,
    string? Detail,
    GraderLayer Layer,
    bool Skipped = false,
    int? Stage = null,
    string? StageName = null);
