# Blasphemous1_TemplateModRepo

This repository is the shared setup entry point for Blasphemous 1 Mod repository development. The Generator Command creates new Mod repositories only. Existing repositories use the in-place migration path.

## Prerequisites

These are the common host prerequisites for the creation and migration paths.

Use a Windows machine with:

- .NET SDK 10.
- Python 3.9 or later.
- Git.
- NuGet access to restore the Official Template Baseline and generated projects.

Open a new PowerShell window after installation and verify the required tools:

```powershell
[System.Environment]::OSVersion.Version
dotnet --version
python --version
git --version
```

The operating system must be Windows, `dotnet --version` must start with `10.`, and Python must report version 3.9 or later.

## Clone the Repository

```powershell
git clone https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo.git
Set-Location .\Blasphemous1_TemplateModRepo
```

## Choose your path

- [Create a new Mod repository](docs/create-mod-repository.md) from the Official Template Baseline.
- [Migrate an existing Mod repository](docs/migrate-mod-repository.md) in place. Migration preserves Mod Identity and layout by default and permits only an approved structural refactor required by a failing gate.

For a supplemental verification path, see the [Test Template Package verification journey](Templates/Blasphemous1.ModTest.Templates/README.md).

## Contributing

Report bugs and request features through [GitHub Issues](https://github.com/EltonZhang777/Blasphemous1_TemplateModRepo/issues). Include the command, full error output, and steps needed to reproduce the problem.

## License

This repository uses the MIT License; see [LICENSE](LICENSE).
