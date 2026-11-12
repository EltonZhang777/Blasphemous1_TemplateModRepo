using BepInEx;

namespace Blasphemous1.ModTest;

[BepInPlugin(ModInfo.ModId, ModInfo.ModName, ModInfo.ModVersion)]
[BepInDependency("Blasphemous.ModdingAPI", "3.0.1")]
internal sealed class Main : BaseUnityPlugin
{
    private TestMod? _mod;

    private void Start()
    {
        _mod = new TestMod();
        Logger.LogInfo($"[{ModInfo.ModId}] STARTUP_READY");
    }
}
