using Beval.Models;
using Xunit;

namespace Beval.Tests;

public class ModelsTests
{
    [Fact]
    public void Grade_RecordEquality()
    {
        var a = new Grade("criterion", 0.95, "correctness", true, "ok", GraderLayer.Deterministic);
        var b = new Grade("criterion", 0.95, "correctness", true, "ok", GraderLayer.Deterministic);

        Assert.Equal(a, b);
    }

    [Fact]
    public void Grade_DefaultSkippedIsFalse()
    {
        var grade = new Grade("test", 1.0, "quality", true, null, GraderLayer.Deterministic);

        Assert.False(grade.Skipped);
        Assert.Null(grade.Stage);
        Assert.Null(grade.StageName);
    }

    [Fact]
    public void Subject_RecordEquality()
    {
        var a = new Subject("query", "answer", 1.5);
        var b = new Subject("query", "answer", 1.5);

        Assert.Equal(a, b);
    }

    [Fact]
    public void CaseResult_RequiredProperties()
    {
        var result = new CaseResult
        {
            Id = "test-case",
            Name = "Test Case",
            Category = "test",
            OverallScore = 0.85,
            Passed = true,
            TimeSeconds = 1.2,
            MetricScores = new Dictionary<string, double> { ["correctness"] = 0.85 },
            Grades = [new Grade("check", 0.85, "correctness", true, null, GraderLayer.Deterministic)],
        };

        Assert.Equal("test-case", result.Id);
        Assert.True(result.Passed);
        Assert.Null(result.Error);
    }

    [Fact]
    public void RunConfig_DefaultThresholds()
    {
        var config = new RunConfig();

        Assert.Equal(0.5, config.GradePassThreshold);
        Assert.Equal(0.7, config.CasePassThreshold);
    }

    [Fact]
    public void MetricCategory_HasExpectedValues()
    {
        Assert.Equal(8, Enum.GetValues<MetricCategory>().Length);
        Assert.True(Enum.IsDefined(MetricCategory.Latency));
        Assert.True(Enum.IsDefined(MetricCategory.Safety));
        Assert.True(Enum.IsDefined(MetricCategory.Cost));
    }

    [Fact]
    public void EvaluationMode_HasExpectedValues()
    {
        Assert.Equal(4, Enum.GetValues<EvaluationMode>().Length);
    }
}
