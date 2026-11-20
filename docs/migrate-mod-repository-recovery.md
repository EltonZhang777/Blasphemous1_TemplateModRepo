# Migration Recovery Reference

This reference contains the Git rollback and Non-Git restore procedures for [Migrate a Blasphemous 1 Mod Repository in Place](migrate-mod-repository.md). Record the starting state and create the verified backup in that migration guide before editing. Keep recovery evidence outside the repository and its containing worktree.

## Rollback

Choose the procedure that matches the repository and migration state. Do not use destructive `git checkout`, `git reset`, or `git clean` commands, and do not permanently delete files. Stop if the starting SHA, backup, or state is uncertain.

### Git before merge

Use this path while migration work has not been merged to the original branch. It returns the working directory to the recorded starting branch; any migration commits remain on the migration branch.

1. Check tracked changes before switching branches:

   ```powershell
   git status --short
   git diff --exit-code
   git diff --cached --exit-code
   ```

   If tracked changes remain, stop and ask the repository owner how to preserve them. Do not switch until the tracked working tree is clean.
2. Switch to the recorded starting branch using the branch name captured before migration:

   ```powershell
   git switch '<recorded-starting-branch>'
   ```

   If Git refuses because an untracked file would be overwritten, stop and ask the repository owner to resolve the path. Do not force the switch or move the file without approval.
3. Confirm that the checked-out commit is the exact recorded starting SHA:

   ```powershell
   git rev-parse HEAD
   ```

   Compare the complete output with the recorded 40-character SHA. Stop on any mismatch.
4. Compare ignored and untracked paths with the starting-state record and verified backup inventory:

   ```powershell
   git status --ignored --short --untracked-files=all
   ```

   Identify every touched ignored or untracked path, including nested files. Record additions, removals, and changed hashes. Do not treat an ignored path as disposable.
5. If a touched path must be moved out of the way, obtain separate owner approval for a quarantine directory outside the repository and containing worktree. Verify the quarantine path and every ancestor for reparse points and containment before moving anything. Preserve each relative path and record its hash. Without approval, stop before quarantine.
6. Restore every touched ignored or untracked path from the verified external backup. Before each read or write, recheck that source and destination are contained in their approved roots and that no path component is a reparse point. Verify each restored file against its recorded SHA-256.
7. Run `git status --short`, `git status --ignored --short --untracked-files=all`, and compare the recorded starting paths and hashes. Confirm the branch and exact starting SHA again. Run the original recorded build and test commands if recovery is being marked `TESTED`.

### Git after merge

Choose exactly one path according to the merge recorded in the repository history and pull request. If the history does not unambiguously identify one path, stop and ask the repository owner. Begin with a clean tracked working tree and record the current branch and HEAD. Prepare the revert without committing, review its complete diff, and obtain separate explicit approval before creating a revert commit.

#### Merge commit

Use only when the migration entered the target branch through a merge commit. Inspect its parents and confirm that parent 1 is the recorded target-branch mainline immediately before the merge; stop if that cannot be verified. Then prepare the revert:

```powershell
$recordedMainlineParent = '<recorded-target-branch-tip-before-merge>'
$mergeParents = @((git show -s --format=%P '<merge-commit>') -split '\s+' | Where-Object { $_ })
if ($mergeParents.Count -lt 2 -or $mergeParents[0] -ne $recordedMainlineParent) {
  throw 'The selected merge commit mainline parent does not match the recorded target branch.'
}
git revert --no-commit -m 1 '<merge-commit>'
git diff --cached --check
git diff --cached
```

Do not commit this prepared revert until its diff has been reviewed and the owner separately approves the revert commit.

#### Linear commit range

Use only when the migration was applied as a contiguous, non-merge sequence of commits. Confirm the recorded start is an ancestor of the target tip and that every commit in the range has exactly one parent. `git rev-list` emits the linear range newest first, which is the order needed to revert it:

