# Repository Maintenance

This tracked file is the authoritative repository guidance for maintainers and
coding agents. The root README is the user entry page.

## Scope and local supplements

Change the generator, templates, workflows, release behavior, or game
deployment only when the active issue explicitly includes that scope.

An optional untracked `AGENTS.local.md` may supplement this file for one
checkout. If it exists, read it after this file; this tracked file remains
authoritative on conflict. The local file is not required. Do not link to it,
create it, overwrite it, or clean it.

## Documentation ownership

- The root README contains only the project introduction, clone path,
  prerequisites, links to the creation and migration paths, contribution entry,
  and license.
- [Create a Mod repository](docs/create-mod-repository.md) owns the creation
  journey.
- [Migrate a Mod repository](docs/migrate-mod-repository.md) owns the in-place
  migration journey.
- This file owns maintainer and agent rules.
- [GLOSSARY.md](GLOSSARY.md) owns domain vocabulary, and
  [docs/adr/](docs/adr/) owns architecture decisions.
- [docs/agents/](docs/agents/) owns issue, triage, and domain workflow details.

## Language

Write repository prose in English. Report any residual language mixture. Use
Simplified Chinese in conversation unless the user requests another language.

## Issue and domain workflow

- Issues and specifications live in GitHub Issues; use `gh` as described in
  [docs/agents/issue-tracker.md](docs/agents/issue-tracker.md).
- Use the five labels in
  [docs/agents/triage-labels.md](docs/agents/triage-labels.md).
- Before exploring code, read [GLOSSARY.md](GLOSSARY.md) and the relevant files
  under [docs/adr/](docs/adr/). Follow the routing in
  [docs/agents/domain.md](docs/agents/domain.md).

## Maintainer checks

Run the repository tests from the root:

```powershell
python -m unittest discover -s tests -v
```

The dotnet-backed tests skip on a normal Windows maintainer account before the
first `dotnet` invocation. Run them only in a Disposable Test Context: an
ephemeral CI runner, Windows Sandbox, or another disposable VM. Set
`BLAS1_DISPOSABLE_TEST_CONTEXT=1` only inside that context.

The test harness captures raw User and Machine `Path` values and permits
disposable-context changes only when they append inside the declared Test Hive.
It never repairs, normalizes, or deletes persistent PATH entries.

Generated repositories keep game deployment opt-in: `DeployToGame` must remain
empty or `false` unless explicitly enabled with a valid `DevFolder`. Default
builds and tests must not touch a game profile.

## Test Template Package

Build and install the package from this repository:

```powershell
dotnet pack .\Templates\Blasphemous1.ModTest.Templates\Blasphemous1.ModTest.Templates.csproj --configuration Release
$package = Get-ChildItem .\Templates\Blasphemous1.ModTest.Templates\bin\Release -Filter *.nupkg |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1
dotnet new install $package.FullName
```

Generate the optional Verification Mod in an existing repository, then add its
project to the solution manually:

```powershell
dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  -o .\Blasphemous.Example.TestMod `
  -ti "Example Mod Test" `
  -au "Example Author"
dotnet sln add .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
```

See the
[Test Template Package README](Templates/Blasphemous1.ModTest.Templates/README.md)
for target-project behavior.
