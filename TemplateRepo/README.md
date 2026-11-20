# @TITLE@

`@TITLE@` is a Blasphemous 1 Mod built with ModdingAPI. The root project contains the Mod, the adjacent Automated Test Project verifies its metadata without starting the game, and a Verification Mod project can provide manual in-game checks when it is present.

## Requirements

### Development prerequisites

- Windows
- .NET SDK 10
- Git and an authenticated GitHub remote with permission to push release tags

Verify the SDK in PowerShell:

```powershell
dotnet --version
```

The first version number must be `10`.

### In-game testing prerequisites

- Blasphemous 1
- BepInEx installed for Blasphemous 1
- Blasphemous ModdingAPI 3.0.1

These requirements apply only to manual in-game testing. The Automated Test Project does not require Blasphemous, Unity, or BepInEx.

## Build and test

Run these commands from the repository root in order:

```powershell
dotnet restore @PROJECT_NAME@.sln
dotnet build @PROJECT_NAME@.sln --no-restore
dotnet test @PROJECT_NAME@.sln --no-build
```

The Automated Test Project is a `net48` xUnit project that references the real `net35` Mod assembly.

The formatting helper changes tracked source files, so review and commit any resulting changes deliberately:

```powershell
.\dotnet_format.bat
```

It restores the solution before applying whitespace and style fixes. Pass a solution or project path as its first argument when more than one exists.

CI formatting verification is read-only validation and fails when it would change files. Run these commands after restore:

```powershell
dotnet format whitespace @PROJECT_NAME@.sln --no-restore --verify-no-changes
dotnet format style @PROJECT_NAME@.sln --no-restore --severity warn --verify-no-changes
```

## Development deployment

Development deployment is opt-in and is disabled by default. To copy the Mod into an existing game Modding folder, provide both deployment properties and quote the folder path:

```powershell
dotnet build @PROJECT_NAME@.sln -p:DeployToGame=true -p:DevFolder="C:\path\to\Blasphemous\Modding"
```

The target Modding folder must already exist. Files are copied only when deployment is enabled, a path is provided, and the target folder exists; otherwise the build can succeed without copying anything.

After the build, visually confirm that `plugins/@MACHINE_IDENTIFIER@.dll` and the expected resources are present under the target folder. A successful command does not by itself prove that deployment copied the current artifacts.

## Resources and Mod Package

Place resources for the Mod under `resources/`; every file under `resources/` is packaged with its path relative to that directory, including `.gitkeep` when `resources/` is otherwise empty.

A build of the main solution creates the Mod Package at `publish/@MACHINE_IDENTIFIER@.zip`. The package contains `plugins/@MACHINE_IDENTIFIER@.dll` as the Mod entry assembly and the resource files with their relative directory layout preserved. Automated Test Project outputs are not included. Dependency DLLs are not included.

CI releases the same `publish/@MACHINE_IDENTIFIER@.zip` package that the documented local build produces.

## Verification Mod

If `@PROJECT_NAME@.TestMod/@PROJECT_NAME@.TestMod.csproj` exists, `@PROJECT_NAME@.TestMod` is a separate `net35` project. Building the main solution also creates its archive at `@PROJECT_NAME@.TestMod/publish/@PROJECT_NAME@.TestMod.zip`. That archive contains both `plugins/@PROJECT_NAME@.TestMod.dll` and `plugins/@MACHINE_IDENTIFIER@.dll`.

To check in game, close Blasphemous, extract the Verification Mod archive into the game Modding folder, start the game, and look for `STARTUP_READY` in the BepInEx output. This startup check is manual in-game verification; the Automated Test Project does not prove that the game loads, links, or runs either plugin.

No Verification Mod directory is expected when that project file is absent.

## CI and releases

Validation is defined by the local [Build workflow](.github/workflows/build.yml), and tag handling is defined by the [Release workflow](.github/workflows/release.yml).

Validation runs on Windows with .NET 10 for pull requests targeting `main` and pushes to `main`. It restores the solution, builds in Release with game deployment disabled, runs tests, performs the read-only formatting verification above, and enforces CRLF line endings for tracked C# files.

An eligible SemVer tag, with or without a leading `v`, must point to a commit reachable from remote `main`. From a local `main` branch containing the target commit, publish that branch first, create the tag, and push the tag:

```powershell
git push origin main
git tag 1.2.3
git push origin 1.2.3
```

An eligible tag creates a draft release. If that tag already has a draft, the workflow replaces the asset in an existing draft. An already published release is refused. The draft contains only the main Mod Package. The optional NuGet and Discord integrations emit a warning and skip when their configuration is missing.
