# Keep the cloneable template inside TemplateRepo

## Status

Superseded by [ADR-0003](0003-non-vendored-official-template-overlay.md).

The cloneable-template boundary, manifest, and custom initializer described below are no longer active.

## Context

The meta-repository contains its own management files and a cloneable Blasphemous 1 Mod template. Mixing both sets of files would make it ambiguous which files belong to a new Mod repository.

Initialization changes many files and paths. A partial run could leave a repository that is neither a valid template nor a valid Mod.

## Decision

- All Template Content lives under `TemplateRepo/`. The meta-repository root contains only management and explanatory files.
- The initializer runs only when its current working directory is the Template Root. It requires a dedicated marker and the expected project files.
- A template manifest defines the Template-owned files and paths. The initializer does not use Git status or Git history.
- Initialization collects a Machine Identifier, Display Title, and Author, shows a complete plan, and requires confirmation.
- The initializer does not rename the Template Root, change `.git`, or run Git commands.
- The initializer has transactional failure recovery. It removes the marker and manifest after success and safely refuses a second run.

## Consequences

Template ownership is explicit and testable. The template must keep its manifest synchronized, and initialization must be verified against wrong-directory, rollback, conflict, and repeated-run cases.
