using System.Diagnostics;
using OpenTelemetry;
using OpenTelemetry.Exporter;
using OpenTelemetry.Trace;

namespace Beval;

/// <summary>
/// OpenTelemetry tracing setup for process graders. See SPEC §9.
/// </summary>
public static class Tracing
{
    private static readonly ActivitySource Source = new("beval");

    /// <summary>
    /// Configure OpenTelemetry tracing with an in-memory exporter.
    /// Returns the exporter so process graders can inspect captured spans.
    /// </summary>
    public static InMemoryExporter<Activity> SetupTracing(string serviceName = "beval")
    {
        var exporter = new InMemoryExporter<Activity>(new List<Activity>());
        Sdk.CreateTracerProviderBuilder()
            .AddSource(serviceName)
            .AddInMemoryExporter(new List<Activity>())
            .Build();
        return exporter;
    }

    /// <summary>
    /// Start a new activity (span) for tracing.
    /// </summary>
    public static Activity? StartActivity(string name)
    {
        return Source.StartActivity(name);
    }
}
