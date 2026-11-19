# Restore the generated development configuration

## Status

Accepted

## Context

Commit `0c5b89d` reduced the Overlay's `.editorconfig` to global and non-C# indentation policies and reduced `.gitignore` to a short list. That left generated repositories without the established C# conventions and omitted Visual Studio user state, certificate files, and publish settings that are relevant to the generated development workflow.

The real-generation test only checked that both files existed, so either file could regress without failing a test.

## Decision

- Keep the current UTF-8, CRLF, final-newline, trailing-whitespace, four-space indentation, and non-C# two-space indentation policies.
- Restore the former C# convention families in the single `[*.cs]` section.
- Do not force `System` using directives first.
- Remove the former C# `insert_final_newline = false` override so C# inherits the global `true` policy.
- Generate exactly 19 ignore rules for build and test output, Visual Studio user state, package output, local development and agent state, certificates, and publish settings.
- Exclude unrelated language, platform, IDE-plugin, logging, and coverage rules so the policy stays small and auditable.
- Reject duplicate EditorConfig sections across the generated `.editorconfig` and duplicate keys within any section before merge.
- Assert exact key/value sets for the global `[*]` section, the single `[*.cs]` section, and the existing non-C# section. Keep the exact ordered `.gitignore` rule-list assertion.

Certificate and publish-settings rules remain because they prevent accidental staging of local credentials or deployment configuration. The ignore list is curated instead of inheriting a broad Visual Studio ignore file because most of that file covers tools this template does not use.

## Consequences

Generated C# files receive the established conventions without changing the global or non-C# policies.

The real-generation test rejects duplicate sections and per-section duplicate keys. It catches missing, extra, or changed keys and values in the checked sections, and it catches changes to the ordered `.gitignore` list. It does not run `git check-ignore`, so it verifies the configured rule set, not Git's matching behavior. The accepted limitation is sufficient because the rules are intentionally simple and the behavior test would add a separate temporary-repository seam.
