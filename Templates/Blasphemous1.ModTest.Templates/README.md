# Blasphemous 1 Mod Test template

`blasmodtest` adds a `net35` verification Mod to an existing Blasphemous 1 Mod or class-library repository.

## Install and generate

```powershell
dotnet new install Blasphemous1.ModTest.Templates

dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  --title "Example Mod Test" `
  -au "Example Author"
```

The generated project references the Blasphemous ModdingAPI `3.0.1` and GameLibs `4.0.67`. It logs `STARTUP_READY` with its own Mod ID once the verification Mod is constructed.

## Reference an existing project

Pass `--targetProject` with an absolute path or a path relative to the generated project:

```powershell
dotnet new blasmodtest -n Blasphemous.Example.TestMod `
  -o .\Blasphemous.Example.TestMod `
  --title "Example Mod Test" `
  -au "Example Author" `
  --targetProject ..\Blasphemous.Example\Blasphemous.Example.csproj
```

The target project is added as a normal `ProjectReference`. Building the verification Mod creates `publish\<project>.zip` with both assemblies under `plugins/`. Without a target project, the ZIP contains only the verification Mod.

An invalid target path fails the build with `Target project not found`.

## Wire the solution manually

The template writes only the new project and its source files. Add it to the existing solution yourself:

```powershell
dotnet sln add .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
dotnet build .\Blasphemous.Example.TestMod\Blasphemous.Example.TestMod.csproj
```

The existing repository must already configure the NuGet sources required by `Blasphemous.ModdingAPI` and `Blasphemous.GameLibs`.
