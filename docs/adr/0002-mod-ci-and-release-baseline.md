# Use a Windows .NET 10 baseline for Mod CI

## Status

Accepted

## Context

The available reference repositories have different shapes. `NewbieEltonLibs` is a net35 class library with .NET 8 library CI, while FrameRateUnlimiter is a net35 BepInEx Mod with an adjacent net48 xUnit project and a `plugins/<TargetName>.dll` ZIP layout.

The template must verify the Mod and its tests, create a usable Mod Package, and support NuGet publishing without a long-lived API key.

## Decision

- Use a `.sln` solution, `windows-latest`, and .NET 10 for build, test, and formatting jobs.
- Keep the Mod at net35 and use a net48 adjacent xUnit project that directly references the Mod.
- Build and test on `main` pushes and eligible tags. Validate pull requests that target `main`.
- Accept both `v*` and bare SemVer tags. A non-main-ancestor release tag fails.
- Create a draft release with only the Mod Package ZIP.
- Publish NuGet with `NuGet/login@v1` and OIDC. The release job has `id-token: write`; pull request jobs do not receive publishing credentials.
- Skip NuGet when `NUGET_USERNAME` is missing and warn. A present credential rejected by NuGet fails the release job.
- Skip Discord when `WEBHOOK_URL` is missing and warn. Notify only for a published, non-prerelease release.
- Normalize tracked C# files to CRLF before validation. Fail if normalization changes the checkout.

## Consequences

The class-library release workflow is not copied as-is. CI must prove net35 build, net48 test execution, ZIP packaging, formatting, trusted publishing, and the Windows line-ending step before implementation is accepted. .NET 8 is not used as the template baseline.
