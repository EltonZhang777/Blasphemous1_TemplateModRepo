# Isolate dotnet template tests from the user PATH

## Status

Accepted

## Context

The meta-repository's dotnet template tests create a fresh `DOTNET_CLI_HOME`
per test and run `dotnet new install`. `DOTNET_CLI_HOME` isolates template
state, but it is not a Windows-user isolation boundary; the .NET CLI can append
the Test Hive's `.dotnet\tools` directory to the real user's persistent
`HKCU\Environment\Path`. The original incident accumulated 275 temporary hive
entries, and the current User PATH still contains 25 repository `.wt` hive
entries whose target directories are all missing. The environment block
exceeded the Windows limit and caused system-wide `0xC0000017` process-creation
failures.

The Generator Command and Test Template Package are Consumer Entry Points, not
the polluting test harness. The Generator Command does not install templates or
set `DOTNET_CLI_HOME`/PATH; the Test Template Package has no post-actions. A
consumer `dotnet new install` may make the .NET CLI's normal one-time default
tools entry, but it does not create the repeated Test Hive pattern unless the
consumer creates a fresh `DOTNET_CLI_HOME` per invocation.

## Decision

- Run dotnet-backed template tests only in a Disposable Test Context: an
  ephemeral CI runner, Windows Sandbox, or another disposable VM.
- On a normal maintainer checkout, skip those tests before the first dotnet
  invocation and state why.
- Capture raw User and Machine Path before and after every dotnet-backed test
  context. A non-disposable host must show zero change; a disposable context
  must report an exact diff and fail on additions outside the declared Test
  Hive.
- Never repair, normalize, de-duplicate, or delete persistent PATH entries from
  a test or build.
- Keep the existing 25 residual entries as a separate, backed-up,
  human-approved cleanup; this ADR does not authorize automatic cleanup.
- Keep consumer wrapper and template behavior unchanged; document that
  consumers using a custom `DOTNET_CLI_HOME` must use a fixed or disposable
  context.

## Considered Options

- Keep running tests on the host and clean PATH afterward. Rejected because
  contamination occurs before cleanup and can break process creation.
- Set `DOTNET_CLI_HOME` only. Rejected because it is template-state isolation,
  not user isolation.
- Run dotnet-backed tests only in Disposable Test Contexts. Chosen.

## Consequences

Local maintainers lose dotnet-backed template coverage on a normal checkout;
they must use Windows Sandbox, CI, or a disposable VM. The test harness must
fail closed rather than silently repair PATH. The safety behavior is
implemented by ticket #15, while residual cleanup remains a separate operation.
Consumer setup still relies on normal .NET CLI behavior and is not promised to
be free of the CLI's standard one-time tools-path write.
