# Migrate a Blasphemous 1 Mod Repository in Place

Use this guide for an existing supported Blasphemous 1 Mod repository. The migration preserves Mod Identity, public contracts, and the existing layout by default. It converges tests, packaging, deployment, configuration, and CI only where a required check needs the change.

The representative shape is a repository such as `Blasphemous.ForgivingSpikes`: a `net35` project in a subdirectory of a solution, no adjacent Automated Test Project, an inline build and deployment target, and CI that predates the generated baseline. Treat that repository as evidence only. Re-run every inventory step against the repository being migrated, and do not modify the representative repository.

## Supported Inputs

The migration path supports an ordinary Windows .NET repository that:

- Contains a `net35` Blasphemous 1 BepInEx Mod or compatible class library.
- Contains a project file and a solution file.
- Builds against supported Blasphemous 1 and ModdingAPI package references.
- Can be restored, built, tested, packaged, and validated on Windows.

Use Windows with:

- A working .NET SDK 10 installation.
- NuGet access to the feeds recorded in the repository.
- Python 3.9 or later when generating a clean reference repository.
- Git for the Git recovery path; non-Git repositories do not require it.

Verify the host:

```powershell
[System.Environment]::OSVersion.Version
dotnet --version
python --version
```

Expected outcomes are Windows, a `dotnet --version` value starting with `10.`, and Python 3.9 or later when needed. For a Git repository, also verify `git --version`.

Inspect the repository inputs:

```powershell
rg --files --hidden -g "*.sln" -g "*.csproj" -g "*.props" -g "*.targets" `
  -g "NuGet.Config" -g "Directory.*" -g ".github/workflows/*" `
  -g "!bin/**" -g "!obj/**" -g "!publish/**"
```

Expected output includes at least one solution and the Mod or class-library project. A nested project is supported.

Use this path only for an ordinary repository of that shape. When the repository uses a custom or unverifiable build system, is not a Windows .NET `net35` repository, is missing a project or solution, or cannot be restored through the recorded feeds, continue with the read-only inventory and prepare a verified external backup outside the target and any containing worktree. Do not edit the repository. Then record the result as `UNSUPPORTED FOR THIS MIGRATION RUN`; do not promise a migration.

The creation path is different. Do not point the Generator Command at an existing repository: it requires a new output path. A generated repository may be created separately as a clean reference for required files and commands using [Create a new Mod repository](create-mod-repository.md).

## Record the Starting State and Prepare Recovery

Recovery is a prerequisite. Do not edit the target repository until one of the following paths is complete and recorded. Replace every `<...>` placeholder before running a command.

### Git repository

Record the current branch, working-tree state, and exact starting SHA:

```powershell
git branch --show-current
git status --short
git rev-parse HEAD
```

Expected outcome: a non-empty branch name and a 40-character SHA. The working tree must be clean before migration edits begin. If it is not clean, stop and ask the repository owner to preserve or commit those changes. Do not use `git reset`, `git reset --hard`, `git clean`, or destructive checkout commands to make the repository appear clean.

Before editing, copy any ignored or untracked file the migration may touch to a verified external backup outside the repository and any containing worktree. At minimum, protect `AGENTS.local.md`, local `NuGet.Config`, deployment settings, and generated local files. A branch and SHA do not restore ignored or untracked files. Record each copied relative path and SHA-256 hash, then verify the backup before editing.

After the owner confirms the starting state, create a dedicated migration branch from that exact SHA:

```powershell
git switch -c migrate/template-baseline '<recorded-start-sha>'
```

Expected outcome: the new branch points at the recorded SHA and `git status --short` is empty. Use phase-sized commits for inventory, recovery, tests/package, CI, and validation. Commit, push, and pull request actions remain separately approval-gated.

