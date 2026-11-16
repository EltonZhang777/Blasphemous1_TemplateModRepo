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

## CI and releases

Pull requests targeting `main` run restore, build, test, formatting, and the tracked C# CRLF check on Windows with .NET 10. Pushes to `main` run the same build and test validation.

A `vX.Y.Z...` or bare SemVer tag on a commit reachable from `main` creates a draft GitHub release containing only `publish/@MACHINE_IDENTIFIER@.zip`. Configure `NUGET_USERNAME` for OIDC trusted publishing; when it is missing, NuGet publication is skipped with a warning. Configure `WEBHOOK_URL` for Discord notifications on published stable releases; when it is missing, the notification is skipped with a warning.

## Agent documentation

See [AGENTS.md](AGENTS.md), [docs/agents/domain.md](docs/agents/domain.md), and the project ADRs when present.
