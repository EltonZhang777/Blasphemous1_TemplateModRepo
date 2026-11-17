# Blasphemous1_TemplateModRepo

A non-vendored repository generator for Blasphemous 1 Mod development. It
creates a new Mod repository from the Official Template Baseline or migrates an
existing repository in place while preserving its Mod Identity and layout.

This repository also maintains the standalone `Blasphemous1.ModTest.Templates`
package, which adds a Verification Mod to an existing repository; that project
is separate from the generated Mod and its main Mod Package.

## Clone the Repository

```powershell
git clone https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo.git
Set-Location .\Blasphemous1_TemplateModRepo
```

## Prerequisites

Use a Windows machine with:

- .NET SDK 10.
- Python 3.9 or later.
- Git.
- NuGet access to restore the Official Template Baseline and generated
  projects.

Open a new PowerShell window after installation and verify the required tools:

```powershell
[System.Environment]::OSVersion.Version
dotnet --version
python --version
git --version
```

The operating system must be Windows, `dotnet --version` must start with `10.`,
and Python must report version 3.9 or later.

## Choose your path

- [Create a new Mod repository](docs/create-mod-repository.md) from the
  Official Template Baseline.
- [Migrate an existing Mod repository](docs/migrate-mod-repository.md) in
  place.

## Contributing

Report bugs and request features through
[GitHub Issues](https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo/issues).
Include the command, full error output, and steps needed to reproduce the
problem.

## License

This repository uses the MIT License; see [LICENSE](LICENSE).
