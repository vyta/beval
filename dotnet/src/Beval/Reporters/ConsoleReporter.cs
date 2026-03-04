using System.Text.Json;
using Beval.Models;

namespace Beval.Reporters;

/// <summary>
/// Formats and outputs evaluation results to console or JSON. See SPEC §12.
/// </summary>
public static class ConsoleReporter
{
    /// <summary>
    /// Serialize a <see cref="RunResult"/> to a JSON string.
    /// </summary>
    public static string ToJson(RunResult result, int indent = 2)
    {
        var options = new JsonSerializerOptions
        {
            WriteIndented = indent > 0,
            PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        };
        return JsonSerializer.Serialize(result, options);
    }

    /// <summary>
    /// Write a <see cref="RunResult"/> to a JSON file.
    /// </summary>
    public static void WriteJson(RunResult result, string path)
    {
        var json = ToJson(result);
        File.WriteAllText(path, json);
    }
}
