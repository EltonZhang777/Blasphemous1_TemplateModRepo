using Blasphemous.ModdingAPI;

namespace Blasphemous1.ModTest;

internal sealed class TestMod : BlasMod
{
    internal TestMod()
        : base(ModInfo.ModId, ModInfo.ModName, ModInfo.ModAuthor, ModInfo.ModVersion)
    {
    }
}