```powershell
$start = '<recorded-start-sha>'
$tip = '<migration-tip-on-target>'
git merge-base --is-ancestor $start $tip
if ($LASTEXITCODE -ne 0) { throw 'The recorded start is not an ancestor of the target tip.' }
$commits = @(git rev-list "$start..$tip")
foreach ($commit in $commits) {
  $parents = @((git show -s --format=%P $commit) -split '\s+' | Where-Object { $_ })
  if ($parents.Count -ne 1) { throw "The range contains a merge commit: $commit" }
}
if ($commits.Count -eq 0) { throw 'The migration commit range is empty.' }
$oldestCommit = $commits[-1]
$oldestParents = @((git show -s --format=%P $oldestCommit) -split '\s+' | Where-Object { $_ })
if ($oldestParents.Count -ne 1 -or $oldestParents[0] -ne $start) {
  throw 'The linear range does not begin at the recorded starting SHA.'
}
foreach ($commit in $commits) {
  git revert --no-commit $commit
  if ($LASTEXITCODE -ne 0) { throw "Could not prepare revert for $commit; stop for owner review." }
}
git diff --cached --check
git diff --cached
```

Review the complete prepared diff. Obtain separate explicit approval before creating a revert commit.

#### Squash commit

Use only when the migration is represented by one squash commit. Verify that it has exactly one parent and that parent is the recorded target-branch mainline immediately before the squash. Do not select this path for a merge commit or a linear commit range.

```powershell
$recordedMainlineParent = '<recorded-target-branch-tip-before-squash>'
$parents = @((git show -s --format=%P '<squash-commit>') -split '\s+' | Where-Object { $_ })
if ($parents.Count -ne 1 -or $parents[0] -ne $recordedMainlineParent) {
  throw 'The selected squash commit parent does not match the recorded target branch.'
}
git revert --no-commit '<squash-commit>'
git diff --cached --check
git diff --cached
```

Review the complete prepared diff. Obtain separate explicit approval before creating a revert commit.

### Non-Git restore

Run this procedure first in a disposable copy of the migrated repository. The backup and evidence paths must remain outside both the comparison root and any containing worktree. This procedure includes hidden, ignored, and untracked files; it excludes no file class and does not normalize line endings. It compares file paths and exact SHA-256 values.

Start a fresh PowerShell session. Replace every placeholder, then run the full script. Use a new, empty `$disposableRoot` for the restore trial. The script checks path containment and reparse points again before each target read or write; stop on any error. Do not run the final restore against the original target until the disposable result is reviewed and the owner explicitly approves that restore.

