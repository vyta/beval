using YamlDotNet.Serialization;
using YamlDotNet.Serialization.NamingConventions;

namespace Beval;

/// <summary>
/// YAML case file loading with safe typed deserialization.
/// Never uses WithTagMapping for user-supplied YAML.
/// See SPEC §4 for YAML case format.
/// </summary>
public static class Loader
{
    private static readonly IDeserializer Deserializer = new DeserializerBuilder()
        .WithNamingConvention(UnderscoredNamingConvention.Instance)
        .Build();

    /// <summary>
    /// Load a single YAML case file using safe typed deserialization.
    /// </summary>
    public static Dictionary<string, object> LoadCaseFile(string path)
    {
        var content = File.ReadAllText(path);
        var data = Deserializer.Deserialize<Dictionary<string, object>>(content);
        return data ?? throw new InvalidOperationException(
            $"Expected a mapping at top level of {path}");
    }

    /// <summary>
    /// Load all YAML case files from a directory recursively.
    /// </summary>
    public static List<Dictionary<string, object>> LoadCaseDirectory(string directory)
    {
        var results = new List<Dictionary<string, object>>();
        var patterns = new[] { "*.yaml", "*.yml" };

        foreach (var pattern in patterns)
        {
            foreach (var path in Directory.GetFiles(directory, pattern, SearchOption.AllDirectories).Order())
            {
                results.Add(LoadCaseFile(path));
            }
        }

        return results;
    }
}
