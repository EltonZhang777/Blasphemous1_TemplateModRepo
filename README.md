# Blasphemous1_TemplateModRepo

A non-vendored repository generator for Blasphemous 1 Mod development.

## Status

The product is specified in [Issue #1](https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo/issues/1). Implementation has not started.

## Planned delivery

- A Generator Command that wraps the official `blas1mod` template, pins `Blasphemous.Modding.Templates` `1.4.1`, and applies repository-owned tooling.
- `TemplateRepo/` as the Overlay Root containing automated tests, agent documentation, project CI, and development configuration.
- An opt-in Verification Mod for Mods and libraries that expose public APIs to other Mods.
- A standalone `blasModTest` dotnet template, `Blasphemous1.ModTest.Templates`, for existing repositories.

The official template remains the canonical source of the base Mod project. This repository does not distribute a fork or cloneable snapshot of it.

## Documentation

- Domain vocabulary: [GLOSSARY.md](GLOSSARY.md)
- Architecture decisions: [docs/adr](docs/adr)
- Agent workflow: [AGENTS.md](AGENTS.md)
