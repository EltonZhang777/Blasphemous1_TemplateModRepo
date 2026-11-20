# @PROJECT_NAME@

This repository is a Blasphemous 1 Mod. This file owns agent boundaries, and [README.md](README.md) is the single authority for complete commands and workflow conditions.

## Repository boundary

- `@PROJECT_NAME@.csproj` is the `net35` Mod entry assembly.
- `@PROJECT_NAME@.Tests` is the adjacent `net48` xUnit project and must stay non-packable.
- `resources/` contains the files placed in the Mod Package.
- [PackageMod.targets](PackageMod.targets) owns package construction.
- Change packaging, release workflows, or CI triggers only when the task explicitly includes that scope.
- Automated Test Project output and dependency DLLs must not enter the Mod Package.

## Mandatory constraints

- Game deployment is opt-in through `DeployToGame`. Enable it only when the user explicitly requests deployment to a valid existing game destination, and use the README command.
- Follow the README for restore, build, test, formatting, deployment, packaging, release, and Verification Mod work before claiming a check passed.
- Keep local process, environment, and path changes out of repository files unless the task requires them.

## Local context

- An optional untracked `AGENTS.local.md` may add checkout-specific notes. It is not required and may be absent.
- Read [domain routing](docs/agents/domain.md), [issue operations](docs/agents/issue-tracker.md), and [triage labels](docs/agents/triage-labels.md) when those branches apply.
