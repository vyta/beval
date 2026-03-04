namespace Beval.Models;

/// <summary>
/// Grader layer classification. See SPEC §5.1.
/// </summary>
public enum GraderLayer
{
    Deterministic,
    Process,
    AiJudged,
}

/// <summary>
/// Evaluation mode controlling which grader layers are active. See SPEC §8.
/// </summary>
public enum EvaluationMode
{
    Dev,
    DevProcess,
    Validation,
    Monitoring,
}
