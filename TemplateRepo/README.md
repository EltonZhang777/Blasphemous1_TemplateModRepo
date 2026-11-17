# @TITLE@

`@TITLE@` is a Blasphemous 1 Mod built with ModdingAPI. The root project contains the Mod, the adjacent Automated Test Project verifies its metadata without starting the game, and an optional Verification Mod can be generated for manual in-game checks.

## Requirements

### Development prerequisites

- Windows
- .NET SDK 10

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

The formatting helper is separate from validation. It changes tracked source files:

```powershell
.\dotnet_format.bat
```

Do not use it as a read-only formatting check.

## Development deployment

Development deployment is opt-in. To copy the Mod into an existing game Modding folder, provide both deployment properties and quote the folder path:

```powershell
dotnet build @PROJECT_NAME@.sln -p:DeployToGame=true -p:DevFolder="C:\path\to\Blasphemous\Modding"
```

The target Modding folder must already exist. Files are copied only when deployment is enabled, a path is provided, and the target folder exists; otherwise the build can succeed without copying anything.

After the build, visually confirm that `plugins/@MACHINE_IDENTIFIER@.dll` and the expected resources are present under the target folder. A successful command does not by itself prove that deployment copied the current artifacts.

## Resources and Mod Package

Place resources for the Mod under `resources/`. A build of the main solution creates `publish/@MACHINE_IDENTIFIER@.zip`.

The package contains `plugins/@MACHINE_IDENTIFIER@.dll` as the Mod entry assembly and tracked resources with their relative directory layout preserved. Automated Test Project outputs are not included. Dependency DLLs are not included.

CI releases the same `publish/@MACHINE_IDENTIFIER@.zip` package that the documented local build produces.

## Verification Mod

When generated with the optional Verification Mod (`--with-test-mod`), `@PROJECT_NAME@.TestMod` is a separate `net35` project. Building the main solution also creates its archive at `@PROJECT_NAME@.TestMod/publish/@PROJECT_NAME@.TestMod.zip`. That archive contains both `plugins/@PROJECT_NAME@.TestMod.dll` and `plugins/@MACHINE_IDENTIFIER@.dll`.

To check in game, close Blasphemous, extract the Verification Mod archive into the game Modding folder, start the game, and look for `STARTUP_READY` in the BepInEx output. This startup check is manual in-game verification; the Automated Test Project does not prove that the game loads, links, or runs either plugin.

## CI and releases

Validation runs on Windows with .NET 10 for pull requests targeting `main` and pushes to `main`. It restores the solution, builds in Release, runs tests, checks formatting, and enforces CRLF line endings for tracked C# files.

An eligible SemVer tag, with or without a leading `v`, creates or updates a draft release when its commit is reachable from `main`. The draft contains only the main Mod Package. The optional NuGet and Discord integrations warn and skip when their configuration is missing.