The ordered Git rollback procedure is in [Migration Recovery Reference](migrate-mod-repository-recovery.md#rollback).

### Non-Git repository

Create a complete backup outside both the target repository and any containing worktree. Use a new directory that does not already exist:

```powershell
$repo = (Resolve-Path '<recorded-repository-root>').Path
$containingRoot = '<recorded-containing-worktree-root-or-empty>'
$backupRoot = [IO.Path]::GetFullPath(
  'D:\Blasphemous\MigrationBackups\Example-20261117'
)
$backup = Join-Path $backupRoot 'repository'

function Test-IsWithin([string] $candidate, [string] $parent) {
  $candidateFull = [IO.Path]::GetFullPath($candidate)
  $parentFull = [IO.Path]::GetFullPath($parent)
  if (-not $parentFull.EndsWith("\")) {
    $parentFull += "\"
  }
  return $candidateFull.Equals(
    $parentFull.TrimEnd("\"),
    [StringComparison]::OrdinalIgnoreCase
  ) -or $candidateFull.StartsWith(
    $parentFull,
    [StringComparison]::OrdinalIgnoreCase
  )
}

function Assert-NoReparsePointAncestor([string] $candidate) {
  $path = [IO.Path]::GetFullPath($candidate)
  while ($path) {
    if (Test-Path -LiteralPath $path) {
      $item = Get-Item -LiteralPath $path -Force -ErrorAction Stop
      if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Path traverses a reparse point: $path"
      }
    }
    $parent = [IO.Path]::GetDirectoryName($path)
    if (-not $parent -or $parent -eq $path) {
      break
    }
    $path = $parent
  }
}

Assert-NoReparsePointAncestor $repo
if ($containingRoot) {
  Assert-NoReparsePointAncestor $containingRoot
}
foreach ($candidate in @($backupRoot, $backup)) {
  Assert-NoReparsePointAncestor $candidate
  if ((Test-IsWithin $candidate $repo) -or (Test-IsWithin $repo $candidate)) {
    throw "The backup and target repository must not contain each other: $candidate"
  }
  if (
    $containingRoot -and
    ((Test-IsWithin $candidate $containingRoot) -or
      (Test-IsWithin $containingRoot $candidate))
  ) {
    throw "The backup must not overlap the containing worktree: $candidate"
  }
}
if ((Test-Path -LiteralPath $backupRoot) -or (Test-Path -LiteralPath $backup)) {
  throw "Choose a new backup path: $backupRoot"
}
$links = @(
  Get-ChildItem -LiteralPath $repo -Recurse -Force |
    Where-Object {
      ($_.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0
    }
)
if ($links.Count -ne 0) {
  throw "Resolve repository reparse points before backup: $($links.FullName)"
}
New-Item -ItemType Directory -Path $backupRoot | Out-Null
robocopy $repo $backup /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ
if ($LASTEXITCODE -gt 7) {
  throw "Backup copy failed with exit code $LASTEXITCODE"
}
```

These checks walk every existing ancestor of the target, containing root, and backup paths, then compare normalized paths. They stop on a junction or symbolic link even when the final backup directory does not exist yet. The backup also stops if the source repository contains a reparse point; resolve those links manually instead of letting the copy follow them.

Verify that the source and backup contain the same relative file paths and SHA-256 hashes:

```powershell
function Get-RepositoryManifest([string] $root) {
  @(
    Get-ChildItem -LiteralPath $root -Recurse -File -Force |
      ForEach-Object {
        [pscustomobject]@{
          RelativePath = $_.FullName.Substring($root.Length).TrimStart("\")
          Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_.FullName).Hash
        }
      } |
      Sort-Object RelativePath
  )
}

$sourceManifest = Get-RepositoryManifest $repo
$backupManifest = Get-RepositoryManifest $backup
$differences = Compare-Object $sourceManifest $backupManifest `
  -Property RelativePath, Hash

if ($sourceManifest.Count -ne $backupManifest.Count -or $differences) {
  throw "Backup verification failed."
}

$manifestPath = Join-Path $backupRoot 'repository-manifest.json'
ConvertTo-Json -InputObject @($backupManifest) -Depth 3 |
  Set-Content -LiteralPath $manifestPath -Encoding UTF8
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
  throw "The reference manifest was not written."
}
```

Expected outcome: both manifests have the same count and `Compare-Object` returns no differences, and `repository-manifest.json` exists under `$backupRoot`. Keep that file with the backup; it is the reference for restore verification. If the copy, verification, or manifest write fails, stop before the first edit.

A backup is not proof that restore works. The approved procedure is in [Migration Recovery Reference](migrate-mod-repository-recovery.md#rollback); do not claim it was tested unless it was actually run.

## Inventory Before Editing

Inventory the repository before changing files. Record absolute paths, exact versions, and command output where relevant.

Useful read-only commands include:

```powershell
rg --files --hidden -g "*.sln" -g "*.csproj" -g "*.props" -g "*.targets" `
  -g "NuGet.Config" -g "Directory.*" -g "!bin/**" -g "!obj/**"
rg -n "<TargetFramework>|<AssemblyName>|<RootNamespace>|<TargetName>|<PackageId>|<Version>|<Product>|<Title>|<Company>|<PackageReference|<Target |<Import " `
  -g "*.csproj" -g "*.targets" -g "*.props"
