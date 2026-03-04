namespace Beval.Models;

/// <summary>
/// Normalized system output exposed to graders. See SPEC §7.2.
/// </summary>
/// <param name="Query">The input query.</param>
/// <param name="Answer">The system response text.</param>
/// <param name="CompletionTime">Time in seconds to produce the answer.</param>
/// <param name="DocumentsRetrieved">Number of documents retrieved.</param>
/// <param name="CitationsCount">Number of citations in the answer.</param>
/// <param name="SourcesUsed">Sources referenced by the system.</param>
/// <param name="Spans">OpenTelemetry spans from the system execution.</param>
/// <param name="Metadata">Arbitrary metadata from the system.</param>
/// <param name="Stage">Stage index for multi-stage cases.</param>
/// <param name="StageName">Stage name for multi-stage cases.</param>
/// <param name="PriorSubject">Subject from the previous stage.</param>
public record Subject(
    string Query,
    string Answer,
    double CompletionTime,
    int DocumentsRetrieved = 0,
    int CitationsCount = 0,
    IReadOnlyList<string>? SourcesUsed = null,
    IReadOnlyList<object>? Spans = null,
    IReadOnlyDictionary<string, object>? Metadata = null,
    int? Stage = null,
    string? StageName = null,
    Subject? PriorSubject = null);