```powershell
$repo = (Resolve-Path -LiteralPath '<migrated-repository-root>').Path
$containingRoot = '<containing-worktree-root-or-empty>'
$backupRoot = [IO.Path]::GetFullPath('<external-backup-root>')
$backup = [IO.Path]::GetFullPath((Join-Path $backupRoot 'repository'))
$manifestPath = [IO.Path]::GetFullPath((Join-Path $backupRoot 'repository-manifest.json'))
$evidenceRoot = [IO.Path]::GetFullPath('<external-evidence-directory>')
$disposableRoot = [IO.Path]::GetFullPath('<new-external-disposable-copy>')
$disposableTarget = [IO.Path]::GetFullPath((Join-Path $disposableRoot 'repository'))
$quarantineRoot = [IO.Path]::GetFullPath('<new-external-quarantine-directory>')

function Test-IsWithin([string] $candidate, [string] $parent) {
  $candidateFull = [IO.Path]::GetFullPath($candidate)
  $parentFull = [IO.Path]::GetFullPath($parent).TrimEnd('\')
  return $candidateFull.Equals($parentFull, [StringComparison]::OrdinalIgnoreCase) -or
    $candidateFull.StartsWith($parentFull + '\', [StringComparison]::OrdinalIgnoreCase)
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
    if (-not $parent -or $parent -eq $path) { break }
    $path = $parent
  }
}

function Assert-NoReparsePointTree([string] $root) {
  Assert-NoReparsePointAncestor $root
  $pending = [Collections.Generic.Stack[string]]::new()
  $pending.Push([IO.Path]::GetFullPath($root))
  while ($pending.Count -gt 0) {
    $directory = $pending.Pop()
    Assert-NoReparsePointAncestor $directory
    foreach ($item in Get-ChildItem -LiteralPath $directory -Force -ErrorAction Stop) {
      if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Resolve repository reparse points before restore: $($item.FullName)"
      }
      if ($item.PSIsContainer) { $pending.Push($item.FullName) }
    }
  }
}

function Assert-RestorePathsSafe([string] $targetRoot, [switch] $SkipTreeCheck) {
  foreach ($candidate in @($targetRoot, $backupRoot, $backup, $manifestPath, $evidenceRoot, $quarantineRoot)) {
    Assert-NoReparsePointAncestor $candidate
  }
  if (-not (Test-IsWithin $backup $backupRoot)) { throw 'Backup is outside backup root.' }
  if (-not (Test-IsWithin $manifestPath $backupRoot)) { throw 'Manifest is outside backup root.' }
  foreach ($external in @($backupRoot, $evidenceRoot, $quarantineRoot)) {
    if ((Test-IsWithin $external $targetRoot) -or (Test-IsWithin $targetRoot $external)) {
      throw "Target and external paths must not contain each other: $external"
    }
    if ($containingRoot -and ((Test-IsWithin $external $containingRoot) -or (Test-IsWithin $containingRoot $external))) {
      throw "External path overlaps the containing worktree: $external"
    }
  }
  foreach ($left in @($backupRoot, $evidenceRoot, $quarantineRoot)) {
    foreach ($right in @($backupRoot, $evidenceRoot, $quarantineRoot)) {
      if ($left -ne $right -and ((Test-IsWithin $left $right) -or (Test-IsWithin $right $left))) {
        throw "External paths must not contain each other: $left, $right"
      }
    }
  }
  if (-not $SkipTreeCheck) {
    foreach ($root in @($targetRoot, $backup)) {
      if (Test-Path -LiteralPath $root) { Assert-NoReparsePointTree $root }
    }
  }
}

function Resolve-ContainedFilePath([string] $root, [string] $relativePath) {
  if ([IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
    throw "Manifest path is not relative to its root: $relativePath"
  }
  $full = [IO.Path]::GetFullPath((Join-Path $root $relativePath))
  if (-not (Test-IsWithin $full $root) -or $full -eq [IO.Path]::GetFullPath($root)) {
    throw "Manifest path escapes its root: $relativePath"
  }
  return $full
}

function Get-RepositoryManifest([string] $root, [string] $targetRoot) {
  if ($root -eq $targetRoot) { Assert-RestorePathsSafe $targetRoot }
  $files = @(Get-ChildItem -LiteralPath $root -Recurse -File -Force -ErrorAction Stop)
  $result = foreach ($file in $files) {
    if ($root -eq $targetRoot) { Assert-RestorePathsSafe $targetRoot -SkipTreeCheck }
    Assert-NoReparsePointAncestor $file.FullName
    [pscustomobject]@{
      RelativePath = $file.FullName.Substring($root.Length).TrimStart('\')
      Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $file.FullName -ErrorAction Stop).Hash
    }
  }
  return @($result | Sort-Object RelativePath)
}

function Invoke-ManifestRestore([string] $targetRoot) {
  Assert-RestorePathsSafe $targetRoot
  if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw "Missing backup manifest: $manifestPath" }
  Assert-NoReparsePointAncestor $manifestPath
  $expected = @(Get-Content -LiteralPath $manifestPath -Raw -ErrorAction Stop | ConvertFrom-Json)
  $backupManifest = @(Get-RepositoryManifest $backup '')
  if ($expected.Count -ne $backupManifest.Count) { throw 'Persisted manifest is incomplete.' }
  if (@(Compare-Object $expected $backupManifest -Property RelativePath, Hash).Count -ne 0) {
    throw 'Persisted manifest does not match the verified backup.'
  }
  $expectedByPath = @{}
  foreach ($entry in $expected) {
    $null = Resolve-ContainedFilePath $backup $entry.RelativePath
    $expectedByPath[$entry.RelativePath] = $entry.Hash
  }

  $actual = @(Get-RepositoryManifest $targetRoot $targetRoot)
  $actualByPath = @{}
  foreach ($entry in $actual) { $actualByPath[$entry.RelativePath] = $entry.Hash }
  foreach ($entry in $actual) {
    if (-not $expectedByPath.ContainsKey($entry.RelativePath)) {
      $source = Resolve-ContainedFilePath $targetRoot $entry.RelativePath
      $destination = Resolve-ContainedFilePath $quarantineRoot $entry.RelativePath
      Assert-RestorePathsSafe $targetRoot -SkipTreeCheck
      Assert-NoReparsePointAncestor $source
      Assert-NoReparsePointAncestor $destination
      $parent = Split-Path -Parent $destination
      New-Item -ItemType Directory -Path $parent -Force | Out-Null
      Assert-RestorePathsSafe $targetRoot -SkipTreeCheck
      Assert-NoReparsePointAncestor $source
      Assert-NoReparsePointAncestor $destination
      Move-Item -LiteralPath $source -Destination $destination -ErrorAction Stop
    }
  }
  foreach ($entry in $expected) {
    $source = Resolve-ContainedFilePath $backup $entry.RelativePath
    $destination = Resolve-ContainedFilePath $targetRoot $entry.RelativePath
    if ($actualByPath.ContainsKey($entry.RelativePath) -and $actualByPath[$entry.RelativePath] -eq $entry.Hash) {
      continue
    }
    Assert-RestorePathsSafe $targetRoot -SkipTreeCheck
    Assert-NoReparsePointAncestor $source
    Assert-NoReparsePointAncestor $destination
    if (Test-Path -LiteralPath $destination) {
      $currentItem = Get-Item -LiteralPath $destination -Force -ErrorAction Stop
      $quarantineRelativePath = $entry.RelativePath
      if ($currentItem.PSIsContainer) {
        $quarantineRelativePath = Join-Path '.directory-conflicts' $entry.RelativePath
      }
      $quarantine = Resolve-ContainedFilePath $quarantineRoot $quarantineRelativePath
      Assert-NoReparsePointAncestor $quarantine
      $quarantineParent = Split-Path -Parent $quarantine
      New-Item -ItemType Directory -Path $quarantineParent -Force | Out-Null
      Assert-RestorePathsSafe $targetRoot -SkipTreeCheck
      Assert-NoReparsePointAncestor $destination
      Assert-NoReparsePointAncestor $quarantine
      Move-Item -LiteralPath $destination -Destination $quarantine -ErrorAction Stop
    }
    $parent = Split-Path -Parent $destination
    if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
    Assert-RestorePathsSafe $targetRoot -SkipTreeCheck
    Assert-NoReparsePointAncestor $source
    Assert-NoReparsePointAncestor $destination
    Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop
  }

  $restored = @(Get-RepositoryManifest $targetRoot $targetRoot)
  $differences = @(Compare-Object $expected $restored -Property RelativePath, Hash)
  $added = @($differences | Where-Object SideIndicator -eq '=>')
  $deleted = @($differences | Where-Object SideIndicator -eq '<=')
  $modified = @(
    foreach ($path in $expectedByPath.Keys) {
      $expectedHash = $expectedByPath[$path]
      $restoredEntry = $restored | Where-Object RelativePath -eq $path | Select-Object -First 1
      if (-not $restoredEntry -or $restoredEntry.Hash -ne $expectedHash) { $path }
    }
  )
  if ($added.Count -or $deleted.Count -or $modified.Count) {
    throw "Restore differs: added=$($added.Count), deleted=$($deleted.Count), modified=$($modified.Count)"
  }
  return [pscustomobject]@{ Added = $added; Deleted = $deleted; Modified = $modified }
}

Assert-NoReparsePointAncestor $repo
Assert-NoReparsePointAncestor $backupRoot
Assert-NoReparsePointAncestor $evidenceRoot
Assert-NoReparsePointAncestor $disposableRoot
Assert-RestorePathsSafe $repo
if ((Test-Path -LiteralPath $disposableRoot) -or (Test-Path -LiteralPath $quarantineRoot)) {
  throw 'Choose new, empty disposable and quarantine paths.'
}
if ($containingRoot) { Assert-NoReparsePointAncestor $containingRoot }
if ((Test-IsWithin $disposableRoot $repo) -or (Test-IsWithin $repo $disposableRoot)) {
  throw 'The disposable copy must be separate from the original repository.'
}
if ($containingRoot -and ((Test-IsWithin $disposableRoot $containingRoot) -or (Test-IsWithin $containingRoot $disposableRoot))) {
  throw 'The disposable copy must be outside the containing worktree.'
}
foreach ($candidateRoot in @($disposableRoot, $disposableTarget)) {
  foreach ($external in @($backupRoot, $evidenceRoot, $quarantineRoot)) {
    if ((Test-IsWithin $candidateRoot $external) -or (Test-IsWithin $external $candidateRoot)) {
      throw "Disposable and external paths must not contain each other: $candidateRoot, $external"
    }
  }
}
Assert-RestorePathsSafe $disposableTarget
Assert-NoReparsePointAncestor $disposableRoot
Assert-NoReparsePointAncestor $disposableTarget
New-Item -ItemType Directory -Path $disposableRoot | Out-Null
Assert-RestorePathsSafe $repo
Assert-RestorePathsSafe $disposableTarget
Assert-NoReparsePointAncestor $disposableTarget
$null = robocopy $repo $disposableTarget /E /COPY:DAT /DCOPY:DAT /R:1 /W:1 /XJ
if ($LASTEXITCODE -gt 7) { throw "Disposable copy failed with exit code $LASTEXITCODE" }
$null = Invoke-ManifestRestore $disposableTarget

# Keep this complete file comparison outside $disposableTarget and $repo.
$evidencePath = Join-Path $evidenceRoot 'restore-comparison.json'
Assert-RestorePathsSafe $disposableTarget
Assert-NoReparsePointAncestor $evidencePath
$null = New-Item -ItemType Directory -Path $evidenceRoot -Force
Assert-RestorePathsSafe $disposableTarget
Assert-NoReparsePointAncestor $evidencePath
$comparison = Get-RepositoryManifest $disposableTarget $disposableTarget
$comparisonResult = [pscustomobject]@{
  Added = @()
  Deleted = @()
  Modified = @()
  Files = $comparison
}
ConvertTo-Json -InputObject $comparisonResult -Depth 5 |
  Set-Content -LiteralPath $evidencePath -Encoding UTF8
if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) { throw 'Restore evidence was not written.' }

# Run each original recorded build and test command in the disposable repository only after the comparison is empty.
# Record exact commands, output, manifest/evidence paths, and result outside the comparison root.

function Invoke-ApprovedOriginalRestore([string] $finalQuarantinePath) {
  $trialQuarantineRoot = $quarantineRoot
  $finalQuarantineRoot = [IO.Path]::GetFullPath($finalQuarantinePath)
  Assert-NoReparsePointAncestor $finalQuarantineRoot
  Assert-NoReparsePointAncestor $disposableRoot
  if (Test-Path -LiteralPath $finalQuarantineRoot) {
    throw 'Choose a new, nonexistent final-restore quarantine path.'
  }
  if (
    (Test-IsWithin $finalQuarantineRoot $trialQuarantineRoot) -or
    (Test-IsWithin $trialQuarantineRoot $finalQuarantineRoot) -or
    (Test-IsWithin $finalQuarantineRoot $disposableRoot) -or
    (Test-IsWithin $disposableRoot $finalQuarantineRoot)
  ) {
    throw 'The final-restore quarantine must be separate from the trial quarantine and disposable copy.'
  }
  $quarantineRoot = $finalQuarantineRoot
  $targetRoot = $repo
  Assert-RestorePathsSafe $targetRoot
  $null = Invoke-ManifestRestore $targetRoot
}
```