Get-ChildItem -LiteralPath .github\workflows -File -Force -ErrorAction SilentlyContinue |
  Select-Object Name, FullName
rg --hidden -n "on:|push:|pull_request:|tags:|permissions:|runs-on:|dotnet-version|secrets\.[A-Za-z_]+|NUGET|WEBHOOK" `
  .github -g "*.yml" -g "*.yaml"
rg -n "^\s*(public|protected)\s" -g "*.cs"
```

The declaration search is a starting point for the public-contract inventory, not proof of stability; it does not capture implicit interface members, multiline signatures, or enum values.

When the repository uses Git, also record:

```powershell
git ls-files
git status --ignored --short --untracked-files=all
```

Use the same file-level `--untracked-files=all` form during rollback so nested ignored files compare consistently.

For a non-Git repository, use `Get-ChildItem -Recurse -Force` and the verified backup manifest as the inventory of present and ignored files.

Complete this inventory:

| Area | Record |
| --- | --- |
| Recovery | Git branch and exact start SHA, or verified backup path |
| Solution and projects | Solution path, project paths, nesting, target frameworks, build configurations |
| Mod Identity | Display Title, Author, Machine Identifier, `TargetName`, assembly name, root namespace, project/solution/test names |
| Module boundaries | Project or assembly responsibilities, dependencies between modules, shared libraries, and externally consumed entry points |
| Public contract | Public namespaces, types, methods, events, enum values, implicit interface members, configuration keys, `BepInDependency` IDs |
| Package identity | Product/Title, Authors/Company, package ID, version, repository URL, package references |
| Resources | Resource roots, expected package paths, data DLLs or other shipped files |
| Build and deployment | Custom targets, export locations, `DevFolder`, data-copy targets, opt-in flags |
| Automated tests | Existing test projects, assembly names, target frameworks, test frameworks, generated tests |
| CI and release | Triggers, runner OS, SDK version, permissions, tags, release assets, publish steps, deployment targets |
| Secrets | Secret names and scopes only, such as `NUGET_API_KEY`, `WEBHOOK_URL`, or OIDC permissions; never values |
| Generated and local files | `bin`, `obj`, `publish`, `.vs`, generated sources, local config, `AGENTS.local.md`, ignored handoff files |

The inventory is complete only when every row is either recorded or explicitly marked not applicable. An unknown required build, test, package, deployment, or CI gate keeps the migration from proceeding.

## Preserve Mod Identity

Preserve these values unless a separate breaking-change decision explicitly approves a rename:

- Machine Identifier.
- Display Title and Author metadata.
- Plugin assembly and `TargetName`.
- Solution, project, test, and namespace names.
- Public types, members, configuration keys, and events.
- Package ID and other external package identity.
- `BepInDependency` IDs and the public API surface consumed by other Mods.

A rename is not a parity cleanup. Before changing any external contract, record the consumers, the impact, a migration note, and user approval for the breaking change. That decision is separate from this migration.

Expected outcome: the identity inventory before and after migration matches, or every difference links to a separately approved breaking-change decision.

## Preserve the Existing Layout

Keep the existing solution and project layout by default. In particular:

- Keep a project that lives in a subdirectory in that subdirectory.
- Keep solution-relative paths, resource roots, export locations, and build entry points.
- Keep intentional custom build steps, data DLL copies, package layouts, and deployment targets.

