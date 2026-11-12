# Blasphemous 1 Mod Repository Template

The official Blasphemous 1 Mod template, the repository-owned wrapper that completes its output, and the verification-Mod test template.

## Language

**Official Template Baseline**:
The installed `Blasphemous.Modding.Templates` version `1.4.1` that supplies the base Mod project.
_Avoid_: vendored template, forked template

**Generator Command**:
The repository-owned command that verifies the Official Template Baseline, invokes `dotnet new`, and applies the Overlay.
_Avoid_: initializer, custom template

**Overlay Root**:
The `TemplateRepo/` directory containing files and modifications applied after official template generation.
_Avoid_: template root, cloneable template

**Overlay**:
The repository-owned files and transformations applied to the official template's staging output.
_Avoid_: template content, patchset

**Mod Identity**:
The machine identifier, display title, and author selected for a Mod, together with the project, namespace, solution, test, and plugin names derived from them.
_Avoid_: project name

**Machine Identifier**:
The identifier-safe Mod name used for the project, namespace, solution, test, and plugin assembly names.
_Avoid_: slug, namespace

**Display Title**:
The human-readable Mod name used in metadata and documentation.
_Avoid_: mod name

**Automated Test Project**:
The adjacent `net48` xUnit project that references the generated `net35` Mod and runs without the game.
_Avoid_: test Mod, verification Mod

**Verification Mod**:
The `net35` Mod generated to load in-game and verify another Mod or prerequisite library through its public surface.
_Avoid_: automated test project, test fixture

**Test Template Package**:
The `blasModTest` dotnet template distributed as `Blasphemous1.ModTest.Templates`.
_Avoid_: template repository, overlay

**Mod Package**:
The release ZIP whose `plugins/<TargetName>.dll` file is the Mod entry assembly.
_Avoid_: release, bundle