`Restore: TESTED` requires the disposable restore above to produce empty added, deleted, and modified file sets and matching SHA-256 hashes for every file in the persisted complete manifest, followed by the original recorded build and test commands in the restored disposable copy. Record commands, output, hashes, and manifest/evidence paths outside the comparison root. If restore or verification was not run, record `Restore: NOT RUN`; `NOT RUN` cannot complete the migration.

#### Apply the approved restore to the original repository

After reviewing the disposable result and receiving separate owner approval, keep the PowerShell session open so the variables and helper functions defined by the procedure remain available. Keep the disposable copy and its trial quarantine. Choose a new external quarantine path for the original repository; the function stops if the path exists or overlaps the trial quarantine or disposable copy. It rechecks containment and reparse points before applying the restore.
After that approval, call `Invoke-ApprovedOriginalRestore -finalQuarantinePath '<new-external-quarantine-for-final-restore>'`. If the PowerShell session was closed, rerun the full procedure in a fresh session to define its inputs and helpers, then review the new disposable trial before calling the function.

### Git restore evidence

`Restore: TESTED` for Git requires a disposable clone checked out at the recorded starting SHA, with its tracked tree matching the starting tree. The following example restores the exact ignored or untracked paths recorded before migration; replace each placeholder and include one row for every backed-up path:

