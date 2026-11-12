# Wrap the official template with a non-vendored overlay

## Status

Accepted

## Context

The official `blas1mod` template is the established Mod creation workflow, but its current output has stale dependencies, unconditional game deployment, and no solution, automated tests, agent documentation, or project CI. The official author authorized adaptation, but publishing a fork would duplicate upstream content, create synchronization work, and leave distribution terms dependent on attribution rather than a clear package license.

The previous cloneable-template and custom-initializer design duplicated naming behavior already provided by the dotnet template engine and required a large manifest and rollback system.

## Decision

- Treat the exact `Blasphemous.Modding.Templates` `1.4.1` installation as the Official Template Baseline.
- Use a Generator Command that invokes `dotnet new blas1mod` in a staging directory, applies the Overlay, validates the result, and only then creates the requested output.
- Keep Overlay content under `TemplateRepo/`; it is no longer a cloneable repository.
- Do not vendor, embed, or redistribute the official template.
- Do not install or update the official template automatically.
- Perform no Git operations in the Generator Command.
- Provide the Verification Mod as a separate `blasModTest` Test Template Package for existing repositories.
- Reuse the Test Template Package content for the Generator Command's opt-in Verification Mod, while keeping the package independently installable.

## Consequences

Generated output is reproducible against one upstream baseline, but the wrapper must fail clearly when that version is missing or changes. The official template remains the only base-project implementation, so upgrades require an explicit compatibility update. The dotnet template engine owns identity replacement, leaving less custom generator code and a smaller failure surface.
The Generator Command and Test Template Package share the Verification Mod source and fixed metadata contract; changes to one must keep both paths aligned.
