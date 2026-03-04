using Beval.Models;

namespace Beval.Graders;

/// <summary>
/// Interface for scoring system output against a criterion. See SPEC §7.
/// </summary>
public interface IGrader
{
    /// <summary>
    /// Evaluate a subject against the given criterion and arguments.
    /// </summary>
    /// <param name="criterion">The grader criterion text.</param>
    /// <param name="args">Additional arguments from the then clause.</param>
    /// <param name="subject">Normalized system output.</param>
    /// <returns>A grade with score, metric, and detail.</returns>
    Grade Evaluate(string criterion, object?[] args, Subject subject);

    /// <summary>
    /// The grader layer this grader belongs to.
    /// </summary>
    GraderLayer Layer { get; }

    /// <summary>
    /// The default metric category for grades produced by this grader.
    /// </summary>
    string Metric { get; }
}
