namespace Beval.Models;

/// <summary>
/// Named quality dimension for score grouping. See SPEC §6.4.
/// </summary>
public enum MetricCategory
{
    Latency,
    Coverage,
    Relevance,
    Groundedness,
    Correctness,
    Quality,
    Safety,
    Cost,
}
