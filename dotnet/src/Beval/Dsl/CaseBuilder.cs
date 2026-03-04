using Beval.Models;

namespace Beval.Dsl;

/// <summary>
/// Internal representation of a registered case. See SPEC §4.
/// </summary>
public class CaseDefinition
{
    public required string Id { get; init; }
    public required string Name { get; init; }
    public required string Category { get; init; }
    public List<string> Tags { get; init; } = [];
    public Action<CaseBuilder>? Body { get; init; }
    public List<Dictionary<string, object>>? Examples { get; init; }
}

/// <summary>
/// Fluent builder for constructing case steps. See SPEC §4.1.
/// </summary>
public class CaseBuilder
{
    private readonly Dictionary<string, object?> _givens = new();
    private readonly List<string> _whens = [];
    private readonly List<(string Criterion, object?[] Args)> _thens = [];

    /// <summary>
    /// Set a precondition. See SPEC §4.1.
    /// </summary>
    public CaseBuilder Given(string name, object? value = null)
    {
        _givens[name] = value;
        return this;
    }

    /// <summary>
    /// Declare the system action. See SPEC §4.1.
    /// </summary>
    public CaseBuilder When(string action)
    {
        _whens.Add(action);
        return this;
    }

    /// <summary>
    /// Add a grading criterion. See SPEC §4.1.
    /// </summary>
    public CaseBuilder Then(string criterion, params object?[] args)
    {
        _thens.Add((criterion, args));
        return this;
    }

    internal IReadOnlyDictionary<string, object?> Givens => _givens;
    internal IReadOnlyList<string> Whens => _whens;
    internal IReadOnlyList<(string Criterion, object?[] Args)> Thens => _thens;
}

/// <summary>
/// Builds and registers evaluation cases. See SPEC §4.1.
/// </summary>
public static class CaseRegistry
{
    private static readonly List<CaseDefinition> Registry = [];

    /// <summary>
    /// Create and register a new evaluation case.
    /// </summary>
    public static CaseDefinition Case(
        string name,
        string category = "",
        List<string>? tags = null,
        Action<CaseBuilder>? body = null)
    {
        var definition = new CaseDefinition
        {
            Id = name.ToLowerInvariant().Replace(' ', '-'),
            Name = name,
            Category = category,
            Tags = tags ?? [],
            Body = body,
        };
        Registry.Add(definition);
        return definition;
    }

    /// <summary>
    /// Return all registered case definitions.
    /// </summary>
    public static IReadOnlyList<CaseDefinition> GetRegisteredCases() => Registry.AsReadOnly();

    /// <summary>
    /// Clear the case registry. Primarily for testing.
    /// </summary>
    public static void ClearRegistry() => Registry.Clear();
}
