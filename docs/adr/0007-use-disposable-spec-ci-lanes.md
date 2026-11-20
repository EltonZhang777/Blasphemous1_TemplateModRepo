# Use disposable spec CI lanes for integration evidence

## Status

Accepted

This decision extends [ADR-0002](0002-mod-ci-and-release-baseline.md) without changing its `main` or `test-ci` trigger contract.

## Context

Several approved specifications integrate concurrently on separate branches. Their dotnet-backed acceptance checks must run only in a Disposable Test Context, as required by [ADR-0004](0004-isolate-template-tests-from-user-path.md). The existing `test-ci` branch remains the long-term disposable validation target, but sharing one unprotected integration ref would make branch ownership, history, and exact-HEAD evidence ambiguous across concurrent specifications.

## Decision

- Add `.github/workflows/spec-validate.yml` as a caller for pushes to `spec-ci/**`. It invokes the existing reusable `validate.yml` workflow with `contents: read`.
- Keep `validate.yml` direct triggers for `main` and `test-ci` unchanged. The caller is an additional event surface, not a replacement for those triggers.
- Use one integration lane per specification, named `spec-ci/issue-<spec>` and created from one shared bootstrap commit. Advance a lane only by fast-forward integration. Never force-push, and retain the branch after completion unless a separate deletion decision is approved.
- Pin SDK selection to .NET 10 with the root `global.json` so a newer preinstalled SDK cannot silently replace the documented baseline.
- Do not add a per-lane concurrency group. Overlapping pushes are correlated by their exact SHA rather than by replacing or cancelling an earlier run.
- In `validate.yml`, fail before dotnet setup when checkout HEAD differs from the event SHA. On success, record the exact SHA, caller run ID, and caller run URL in the job summary.
- Treat the recorded caller run as evidence only for the checkout at that SHA. A later commit invalidates earlier local and hosted evidence.
- Do not treat the workflow-file contract as proof that a hosted event occurred. Only an observed successful caller run on the exact HEAD is hosted evidence.

## Consequences

Each specification can expose a disposable integration branch without changing the established `test-ci` contract. GitHub Actions runners host the dotnet-backed tests, so maintainers do not need to run those tests on a normal Windows checkout. The repository gains four short-lived integration refs and a second read-only workflow entry point to maintain. Branch protection, permanent history, and force-push permission remain outside the guarantee.
