# Blasphemous 1 Mod Test template

`blasmodtest` adds a `net35` verification Mod to an existing Blasphemous 1 Mod or class-library repository.

## Prerequisites

- Windows and the .NET SDK 10 available on `PATH`.
- NuGet access to the sources configured by the existing repository for `Blasphemous.ModdingAPI` and `Blasphemous.GameLibs`.
- An existing compatible Blasphemous 1 Mod or class-library repository and its solution.
- Blasphemous 1 installed with BepInEx and an existing `Modding` folder.

## Install and generate

**Consumer safety:** If you use a custom .NET CLI home (`DOTNET_CLI_HOME`), reuse one fixed path between runs or use a disposable context. Do not create a new home directory per invocation. This is a safety precaution for this consumer workflow, not a guarantee about all .NET CLI behavior.

```powershell
dotnet new install Blasphemous1.ModTest.Templates

dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  --title "Example Mod Test" `
  -au "Example Author"
```

The generated project references the Blasphemous ModdingAPI `3.0.1` and GameLibs `4.0.67`. Once constructed, the Verification Mod logs `[<generated name>] STARTUP_READY` with its generated Mod ID.

## Reference an existing project

Pass `--targetProject` with an absolute path or a path relative to the generated project:

```powershell
dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  -o .\Blasphemous.Example.TestMod `
  --title "Example Mod Test" `
  -au "Example Author" `
  --targetProject ..\Blasphemous.Example\Blasphemous.Example.csproj
```

The target project is added as a normal `ProjectReference`. Building the Verification Mod also builds the target project and includes its assembly in the archive below. The generated Verification Mod does not call target APIs.

An invalid target path fails the build with `Target project not found`.

## Wire the solution manually

The template writes only the new project and its source files. Add it to the existing solution yourself:

```powershell
dotnet sln add .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
dotnet build .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
```

A successful build creates `publish\<project>.zip` with the Verification Mod under `plugins/`. If a target project was supplied, its assembly is included there too; otherwise, the ZIP contains only the Verification Mod.

## Verify startup in-game

1. Close Blasphemous 1 and confirm it has exited.
2. Rename any existing BepInEx log to a non-colliding backup name.
3. Extract the archive directly into the game's `Modding` folder.
4. Confirm the generated Verification Mod assembly is in the game's `Modding/plugins` directory.
5. Start Blasphemous 1.
6. Wait until loading completes.
7. Inspect only the newly created BepInEx log for `[<generated name>] STARTUP_READY`.

For the example generated name `Blasphemous.Example.TestMod`, the expected marker is `[Blasphemous.Example.TestMod] STARTUP_READY`.

## What startup proves

This evidence only proves that the Verification Mod reached its startup log. It does not prove the target assembly was loaded, that a target public API was called, or that target runtime behavior is correct.

## Troubleshooting

If the marker is missing:

- Inspect the archive and confirm it contains `plugins/<generated name>.dll`.
- Confirm the assembly is under the existing `Modding` folder's `plugins` directory.
- Confirm BepInEx is installed and loading with Blasphemous 1.
- Check the new BepInEx log created by this launch.
