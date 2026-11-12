using System.IO;
using System.Reflection;
using Xunit;

namespace @PROJECT_NAME@.Tests;

public sealed class ModMetadataTests
{
    private static readonly Assembly ModAssembly = typeof(@PROJECT_NAME@.@MACHINE_IDENTIFIER@).Assembly;

    [Fact]
    public void ModMetadataMatchesGeneratedIdentity()
    {
        Assert.Equal("@MACHINE_IDENTIFIER@", ModAssembly.GetName().Name);

        System.Type modType = ModAssembly.GetType("@PROJECT_NAME@.@MACHINE_IDENTIFIER@", true)!;
        Assert.Equal("@PROJECT_NAME@", modType.Namespace);

        System.Type modInfoType = ModAssembly.GetType("@PROJECT_NAME@.ModInfo", true)!;
        Assert.Equal("@PROJECT_NAME@", GetConstant(modInfoType, "MOD_ID"));
        Assert.Equal("@TITLE@", GetConstant(modInfoType, "MOD_NAME"));
        Assert.Equal("@AUTHOR@", GetConstant(modInfoType, "MOD_AUTHOR"));
        Assert.False(string.IsNullOrWhiteSpace(GetConstant(modInfoType, "MOD_VERSION")));
        Assert.Equal("@MACHINE_IDENTIFIER@.dll", Path.GetFileName(ModAssembly.Location));
    }

    private static string GetConstant(System.Type type, string name)
    {
        FieldInfo? field = type.GetField(name, BindingFlags.Public | BindingFlags.Static);
        Assert.NotNull(field);
        return (string)field!.GetRawConstantValue()!;
    }
}
