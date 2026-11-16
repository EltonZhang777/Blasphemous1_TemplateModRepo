# @PROJECT_NAME@

This repository is a Blasphemous 1 Mod generated from the official template baseline.

## Repository boundary

- `@PROJECT_NAME@.csproj` is the `net35` Mod entry assembly.
- `@PROJECT_NAME@.Tests` is the adjacent `net48` xUnit project and must stay non-packable.
- `resources/` contains the Mod resources copied into the Mod package.
- `PackageMod.targets` owns packaging and opt-in development deployment.
- Do not add test projects or test assemblies to the Mod package.

## Local verification

```powershell
dotnet restore @PROJECT_NAME@.sln
dotnet build @PROJECT_NAME@.sln --no-restore
dotnet test @PROJECT_NAME@.sln --no-build
.\dotnet_format.bat @PROJECT_NAME@.sln
```

Development deployment requires `-p:DeployToGame=true` and a valid `-p:DevFolder=...`.

## Agent skills

See `docs/agents/domain.md`, `docs/agents/issue-tracker.md`, and `docs/agents/triage-labels.md`.
