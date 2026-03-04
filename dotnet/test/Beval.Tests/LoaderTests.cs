using Xunit;

namespace Beval.Tests;

public class LoaderTests
{
    [Fact]
    public void LoadCaseFile_ThrowsOnMissingFile()
    {
        var nonExistentPath = Path.Combine(Path.GetTempPath(), "nonexistent-file-" + Guid.NewGuid() + ".yaml");
        Assert.Throws<FileNotFoundException>(() => Loader.LoadCaseFile(nonExistentPath));
    }

    [Fact]
    public void LoadCaseFile_ThrowsOnEmptyYaml()
    {
        var tempFile = Path.GetTempFileName();
        try
        {
            File.WriteAllText(tempFile, "");
            Assert.Throws<InvalidOperationException>(() => Loader.LoadCaseFile(tempFile));
        }
        finally
        {
            File.Delete(tempFile);
        }
    }

    [Fact]
    public void LoadCaseFile_ParsesValidYaml()
    {
        var tempFile = Path.GetTempFileName();
        try
        {
            File.WriteAllText(tempFile, "name: test\ncategory: unit\n");
            var data = Loader.LoadCaseFile(tempFile);

            Assert.Equal("test", data["name"]);
            Assert.Equal("unit", data["category"]);
        }
        finally
        {
            File.Delete(tempFile);
        }
    }

    [Fact]
    public void LoadCaseDirectory_ReturnsEmptyForEmptyDirectory()
    {
        var tempDir = Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString());
        Directory.CreateDirectory(tempDir);
        try
        {
            var results = Loader.LoadCaseDirectory(tempDir);
            Assert.Empty(results);
        }
        finally
        {
            Directory.Delete(tempDir, true);
        }
    }

    /// <summary>
    /// Verify that YAML loading uses safe deserialization and does not
    /// execute arbitrary tags. See SPEC security requirements.
    /// </summary>
    [Fact]
    public void LoadCaseFile_SafeDeserialization_NoTagExecution()
    {
        var tempFile = Path.GetTempFileName();
        try
        {
            // YAML with a custom tag — should not execute anything dangerous
            File.WriteAllText(tempFile, "name: !!python/object:os.system 'echo pwned'\n");
            // YamlDotNet rejects unknown tags by throwing — this is safe behavior
            Assert.ThrowsAny<Exception>(() => Loader.LoadCaseFile(tempFile));
        }
        finally
        {
            File.Delete(tempFile);
        }
    }
}