Generated-layout parity alone is not a reason to move or rename a project. For any proposed layout refactor, follow the [Structural Refactor Gate](#structural-refactor-gate).

Expected outcome: the pre-edit and post-migration layout inventories match, or the difference links to approved refactor evidence.

## Classify Template Differences

Classify every difference before applying it.

| Class | Meaning | Typical examples |
| --- | --- | --- |
| Required | A required local or CI gate cannot pass correctly without it. | Adjacent `net48` Automated Test Project, package target that emits the intended plugin/resources, opt-in deployment gate, Windows .NET 10 workflow, configuration needed by those gates. |
| Preserved | Intentional existing behavior that remains authoritative. | Mod Identity, public API, nested layout, custom data DLL packaging, release asset set, deployment paths, custom product README. |
| Optional | Useful cleanup that no required gate needs. | Cosmetic renames, layout flattening, optional Verification Mod, broad documentation rewrites, style-only edits. |

When a difference is unclear, preserve it and record the uncertainty. Do not turn an optional difference into required work without evidence.

## Apply Required Differences

Apply the Required set only after the initial inventory and phase-sized recovery point are recorded.

### Automated Test Project

Create or adapt an adjacent `net48` xUnit Automated Test Project that references the real `net35` Mod or class library. The project must not be packable and must not enter the Mod Package.

Use a clean generated repository as the file-shape reference when needed. Place the test project according to the preserved layout, normally adjacent to the existing project, and adjust its `ProjectReference` rather than moving the Mod project merely to match the generated root layout.

Add the project to the existing solution without discarding existing entries:

```powershell
dotnet sln '<solution-path>' add '<test-project-path>'
```

Expected outcome: `dotnet sln '<solution-path>' list` includes the existing Mod project and the new test project.

The default metadata test verifies assembly and public metadata boundaries. It does not prove every custom behavior. Add behavior tests only where their seams and expected outcomes are understood.

### Mod Package and Deployment

Use the generated package target or an equivalent existing target to produce a Mod Package containing:

- `plugins/<TargetName>.dll` for the main Mod entry assembly.
- The intended resource tree and any intentionally shipped data artifacts.
- No Automated Test Project or test assembly.

Do not copy an inline deployment target over custom behavior. Preserve intentional data-DLL staging, export paths, and deployment destinations, and make game deployment opt-in. A deployment requires an explicit `DeployToGame=true` and a valid `DevFolder`; the default build must still produce the package without touching the game directory.

### Configuration, Documentation, and Agents

Add or reconcile `.editorconfig`, `.gitattributes`, `.gitignore`, `NuGet.Config`, README, and agent documentation only when they enforce a required gate or preserve maintainer knowledge. Merge with intentional repository behavior instead of replacing product documentation wholesale.

The optional Verification Mod remains a separate `net35` project and package. It must not be merged into the main Mod Package or NuGet package. See the [Test Template Package README](../Templates/Blasphemous1.ModTest.Templates/README.md) when that optional path is selected.

## Structural Refactor Gate

A layout refactor is eligible only when a required build, Automated Test Project, package-content, opt-in deployment, or CI-path gate demonstrably cannot pass in the existing layout.

Before proposing a refactor, record:

- The exact command and full failing output.
- Why the in-place alternatives were attempted or are unavailable.
- The smallest move or rename that can satisfy the gate.
- Every external contract and consumer affected.
- The effect on package paths, deployment, CI, and rollback.
- The expected validation after the refactor.

Present that evidence and the smallest viable refactor. Wait for explicit user approval before moving or renaming the solution, project, or external contract. Do not make dependent migration edits while the decision is pending.

If the user declines, stop before dependent edits and record `BLOCKED — DECISION REQUIRED`. If the required refactor is infeasible, stop and record `UNSUPPORTED FOR THIS MIGRATION RUN`. Neither state is a completed migration.

## Reconcile CI and Release Semantics

Inventory the old workflow before replacing it. Record:

- `push`, pull-request, tag, and manual triggers.
- Runner operating system, SDK version, restore source, and caching.
- Workflow and job permissions.
- Tag format and reachability rules.
- Release names, draft/prerelease behavior, ZIP and NuGet assets, and upload behavior.
- Deployment and notification targets.
- Secret names and scopes. Never record secret values.

The representative repository can use a different workflow shape from the generated baseline, including a non-Windows runner, an older SDK, combined build/release logic, and release steps in a single file. These are evidence to reconcile, not files to overwrite blindly.

This phase is inventory only. Do not edit workflow or release files here. The separate [Apply Approved CI and Release Differences](#apply-approved-ci-and-release-differences) phase follows local verification and optional in-game smoke. The generated Windows .NET 10 workflows are a target contract only after the required local gates pass.

## Verify and Record Migration Evidence

Record the inventory paths, deployment-target inspection, command outputs, package entries, and any `NOT RUN` or `UNVERIFIED` state as migration evidence. Record the paths used by the local gates:

```powershell
$solution = '<recorded-solution>'
$mainProject = '<recorded-main-project>'
$testAssemblyNames = @(
  '<recorded-test-assembly-name>'
)
$packageTargetName = '<recorded-target-name>'
$zipPath = '<recorded-package-zip>'
$devFolder = '<recorded-dev-folder>'
```

Replace all placeholders with the paths recorded during inventory.

### Inspect Deployment Targets Before the First Build

Before the first build, inspect the project files and repository-owned targets for deployment operations:

```powershell
rg --no-ignore --hidden -n -i "<Copy\b|<WriteLinesToFile\b|<Move\b|<RemoveDir\b|<RemoveDirectory\b|<Exec\b|<Import\b|<UsingTask\b|DeployToGame|DevFolder" `
  -g "*.csproj" -g "*.props" -g "*.targets" `
  -g "*.ps1" -g "*.cmd" -g "*.bat" `
  -g "!.git/**" -g "!bin/**" -g "!obj/**"
```

Read every hit and record its target, trigger, source, destination, and condition. Follow every `<Import>` and `<UsingTask>` to the resolved target or task implementation. The search is a starting point, not proof by itself. Stop before any build if an operation that can copy, write, move, or remove a directory can bypass `DeployToGame=true`, a valid `DevFolder`, or the recorded destination, or if any import cannot be resolved. Do not run a normal build until inspection and the probe below show that game-affecting operations are opt-in.

After the inspection passes, make the first build a disposable probe build. Choose a unique path that does not exist yet, create it, verify the evaluated default is not true, explicitly disable deployment, and pass the probe as `DevFolder`:

```powershell
$probe = Join-Path ([IO.Path]::GetTempPath()) (
  "blasmod-deploy-probe-" + [guid]::NewGuid()
)
New-Item -ItemType Directory -Path $probe | Out-Null
dotnet restore $solution -p:Configuration=Release
if ($LASTEXITCODE -ne 0) {
  throw "Restore failed with exit code $LASTEXITCODE."
}
$deployProperty = @(
  dotnet msbuild $mainProject -p:Configuration=Release `
    -getProperty:DeployToGame
) -join "`n"
if ($LASTEXITCODE -ne 0) {
  throw "Could not evaluate DeployToGame."
}
$defaultDeployToGame = $deployProperty.Trim()
if ($defaultDeployToGame -and $defaultDeployToGame -ne 'false') {
  throw "Deployment is not opt-in: DeployToGame defaults to $defaultDeployToGame."
}
dotnet build $solution --configuration Release --no-restore --no-incremental `
  -p:Version=1.2.3 -p:DeployToGame=false -p:DevFolder="$probe"
if ($LASTEXITCODE -ne 0) {
  throw "The probe build failed with exit code $LASTEXITCODE."
}
$probeEntries = @(
  Get-ChildItem -LiteralPath $probe -Force -ErrorAction Stop
)
if ($probeEntries.Count -ne 0) {
  throw "The probe build wrote to DevFolder: $($probeEntries.FullName)"
}
```

Expected outcome: `DeployToGame` evaluates to empty or `false`, the probe build exits with code `0`, and the probe directory remains empty. The directory exists before the build, so a target that deploys merely because `DevFolder` exists is exposed. The rebuild forces the deployment target to run instead of being skipped as up to date. If the probe contains anything, stop; deployment is not opt-in.

Only after the probe exits with code `0` and remains empty, run the normal build and tests:

```powershell
dotnet build $solution --configuration Release --no-restore -p:Version=1.2.3 -p:DeployToGame=false
dotnet test $solution --configuration Release --no-build
```

Expected outcomes:

- The probe result above is recorded and successful.
- The normal solution build exits with code `0`, including the `net35` project.
- Every test project in the solution exits with code `0`.
- Test projects recorded outside the solution are run separately and their results recorded.
- No test project or test assembly is part of the Mod Package.

`$testAssemblyNames` must contain every test assembly recorded during inventory; add one entry per test project.

When formatting configuration is available, verify it:

```powershell
dotnet format whitespace $solution --no-restore --verify-no-changes
dotnet format style $solution --no-restore --severity warn --verify-no-changes
```

Both commands must exit with code `0`; record `NOT RUN` with a reason and owner when the formatter or its restore prerequisites are unavailable.

Inspect the main Mod Package instead of inferring it from a successful build:

```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$package = [System.IO.Compression.ZipFile]::OpenRead(
  (Resolve-Path $zipPath)
)
$entries = @($package.Entries.FullName)
$entries
$package.Dispose()

if ($entries -notcontains "plugins/$packageTargetName.dll") {
  throw "The main plugin entry is missing."
}
$testArtifacts = $entries | Where-Object {
  [IO.Path]::GetFileNameWithoutExtension($_) -in $testAssemblyNames
}
if ($testArtifacts) {
  throw "Test output was included in the Mod Package: $testArtifacts"
}
if ($entries | Where-Object { $_ -match '\.Tests(\.dll)?$' }) {
  throw "Test output was included in the Mod Package."
}
```

Set `$zipPath` to the path produced by the recorded package target. Verify the intended resources and data artifacts are present. A successful compile alone does not prove package contents. The exact check uses every recorded test assembly name; the `.Tests` pattern is only a fallback.

Check solution membership and repository hygiene:

```powershell
dotnet sln $solution list
```

For a Git repository, list every changed and untracked file since the recorded start SHA, and review each changed source and configuration file against the pre-edit public-contract inventory:

```powershell
git status --short
git diff '<recorded-start-sha>' --
git diff --check
```

For a non-Git repository, skip `git diff --check` and use the verified backup manifest to list added, modified, and deleted files. Review each changed source and configuration file against the pre-edit inventory.

This is a manual structural comparison, not an automated proof. A source-text search can miss implicit interface members, multiline signatures, and enum values. No public type or member may disappear or change signature without the separately approved breaking-change decision.

If development deployment prerequisites are available, run the opt-in check and inspect the destination:

```powershell
dotnet build $solution --configuration Release --no-restore --no-incremental `
  -p:Version=1.2.3 -p:DeployToGame=true -p:DevFolder="$devFolder"
```

Expected outcome: the solution build preserves solution-relative paths, and the plugin and intended resources/data artifacts are freshly written or updated in the recorded destination. Compare the deployed plugin's hash or timestamp with the build output; a pre-existing file alone is not evidence. If the prerequisites are unavailable or the owner does not approve touching the game profile, record the deployment check as `NOT RUN` with the reason and owner.

## Optional In-Game Smoke

In-game smoke verification is optional. It is not replaced by a build, unit test, package inspection, or CI result.

If the game environment is unavailable, record:

```text
Smoke: NOT RUN
Reason: <missing game, unavailable BepInEx profile, or other concrete reason>
Owner: <person responsible for the remaining check>
```

If it is run, record the Blasphemous version, Mod build version, prerequisites, scenario, expected behavior, observed behavior, and log or screenshot evidence.

## Apply Approved CI and Release Differences

Begin this phase only after the required local gates in [Verify and Record Migration Evidence](#verify-and-record-migration-evidence) pass and the optional smoke result is recorded. Inventory is not approval. Get explicit user approval for each proposed workflow or release difference, then apply only the differences the user approved. Preserve all other workflow, release, and deployment behavior.

If an approved change affects local behavior, rerun the affected gates immediately. After the final approved workflow or release change is committed, confirm a clean working tree and rerun the complete required local gate set. Keep the resulting evidence outside the repository and record the exact 40-character final HEAD. Bind the local results and any applicable hosted-CI result to that same HEAD.

Run applicable hosted CI against the exact final HEAD; hosted CI passes on that same HEAD only after a successful applicable run. Hosted CI is `UNVERIFIED` until an applicable run succeeds; `UNVERIFIED` cannot satisfy completion. A failed required local or hosted check, or any unapproved required residual gap, uses `BLOCKED — DECISION REQUIRED` under [Stop States](#stop-states). Any later commit invalidates both local and hosted evidence; rerun the complete required local gate set and obtain a successful hosted run on the new exact final HEAD.

## Rollback

Use the [Migration Recovery Reference](migrate-mod-repository-recovery.md#rollback) for the ordered Git rollback and Non-Git restore procedures. Starting-state recording and backup creation remain in [Record the Starting State and Prepare Recovery](#record-the-starting-state-and-prepare-recovery). The recovery reference owns only those operations; this guide retains the migration stop states and completion checklist.

## Stop States

Use these stop states exactly:

`BLOCKED — DECISION REQUIRED`

Use when a required local or hosted check fails, an unapproved required residual gap remains, or the next step needs a user decision, including approval of a structural refactor or an external-contract rename. Preserve the branch or backup, record the evidence, and stop before dependent edits.

`UNSUPPORTED FOR THIS MIGRATION RUN`

Use when the supported-input boundary or an infeasible required refactor makes a verified migration impossible. Preserve the inventory and recovery point, and do not continue changing the repository.

`PARTIAL`

Use only after the user explicitly approves a narrowed scope for a deferred approved replacement, an unavailable required verification, or an unrun restore. Record each remaining check, its owner, and its next action; a named follow-up does not replace approval. `PARTIAL` never means the migration is complete. A migration-local `PARTIAL` does not itself establish completion, closure evidence, or closure eligibility.

## Completion Checklist

The migration is complete only when all required local checks pass, approved CI and release differences are applied, applicable hosted CI passes on the exact final 40-character HEAD, and recovery is `TESTED`. `UNVERIFIED` and `PARTIAL` cannot satisfy completion.

- [ ] The repository is within the supported Windows `net35` .NET boundary. If it is not, stop as `UNSUPPORTED FOR THIS MIGRATION RUN`; do not use this checklist as migration completion evidence.
- [ ] A clean Git branch was created from the exact recorded SHA, or a complete external backup outside the target and containing worktree was verified before the first edit.
- [ ] Ignored or untracked files that migration may touch were backed up before the first edit and restored when necessary.
- [ ] The inventory covers identity, layout, public surfaces, package contracts, resources, deployment, CI, secrets, generated files, and ignored files.
- [ ] Display Title, Author, Machine Identifier, plugin assembly, namespaces, public APIs, package identity, and `BepInDependency` IDs are preserved unless a separate breaking change was approved.
- [ ] The existing layout is preserved, or any layout refactor satisfies the [Structural Refactor Gate](#structural-refactor-gate).
- [ ] Required differences are classified and applied; intentional custom behavior is preserved.
- [ ] Every recorded test project passes; the `net48` Automated Test Project is present, non-packable, and not part of the Mod Package.
- [ ] Restore, `net35` build, recorded tests, package inspection, solution membership, and public-surface comparison pass.
- [ ] Deployment targets were inspected before the first build; no copy, write, move, or directory-removal operation can bypass `DeployToGame` and `DevFolder`.
- [ ] The first build explicitly set `DeployToGame=false` against an isolated probe and left it empty; the normal build and tests ran afterward. The explicit opt-in deployment check writes fresh output, or is recorded as `NOT RUN` with reason and owner.
- [ ] Format checks pass when available, or are recorded as `NOT RUN` with reason and owner.
- [ ] Existing workflow semantics and secret names/scopes were inventoried before any replacement; only the differences approved in the separate application phase were applied.
- [ ] Local evidence and the applicable successful hosted-CI result are stored outside the repository and bound to the same exact 40-character final HEAD; any later commit invalidates both.
- [ ] Applicable hosted CI passes on the exact final HEAD; until an applicable run succeeds, record `UNVERIFIED` and do not claim completion.
- [ ] In-game smoke is recorded with evidence, or as `NOT RUN` with reason and owner.
- [ ] Git rollback records the branch switch, newly untracked/ignored paths, and the correct one-commit, squash, or merge revert path, or non-Git restore covers added/modified/deleted files with the required approval.
- [ ] Backup restore is recorded as `TESTED` with evidence. `NOT RUN` cannot satisfy completion and is migration-local `PARTIAL` only under the approved-scope rule in Stop States.
- [ ] No reset-hard, force-push, destructive cleanup, or permanent deletion was used.
- [ ] No completion is claimed while any required decision or verification remains unresolved.
