# Create a Blasphemous 1 Mod Repository

This guide takes you from a checkout of this repository to a generated and verified Blasphemous 1 Mod repository. The Generator Command creates the output only after generation and validation succeed.

## Prerequisites

Before continuing, complete the [common host prerequisites](../README.md#prerequisites) and [clone this repository](../README.md#clone-the-repository).

## Install the Official Template Baseline

**Consumer safety:** If you use a custom .NET CLI home (`DOTNET_CLI_HOME`), reuse one fixed path between runs or use a disposable context. Do not create a new home directory per invocation. This is a safety precaution for this creation workflow, not a guarantee about all .NET CLI behavior.

Install the exact Official Template Baseline:

```powershell
dotnet new install Blasphemous.Modding.Templates::1.4.1
```

Verify that the installed version is `1.4.1`:

```powershell
dotnet new uninstall |
  Select-String -Pattern "Blasphemous.Modding.Templates" -Context 0,3
```

Expected output includes `Blasphemous.Modding.Templates` and `Version: 1.4.1`. The Generator Command requires exactly one installed version of this package; multiple installed versions cannot be used. The Generator Command verifies this installation; it does not install or update templates for you.

## Create the Mod Repository

From the repository root, run:

```powershell
python tools/new_blas1mod.py `
  --name Example `
  --title "Example Mod" `
  --author "Example Author" `
  --output C:\path\to\Blasphemous.Example `
  --game-version 4.0.67
```

The parameter constraints are:

- `--name` is the Machine Identifier. It must contain 2-64 ASCII letters or digits, start with an uppercase letter, and contain no separators.
- `--title` is the Display Title, between 1 and 80 characters after trimming.
- `--author` is the author name, between 1 and 80 characters after trimming.
- `--output` is a new directory path.
- `--game-version`, which defaults to `4.0.67`.

Do not enter a display title such as `My Mod` in `--name`. The Machine Identifier derives `Blasphemous.Example`, `Blasphemous.Example.Tests`, and the plugin assembly name `Example`. The Display Title and Author are metadata.

The output path must not already exist. If it exists, the command refuses the request and leaves the existing path untouched. If the parent directory does not exist, the Generator Command creates it.

The command writes to a temporary staging directory next to the output. On success, it prints:

```text
Created C:\path\to\Blasphemous.Example
```

Only then is the output a completed generated directory.

If generation fails after staging starts, the requested output is not created. The command preserves the staging directory and prints a path similar to:

```text
staging preserved at C:\path\to\.Blasphemous.Example-abcd1234.failed
```

Do not treat the preserved staging directory as a completed repository. See [Recover from Common Failures](#recover-from-common-failures).

## Expected Result

For the example identity, the generated directory contains:

```text
Blasphemous.Example/
|-- Blasphemous.Example.csproj
|-- Blasphemous.Example.sln
|-- Example.cs
|-- Main.cs
|-- ModInfo.cs
|-- PackageMod.targets
|-- Blasphemous.Example.Tests/
|   |-- Blasphemous.Example.Tests.csproj
|   `-- ModMetadataTests.cs
|-- resources/
|-- README.md
|-- AGENTS.md
|-- .editorconfig
|-- .gitattributes
|-- .gitignore
|-- .worktreeinclude
|-- NuGet.Config
|-- dotnet_format.bat
|-- .config/wt.toml
|-- docs/agents/
|-- scripts/check-crlf.ps1
`-- .github/workflows/
    |-- build.yml
    |-- release.yml
    `-- discord.yml
```

The main project targets `net35`. The adjacent Automated Test Project targets `net48`, references the real Mod project, and is not packable. Game deployment is disabled by default; a build creates the Mod Package without requiring a game installation. `Example.cs` contains the generated Mod class, and `Main.cs` contains the startup entry point.

## Verify and Record Creation Evidence

Record the installed baseline version, generated path, command outputs, and package entries as creation evidence. Change to the generated directory and restore, build, and test it:

```powershell
Set-Location C:\path\to\Blasphemous.Example
dotnet restore .\Blasphemous.Example.sln -p:Configuration=Release
dotnet build .\Blasphemous.Example.sln --configuration Release --no-restore -p:Version=1.2.3
dotnet test .\Blasphemous.Example.sln --configuration Release --no-build
```

Expected outcomes:

- Restore completes without a NuGet or target-framework error.
- Build completes with `0 Error(s)`.
- Tests pass, including the generated metadata test.

Verify formatting without modifying the generated files:

```powershell
dotnet format whitespace .\Blasphemous.Example.sln --no-restore --verify-no-changes
dotnet format style .\Blasphemous.Example.sln --no-restore --severity warn --verify-no-changes
```

Both commands must exit with code `0`. A non-zero result means formatting verification failed; see [Recover from Common Failures](#recover-from-common-failures).

Create and inspect the main Mod Package:

```powershell
dotnet pack .\Blasphemous.Example.csproj `
  --configuration Release `
  --no-build `
  --output .\release-nuget `
  -p:PackageVersion=1.2.3

Add-Type -AssemblyName System.IO.Compression.FileSystem
$package = [System.IO.Compression.ZipFile]::OpenRead(
  (Resolve-Path .\publish\Example.zip)
)
$package.Entries.FullName
$package.Dispose()
```

Expected outcomes:

- `release-nuget\Blasphemous.Example.1.2.3.nupkg` exists.
- `publish\Example.zip` exists.
- The ZIP contains `plugins/Example.dll`.
- Any files under `resources/` are included in the package.
- Automated test files and assemblies are absent from the Mod Package.

The package name uses the Machine Identifier; it does not use the Display Title.

## Optional Verification Mod

Add `--with-test-mod` to the original creation command when you need an in-game Verification Mod. Choose this option before generation because the Generator Command refuses an existing output path.

The Verification Mod is a separate `net35` project:

```text
Blasphemous.Example.TestMod/
`-- Blasphemous.Example.TestMod.csproj
```

It is added to the generated solution and remains separate from the main Mod Package and NuGet package. A solution build creates:

```text
Blasphemous.Example.TestMod\publish\Blasphemous.Example.TestMod.zip
```

That ZIP contains both `plugins/Blasphemous.Example.TestMod.dll` and the target Mod assembly, `plugins/Example.dll`. The main `publish\Example.zip` still contains only the main Mod and its resources.

In-game loading is optional and is not part of this creation check. The generated Automated Test Project remains the repeatable local verification path.

## Recover from Common Failures

| Symptom | Cause | Recovery |
| --- | --- | --- |
| `dotnet was not found on PATH` | .NET SDK 10 is missing, or the current terminal predates installation. | Install .NET SDK 10, open a new PowerShell window, and repeat the validation in [Prerequisites](../README.md#prerequisites). |
| Python cannot be found | Python 3.9 or later is missing, or the current terminal predates installation. | Install Python 3.9 or later, open a new PowerShell window, and repeat the validation in [Prerequisites](../README.md#prerequisites). |
| `Blasphemous.Modding.Templates 1.4.1 is required` | The exact package is missing or another version is installed. | Run `dotnet new uninstall Blasphemous.Modding.Templates`, then `dotnet new install Blasphemous.Modding.Templates::1.4.1`, and rerun the Generator Command. |
| Machine Identifier validation error | The value has separators, is too short or too long, starts with a lowercase letter/digit, collides with a reserved C# or Windows name, or reuses `Main`, `ModInfo`, `ModTemplate`, or `TemplateMod`. | Use a value such as `ExampleMod`, without spaces or punctuation, and rerun with an output path that does not exist. |
| Display Title or Author validation error | The value is empty after trimming, exceeds 80 characters, or contains control characters, line breaks, or an unsupported reserved token. | Correct the text and rerun the Generator Command. |
| `Output path already exists` | The final directory is present, even if it is empty. | Choose a new output path. The Generator Command does not overwrite the existing path. |
| `Output parent is not a directory` | A file occupies a path component that must be a directory. | Choose an output below a valid directory. |
| `staging preserved at ...failed` | Generation or validation failed after staging began. | Read the preceding error, inspect the preserved staging directory, fix that cause, and rerun. Do not rename staging to the final output. |
| `dotnet restore` fails | NuGet access, feed configuration, or package resolution failed. | Rerun with `dotnet restore .\Blasphemous.Example.sln --verbosity normal`, read the first error, check network and `dotnet nuget list source`, then retry. |
| Build succeeds but the package is missing | The build did not complete the package target, or you are checking the wrong path. | Confirm the Machine Identifier and inspect `publish\Example.zip` after a successful build. |
| Format verification reports changes | The generated files do not match the checked-in formatting rules. | Run `.\dotnet_format.bat .\Blasphemous.Example.sln`, then repeat both format verification commands. |

Keep the first failing command and its full output when asking for help.

## Stop Before Git

This guide stops at a validated generated directory. Do not run `git init`, `git add`, `git commit`, `git remote add`, or `git push` as part of creation. Repository initialization, remotes, commits, CI configuration, and releases are separate decisions outside this guide.

## Completion Checklist

The creation path is complete only when all of these checks pass:

- [ ] The common host prerequisites in the root README are satisfied.
- [ ] The installed Official Template Baseline is exactly `1.4.1`.
- [ ] The Generator Command prints `Created ...` for a new output path.
- [ ] The expected generated project, test, resource, documentation, and workflow files exist.
- [ ] Restore, Release build, and Automated Test Project execution succeed.
- [ ] Both format verification commands succeed.
- [ ] The Mod Package contains `plugins/Example.dll` and the intended resources, without test assemblies.
- [ ] If selected, the Verification Mod has its own project and package, and that package is outside the main Mod Package.
- [ ] No Git initialization, commit, remote creation, or push was performed after generation.

If any check fails, the generated repository is incomplete. Preserve the failing output and staging evidence, then use [Recover from Common Failures](#recover-from-common-failures).
