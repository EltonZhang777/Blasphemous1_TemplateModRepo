# Blasphemous1_TemplateModRepo

A non-vendored repository generator for Blasphemous 1 Mod development.

## Status

The product is specified in [Issue #1](https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo/issues/1).

## Setup

Install the exact official template baseline:

```powershell
dotnet new install Blasphemous.Modding.Templates::1.4.1
```

Generate a Mod repository with the wrapper:

```powershell
python tools/new_blas1mod.py `
  --name Example `
  --title "Example Mod" `
  --author "Example Author" `
  --output C:\path\to\Blasphemous.Example
```

The wrapper verifies the exact Official Template Baseline, applies the Overlay,
and creates the output only after generation and validation succeed. It does
not install or update templates and refuses an existing output path.

Add `--with-test-mod` to generate the opt-in Verification Mod:

```powershell
python tools/new_blas1mod.py `
  --name Example `
  --title "Example Mod" `
  --author "Example Author" `
  --output C:\path\to\Blasphemous.Example `
  --with-test-mod
```

The Verification Mod is a separate `net35` project. Its ZIP contains both
assemblies under `plugins/`; it remains outside the main Mod's release ZIP and
NuGet package. `--game-version` defaults to `4.0.67` and propagates to both
projects.

Generated repositories validate pull requests and `main` pushes on Windows with
.NET 10. A SemVer tag reachable from `main` creates a draft release containing
only the main Mod ZIP. If configured, the Mod package is published to NuGet
through trusted publishing; missing credentials warn and skip only that
external action.

## Standalone verification Mod template

Build and install the package from this template repository:

```powershell
dotnet pack .\Templates\Blasphemous1.ModTest.Templates\Blasphemous1.ModTest.Templates.csproj --configuration Release
dotnet new install .\Templates\Blasphemous1.ModTest.Templates\bin\Release\Blasphemous1.ModTest.Templates.0.1.0.nupkg
```

Run the template from the existing Mod or class-library repository:

```powershell
Set-Location C:\path\to\existing-repo
$targetProject = 'C:\path\to\target\Target.csproj'
dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  -o .\Blasphemous.Example.TestMod `
  -ti "Example Mod Test" `
  -au "Example Author" `
  -ta $targetProject

dotnet sln add .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
```

`-ta` is optional. The package is `Blasphemous1.ModTest.Templates`, the short
name is `blasmodtest`, and the current package version is `0.1.0`. The
generated project does not modify a solution; add it manually. See the
[template README](Templates/Blasphemous1.ModTest.Templates/README.md) for
target-path behavior.

## Tests

```powershell
python -m unittest discover -s tests -v
```

On a normal Windows maintainer account, dotnet-backed template tests skip
before the first `dotnet` invocation. `DOTNET_CLI_HOME` isolates template-engine
state, but it is not a Windows-user isolation boundary. Run those tests only in
a Disposable Test Context: an ephemeral CI runner, Windows Sandbox, or another
disposable VM. Set `BLAS1_DISPOSABLE_TEST_CONTEXT=1` only inside that context.

The test harness captures raw User and Machine `Path` values, reports known
repository test-hive entries before execution, and allows disposable-context
changes only when they append inside the declared Test Hive. It never repairs,
normalizes, or deletes persistent PATH entries.

## Documentation

- Domain vocabulary: [GLOSSARY.md](GLOSSARY.md)
- Architecture decisions: [docs/adr](docs/adr)
- Agent workflow: [AGENTS.md](AGENTS.md)
