using Beval.Models;

namespace Beval.Judges;

/// <summary>
/// Interface for LLM-based judges. See SPEC §10.
/// </summary>
public interface IJudge
{
    /// <summary>
    /// Evaluate a subject answer against a criterion.
    /// </summary>
    /// <param name="criterion">The evaluation criterion.</param>
    /// <param name="subjectAnswer">The system's response text.</param>
    /// <param name="context">Optional additional context.</param>
    /// <returns>A grade with score, metric, and reasoning detail.</returns>
    Grade Evaluate(string criterion, string subjectAnswer, IDictionary<string, object>? context = null);
}

/// <summary>
/// A no-op judge that returns a skipped grade. Used when no judge is configured.
/// </summary>
public sealed class NullJudge : IJudge
{
    public Grade Evaluate(string criterion, string subjectAnswer, IDictionary<string, object>? context = null)
    {
        return new Grade(
            Criterion: criterion,
            Score: 0.0,
            Metric: "quality",
            Passed: false,
            Detail: "No judge configured.",
            Layer: GraderLayer.AiJudged,
            Skipped: true);
    }
}
