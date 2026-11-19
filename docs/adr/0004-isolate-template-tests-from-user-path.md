# Isolate dotnet template tests from the user PATH

## Status

Accepted

## Context

The meta-repository's dotnet template tests create a fresh `DOTNET_CLI_HOME` per test and run `dotnet new install`. `DOTNET_CLI_HOME` isolates template state, but it is not a Windows-user isolation boundary; the .NET CLI can append the Test Hive's `.dotnet\tools` directory to the real user's persistent `HKCU\Environment\Path`. The original incident accumulated 275 temporary hive entries, and the current User PATH still contains 25 repository `.wt` hive entries whose target directories are all missing. The environment block exceeded the Windows limit and caused system-wide `0xC0000017` process-creation failures.

The meta-repository test harness is distinct from Consumer Entry Points. This decision covers only the meta-repository test harness; the PATH behavior of the Generator Command, Test Template Package, generated projects, and other Consumer Entry Points is out of scope.

## Decision

- Run dotnet-backed template tests only in a Disposable Test Context: an ephemeral CI runner, Windows Sandbox, or another disposable VM.
- On a normal maintainer checkout, skip those tests before the first dotnet invocation and state why.
- Capture a paired PATH Snapshot before and after every dotnet-backed test context. Each snapshot records the raw User and Machine Path, a shared context identifier, its `before` or `after` phase, and a UTC capture time. Take the before snapshot immediately before the context's first dotnet invocation. Take the after snapshot after the test body completes and before the context exits. A snapshot without its pair is not evidence. A non-disposable host must show zero change; a disposable context must report an exact diff and fail on additions outside the declared Test Hive.
- Never repair, normalize, de-duplicate, or delete persistent PATH entries from a test or build.
- Keep the existing 25 residual entries as a separate, backed-up, human-approved cleanup; this ADR does not authorize automatic cleanup.

## Considered Options

- Keep running tests on the host and clean PATH afterward. Rejected because contamination occurs before cleanup and can break process creation.
- Set `DOTNET_CLI_HOME` only. Rejected because it is template-state isolation, not user isolation.
- Run dotnet-backed tests only in Disposable Test Contexts. Chosen.

## Consequences

Local maintainers lose dotnet-backed template coverage on a normal checkout; they must use Windows Sandbox, CI, or a disposable VM. The test harness must fail closed rather than silently repair PATH. The safety behavior is implemented by [tests/path_safety.py](../../tests/path_safety.py). A PATH Snapshot proves only the sampled User and Machine Persistent PATH values at its capture points; it does not prove atomic reads or process-local PATH.
