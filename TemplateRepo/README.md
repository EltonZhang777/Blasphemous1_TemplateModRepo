# @TITLE@

A Blasphemous 1 Mod generated from the official `Blasphemous.Modding.Templates` `1.4.1` baseline.

## Requirements

- Windows with .NET SDK 10
- The `Blasphemous.Modding.Templates` package installed at exactly `1.4.1` when using the generator
- A Blasphemous 1 installation with BepInEx and the matching ModdingAPI only for in-game testing

## Build and test

```powershell
dotnet restore @PROJECT_NAME@.sln
dotnet build @PROJECT_NAME@.sln --no-restore
dotnet test @PROJECT_NAME@.sln --no-build
```

The automated test project targets `net48` and references the real `net35` Mod assembly. It does not require Blasphemous, Unity, or BepInEx to be installed.

## Development deployment

Deployment is opt-in. The default build creates a Mod package under `publish/` without requiring a Steam installation.

```powershell
dotnet build @PROJECT_NAME@.sln -p:DeployToGame=true -p:DevFolder="C:\path\to\Blasphemous\Modding"
```

The `DeployToGame` property and a valid `DevFolder` are both required before files are copied to the game profile.

## Resources and Mod package

Put Mod resources under `resources/`. The generated Mod package contains `plugins/@MACHINE_IDENTIFIER@.dll` and the tracked resource layout. Test projects are not included in the package.

## Agent documentation

See [AGENTS.md](AGENTS.md), [docs/agents/domain.md](docs/agents/domain.md), and the project ADRs when present.
