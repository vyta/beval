using System.Text.Json;
using System.Text.Json.Nodes;
using Json.Schema;

namespace Beval;

/// <summary>
/// JSON Schema validation using shared schemas from spec/.
/// See SPEC §12, §13.
/// </summary>
public static class Schema
{
    /// <summary>
    /// Validate a JSON element against a named schema from the spec/schemas/ directory.
    /// </summary>
    /// <param name="instance">The JSON data to validate.</param>
    /// <param name="schemaName">Schema filename (e.g., "case.schema.json").</param>
    /// <returns>List of validation error messages. Empty list means valid.</returns>
    public static List<string> Validate(JsonNode instance, string schemaName)
    {
        // Stub — resolve schema path relative to project root and validate.
        throw new NotImplementedException("Schema.Validate is not yet implemented.");
    }
}
