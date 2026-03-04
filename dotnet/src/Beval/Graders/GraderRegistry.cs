using Beval.Models;

namespace Beval.Graders;

/// <summary>
/// A registered grader entry with its pattern, grader instance, and options.
/// See SPEC §7.1.
/// </summary>
internal sealed class GraderEntry
{
    public required string Pattern { get; init; }
    public required IGrader Grader { get; init; }
}

/// <summary>
/// Registry for grader pattern matching and lookup. See SPEC §7.1.
/// </summary>
public static class GraderRegistry
{
    private static readonly List<GraderEntry> Entries = [];

    /// <summary>
    /// Register a grader against a pattern. See SPEC §7.1.
    /// </summary>
    public static void Register(string pattern, IGrader grader)
    {
        Entries.Add(new GraderEntry
        {
            Pattern = pattern.ToLowerInvariant(),
            Grader = grader,
        });
    }

    /// <summary>
    /// Find the first grader matching a criterion via prefix match. See SPEC §7.1.
    /// </summary>
    public static IGrader? Match(string criterion)
    {
        var criterionLower = criterion.ToLowerInvariant();
        foreach (var entry in Entries)
        {
            if (criterionLower == entry.Pattern || criterionLower.StartsWith(entry.Pattern, StringComparison.Ordinal))
            {
                return entry.Grader;
            }
        }

        return null;
    }

    /// <summary>
    /// Clear the grader registry. Primarily for testing.
    /// </summary>
    public static void Clear() => Entries.Clear();
}