```powershell
$sourceRepository = (Resolve-Path -LiteralPath '<source-repository>').Path
$disposableClone = [IO.Path]::GetFullPath('<new-external-disposable-clone>')
$startingSha = '<recorded-start-sha>'
$backupRoot = [IO.Path]::GetFullPath('<verified-external-backup-root>')
$backup = [IO.Path]::GetFullPath((Join-Path $backupRoot 'ignored-untracked'))
$containingRoot = '<containing-worktree-root-or-empty>'
$evidenceRoot = [IO.Path]::GetFullPath('<external-evidence-directory>')
$recordedFiles = @(
  [pscustomobject]@{ RelativePath = '<recorded-relative-path>'; Hash = '<recorded-sha256>' }
)

function Test-IsWithin([string] $candidate, [string] $parent) {
  $candidateFull = [IO.Path]::GetFullPath($candidate)
  $parentFull = [IO.Path]::GetFullPath($parent).TrimEnd('\')
  return $candidateFull.Equals($parentFull, [StringComparison]::OrdinalIgnoreCase) -or
    $candidateFull.StartsWith($parentFull + '\', [StringComparison]::OrdinalIgnoreCase)
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
    if (-not $parent -or $parent -eq $path) { break }
    $path = $parent
  }
}

function Resolve-ContainedFilePath([string] $root, [string] $relativePath) {
  if ([IO.Path]::IsPathRooted($relativePath) -or $relativePath -match '(^|[\\/])\.\.([\\/]|$)') {
    throw "Backup path is not relative to its root: $relativePath"
  }
  $full = [IO.Path]::GetFullPath((Join-Path $root $relativePath))
  if (-not (Test-IsWithin $full $root) -or $full -eq [IO.Path]::GetFullPath($root)) {
    throw "Backup path escapes its root: $relativePath"
  }
  return $full
}

Assert-NoReparsePointAncestor $sourceRepository
Assert-NoReparsePointAncestor $backupRoot
Assert-NoReparsePointAncestor $backup
Assert-NoReparsePointAncestor $evidenceRoot
Assert-NoReparsePointAncestor $disposableClone
foreach ($external in @($backupRoot, $evidenceRoot, $disposableClone)) {
  if ((Test-IsWithin $external $sourceRepository) -or (Test-IsWithin $sourceRepository $external)) {
    throw "Clone, backup, and evidence must be outside the source repository: $external"
  }
  if ($containingRoot -and ((Test-IsWithin $external $containingRoot) -or (Test-IsWithin $containingRoot $external))) {
    throw "Clone, backup, and evidence must be outside the containing worktree: $external"
  }
}
$externalRoots = @($backupRoot, $evidenceRoot, $disposableClone)
foreach ($left in $externalRoots) {
  foreach ($right in $externalRoots) {
    if ($left -ne $right -and ((Test-IsWithin $left $right) -or (Test-IsWithin $right $left))) {
      throw "Clone, backup, and evidence paths must not contain each other: $left, $right"
    }
  }
}
if (Test-Path -LiteralPath $disposableClone) { throw 'Choose a new disposable-clone path.' }
git clone --no-hardlinks --no-checkout $sourceRepository $disposableClone
if ($LASTEXITCODE -ne 0) { throw 'Disposable clone failed.' }
git -C $disposableClone switch --detach $startingSha
if ($LASTEXITCODE -ne 0) { throw 'Could not check out the recorded starting SHA.' }
$treeAtStart = (git -C $disposableClone rev-parse "$startingSha^{tree}").Trim()
$actualTree = (git -C $disposableClone rev-parse 'HEAD^{tree}').Trim()
if ($actualTree -ne $treeAtStart) { throw 'Disposable clone tracked tree differs from the starting tree.' }
git -C $disposableClone diff --exit-code $startingSha --
if ($LASTEXITCODE -ne 0) { throw 'Disposable clone has tracked changes.' }

$copyEvidence = @()
foreach ($entry in $recordedFiles) {
  $source = Resolve-ContainedFilePath $backup $entry.RelativePath
  $destination = Resolve-ContainedFilePath $disposableClone $entry.RelativePath
  Assert-NoReparsePointAncestor $source
  Assert-NoReparsePointAncestor $destination
  git -C $disposableClone ls-files --error-unmatch -- $entry.RelativePath 2>$null
  if ($LASTEXITCODE -eq 0) { throw "Recorded ignored/untracked path is tracked at the starting SHA: $($entry.RelativePath)" }
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing backed-up file: $source" }
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $source).Hash -ne $entry.Hash) {
    throw "Backup hash differs from starting-state record: $($entry.RelativePath)"
  }
  $parent = Split-Path -Parent $destination
  if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
  Assert-NoReparsePointAncestor $source
  Assert-NoReparsePointAncestor $destination
  Copy-Item -LiteralPath $source -Destination $destination -Force -ErrorAction Stop
  if ((Get-FileHash -Algorithm SHA256 -LiteralPath $destination).Hash -ne $entry.Hash) {
    throw "Restored file hash differs from starting-state record: $($entry.RelativePath)"
  }
  $copyEvidence += [pscustomobject]@{ RelativePath = $entry.RelativePath; Hash = $entry.Hash }
}
$status = @(git -C $disposableClone status --ignored --short --untracked-files=all)
$treeAfterRestore = (git -C $disposableClone rev-parse 'HEAD^{tree}').Trim()
git -C $disposableClone diff --exit-code $startingSha --
if ($LASTEXITCODE -ne 0) { throw 'Restoring ignored/untracked paths changed the tracked tree.' }
$evidencePath = Resolve-ContainedFilePath $evidenceRoot 'git-restore-evidence.json'
Assert-NoReparsePointAncestor $evidencePath
if (Test-Path -LiteralPath $evidencePath) { throw 'Choose a new Git restore evidence path.' }
New-Item -ItemType Directory -Path $evidenceRoot -Force | Out-Null
Assert-NoReparsePointAncestor $evidencePath
$evidence = [pscustomobject]@{
  StartingSha = $startingSha
  StartingTree = $treeAtStart
  RestoredTree = $treeAfterRestore
  RestoredFiles = $copyEvidence
  GitStatus = $status
}
ConvertTo-Json -InputObject $evidence -Depth 5 |
  Set-Content -LiteralPath $evidencePath -Encoding UTF8
if (-not (Test-Path -LiteralPath $evidencePath -PathType Leaf)) { throw 'Git restore evidence was not written.' }

# Run the original recorded build and test commands in $disposableClone.
# Append their exact commands, output, and result to evidence under $evidenceRoot.
```

Run the original recorded build and test commands in the disposable clone and record their outputs outside it. Do not infer restore success from the existence of a branch or backup. `Restore: NOT RUN` cannot complete the migration.
