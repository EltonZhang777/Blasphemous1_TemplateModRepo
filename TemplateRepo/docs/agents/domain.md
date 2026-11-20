# Domain Guidance

This generated repository contains one Blasphemous 1 Mod. `README.md` owns author workflows, and `AGENTS.md` owns agent boundaries.

## Route by repository layout

- `@PROJECT_NAME@.csproj`, `Main.cs`, and `ModInfo.cs` define the Mod entry and identity.
- `@PROJECT_NAME@.Tests` contains the Automated Test Project and does not require the game.
- `resources/` contains Mod resources packaged with the main plugin.
- `PackageMod.targets` defines package construction in this layout.
- `docs/agents/` owns issue operations and triage-label definitions.

## Use repository vocabulary

Use the names already defined by the README, root project, ModInfo, tests, and source code. Keep a term consistent across code and documentation, and introduce a new local definition beside the behavior that needs it.

## Keep goals explicit

Start from the requested Mod behavior and identify the project, test, resource, packaging, or workflow files it actually changes. Keep each change within that scope.
