# Blasphemous1_TemplateModRepo

A non-vendored repository generator for Blasphemous 1 Mod development.

## Status

The product is specified in [Issue #1](https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo/issues/1).

## Planned delivery

- A Generator Command that wraps the official `blas1mod` template, pins `Blasphemous.Modding.Templates` `1.4.1`, and applies repository-owned tooling.
- `TemplateRepo/` as the Overlay Root containing automated tests, agent documentation, project CI, and development configuration.
- An opt-in Verification Mod for Mods and libraries that expose public APIs to other Mods.
- A standalone `blasModTest` dotnet template, `Blasphemous1.ModTest.Templates`, for existing repositories.

The official template remains the canonical source of the base Mod project. This repository does not distribute a fork or cloneable snapshot of it.

## Standalone verification Mod template

The package is built from `Templates/Blasphemous1.ModTest.Templates`:

```powershell
dotnet pack .\Templates\Blasphemous1.ModTest.Templates\Blasphemous1.ModTest.Templates.csproj
dotnet new install .\Templates\Blasphemous1.ModTest.Templates\bin\Release\Blasphemous1.ModTest.Templates.0.1.0.nupkg

dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  --title "Example Mod Test" `
  -au "Example Author" `
  --targetProject ..\Blasphemous.Example\Blasphemous.Example.csproj

dotnet sln add .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
```

`--targetProject` is optional. The generated project does not modify a solution; add it manually. See the [template README](Templates/Blasphemous1.ModTest.Templates/README.md) for package output and target-path behavior.

## Documentation

- Domain vocabulary: [GLOSSARY.md](GLOSSARY.md)
- Architecture decisions: [docs/adr](docs/adr)
- Agent workflow: [AGENTS.md](AGENTS.md)
