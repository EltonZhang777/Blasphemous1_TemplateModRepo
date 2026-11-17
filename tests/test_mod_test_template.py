import os
import platform
import re
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from path_safety import DotnetTestContext


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PROJECT = (
    REPO_ROOT
    / "Templates"
    / "Blasphemous1.ModTest.Templates"
    / "Blasphemous1.ModTest.Templates.csproj"
)
TEMPLATE_README = TEMPLATE_PROJECT.parent / "README.md"
ROOT_README = REPO_ROOT / "README.md"
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
CREATE_GUIDE = REPO_ROOT / "docs" / "create-mod-repository.md"
MIGRATION_GUIDE = REPO_ROOT / "docs" / "migrate-mod-repository.md"
MARKDOWN_LOCAL_LINK = re.compile(
    r"\[[^\]]+\]\((?!(?:https?://|mailto:))([^)]+)\)"
)


def local_link_targets(document):
    for line in markdown_prose(document):
        for match in MARKDOWN_LOCAL_LINK.finditer(line):
            relative_path, _, anchor = match.group(1).partition("#")
            if relative_path:
                target = document.parent / relative_path
            else:
                target = document
            yield target, anchor


def heading_anchors(document):
    counts = {}
    for line in markdown_prose(document):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not match:
            continue
        slug = re.sub(r"[`*_]", "", match.group(1)).strip().lower()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        yield slug if count == 0 else f"{slug}-{count}"


def markdown_prose(document):
    in_fence = False
    for line in document.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            yield line


def level_two_headings(document):
    return [
        line[3:].strip()
        for line in markdown_prose(document)
        if line.startswith("## ")
    ]


def markdown_section(document, start_heading, end_heading):
    text = document.read_text(encoding="utf-8")
    start = text.index(start_heading)
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def assert_ordered(test_case, text, markers):
    position = -1
    for marker in markers:
        next_position = text.find(marker, position + 1)
        test_case.assertNotEqual(
            -1,
            next_position,
            f"Missing documentation marker: {marker}",
        )
        test_case.assertGreater(
            next_position,
            position,
            f"Out-of-order documentation marker: {marker}",
        )
        position = next_position


def assert_local_links_resolve(test_case, sources):
    for source in sources:
        for target, anchor in local_link_targets(source):
            with test_case.subTest(source=source.name, target=str(target)):
                test_case.assertTrue(target.exists())
                if anchor:
                    test_case.assertIn(anchor, heading_anchors(target))


def assert_guide_contract(test_case, guide, root_link, headings):
    root_readme = ROOT_README.read_text(encoding="utf-8")
    test_case.assertIn(root_link, root_readme)
    test_case.assertTrue(guide.is_file())
    prose = "\n".join(markdown_prose(guide))
    for heading in headings:
        test_case.assertIn(f"\n## {heading}\n", prose)


class ModTestTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if platform.system() != "Windows":
            raise unittest.SkipTest("The Blasphemous Mod toolchain is validated on Windows.")

        cls.dotnet = shutil.which("dotnet")
        if not cls.dotnet:
            raise unittest.SkipTest("dotnet was not found on PATH.")

        artifacts = REPO_ROOT / "tmp"
        artifacts.mkdir(parents=True, exist_ok=True)
        cls.root = Path(
            tempfile.mkdtemp(prefix="blasmodtest-template-", dir=str(artifacts))
        )
        cls.hive = cls.root / "hive"
        cls.packages = cls.root / "packages"
        cls.packages.mkdir()
        shutil.copy2(REPO_ROOT / "TemplateRepo" / "NuGet.Config", cls.root / "NuGet.Config")
        cls.environment = os.environ.copy()
        cls.environment.update(
            {
                "DOTNET_CLI_HOME": str(cls.hive),
                "DOTNET_NOLOGO": "1",
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "PYTHONUTF8": "1",
            }
        )

        cls.path_context = DotnetTestContext(cls.hive)
        cls.path_context.start()
        try:
            packed = cls.run_dotnet(
                [
                    "pack",
                    str(TEMPLATE_PROJECT),
                    "--configuration",
                    "Release",
                    "--output",
                    str(cls.packages),
                ],
                REPO_ROOT,
            )
            if packed.returncode != 0:
                raise AssertionError(packed.stdout + packed.stderr)
            cls.package = next(
                cls.packages.glob("Blasphemous1.ModTest.Templates.*.nupkg")
            )
            installed = cls.run_dotnet(
                ["new", "install", str(cls.package)], cls.root
            )
            if installed.returncode != 0:
                raise AssertionError(installed.stdout + installed.stderr)
            cls.install_output = installed.stdout + installed.stderr
        except BaseException:
            cls.path_context.finish()
            raise

    @classmethod
    def tearDownClass(cls):
        cls.path_context.finish()

    @classmethod
    def run_dotnet(cls, arguments, cwd):
        return subprocess.run(
            [cls.dotnet, *arguments],
            cwd=str(cwd),
            env=cls.environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def generate(self, name, output, title, author, target=None):
        arguments = [
            "new",
            "blasmodtest",
            "-n",
            name,
            "-o",
            str(output),
            "-ti",
            title,
            "-au",
            author,
        ]
        if target is not None:
            arguments.extend(["-ta", str(target)])
        return self.run_dotnet(arguments, self.root)

    def build(self, project):
        return self.run_dotnet(["build", str(project)], project.parent)

    def package_entries(self, package):
        with zipfile.ZipFile(package) as archive:
            return set(archive.namelist())

    def test_requires_dotnet_sdk_10(self):
        version = self.run_dotnet(["--version"], REPO_ROOT)
        self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
        self.assertEqual(version.stdout.strip().split(".")[0], "10")

    def test_package_installs_with_expected_identity_and_short_name(self):
        self.assertIn("Blasphemous1.ModTest.Templates@0.1.0", self.install_output)
        self.assertIn("blasmodtest", self.install_output)

    def test_generated_project_builds_without_target(self):
        name = "Blasphemous.Verification.TestMod"
        output = self.root / "without-target"
        result = self.generate(
            name, output, "Verification Test Mod", "Test Author"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        project = output / f"{name}.csproj"
        self.assertTrue(project.is_file())
        self.assertTrue((output / "Main.cs").is_file())
        self.assertTrue((output / "ModInfo.cs").is_file())
        self.assertTrue((output / "TestMod.cs").is_file())
        self.assertFalse((output / "TargetProjectReference.props").exists())

        project_text = project.read_text(encoding="utf-8")
        self.assertIn("<TargetFramework>net35</TargetFramework>", project_text)
        self.assertIn('Blasphemous.GameLibs" Version="4.0.67"', project_text)
        self.assertNotIn("<ProjectReference", project_text)
        self.assertIn("<IsPackable>false</IsPackable>", project_text)
        mod_info = (output / "ModInfo.cs").read_text(encoding="utf-8")
        self.assertIn(f'internal const string ModId = "{name}"', mod_info)
        self.assertIn('internal const string ModName = "Verification Test Mod"', mod_info)
        self.assertIn('internal const string ModAuthor = "Test Author"', mod_info)
        self.assertIn("STARTUP_READY", (output / "Main.cs").read_text(encoding="utf-8"))

        built = self.build(project)
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        package = output / "publish" / f"{name}.zip"
        self.assertEqual(
            self.package_entries(package), {f"plugins/{name}.dll"}
        )

    def test_metadata_special_characters_are_escaped(self):
        name = "Blasphemous.Verification.EscapedMetadata"
        output = self.root / "escaped-metadata"
        result = self.generate(
            name,
            output,
            'A & B "C" \\ D',
            'R&D "Author"',
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        mod_info = (output / "ModInfo.cs").read_text(encoding="utf-8")
        self.assertIn(
            'internal const string ModName = "A & B \\"C\\" \\\\ D";',
            mod_info,
        )
        self.assertIn(
            'internal const string ModAuthor = "R&D \\"Author\\"";',
            mod_info,
        )

        built = self.build(output / f"{name}.csproj")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

    def test_target_project_is_referenced_and_packaged(self):
        target_dir = self.root / "target-lib & tools"
        target_dir.mkdir()
        (target_dir / "TargetLib.csproj").write_text(
            """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <TargetFramework>net35</TargetFramework>
    <LangVersion>latest</LangVersion>
    <AssemblyName>TargetLib</AssemblyName>
    <AppendTargetFrameworkToOutputPath>false</AppendTargetFrameworkToOutputPath>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net35" Version="1.0.3" PrivateAssets="all" />
  </ItemGroup>
</Project>
""",
            encoding="utf-8",
        )
        (target_dir / "TargetApi.cs").write_text(
            """namespace TargetLib;

public static class TargetApi
{
    public static string Name => "TargetLib";
}
""",
            encoding="utf-8",
        )

        solution = self.root / "Existing.sln"
        solution.write_text("solution-marker", encoding="utf-8")
        name = "Blasphemous.Verification.TestMod"
        output = self.root / "with-target"
        target = Path("..") / "target-lib & tools" / "TargetLib.csproj"
        result = self.generate(
            name, output, "Verification Test Mod", "Test Author", target
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(solution.read_text(encoding="utf-8"), "solution-marker")

        optional = output / "TargetProjectReference.props"
        self.assertTrue(optional.is_file())
        optional_text = optional.read_text(encoding="utf-8")
        self.assertIn("TargetLib.csproj", optional_text)
        self.assertIn("&amp;", optional_text)

        built = self.build(output / f"{name}.csproj")
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        package = output / "publish" / f"{name}.zip"
        self.assertEqual(
            self.package_entries(package),
            {f"plugins/{name}.dll", "plugins/TargetLib.dll"},
        )

    def test_invalid_target_fails_with_clear_build_error(self):
        name = "Blasphemous.Verification.TestMod"
        output = self.root / "invalid-target"
        result = self.generate(
            name,
            output,
            "Verification Test Mod",
            "Test Author",
            Path("..") / "missing" / "Missing.csproj",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        built = self.build(output / f"{name}.csproj")
        self.assertNotEqual(built.returncode, 0)
        self.assertIn("Target project not found", built.stdout + built.stderr)


class TemplatePackageDocumentationTests(unittest.TestCase):
    def test_documentation_shows_manual_solution_wiring(self):
        readme = TEMPLATE_README.read_text(encoding="utf-8")
        self.assertIn("dotnet sln add", readme)


class RootDocumentationTests(unittest.TestCase):
    def test_guides_are_discoverable_and_complete(self):
        self.assertIn(
            "## Choose your path",
            ROOT_README.read_text(encoding="utf-8"),
        )
        assert_guide_contract(
            self,
            MIGRATION_GUIDE,
            "[Migrate an existing Mod repository]"
            "(docs/migrate-mod-repository.md)",
            (
                "Supported Inputs",
                "Record the Starting State and Prepare Recovery",
                "Inventory Before Editing",
                "Preserve Mod Identity",
                "Preserve the Existing Layout",
                "Classify Template Differences",
                "Apply Required Differences",
                "Structural Refactor Gate",
                "Reconcile CI and Release Semantics",
                "Verify and Record Migration Evidence",
                "Optional In-Game Smoke",
                "Rollback",
                "Stop States",
                "Completion Checklist",
            ),
        )
        assert_guide_contract(
            self,
            CREATE_GUIDE,
            "[Create a new Mod repository](docs/create-mod-repository.md)",
            (
                "Prerequisites",
                "Install the Official Template Baseline",
                "Create the Mod Repository",
                "Expected Result",
                "Verify and Record Creation Evidence",
                "Optional Verification Mod",
                "Recover from Common Failures",
                "Stop Before Git",
                "Completion Checklist",
            ),
        )

    def test_documentation_links_resolve_locally(self):
        assert_local_links_resolve(
            self,
            (ROOT_README, CREATE_GUIDE, MIGRATION_GUIDE, ROOT_AGENTS),
        )

    def test_migration_deployment_safety_order(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")
        probe_build = (
            "dotnet build $solution --configuration Release "
            "--no-restore --no-incremental"
        )

        self.assertEqual(text.find("dotnet build "), text.find(probe_build))
        self.assertNotEqual(-1, text.find("dotnet build "))
        assert_ordered(
            self,
            text,
            (
                "### Inspect Deployment Targets Before the First Build",
                "rg --no-ignore --hidden -n -i",
                r"<Copy\b",
                r"<WriteLinesToFile\b",
                r"<Move\b",
                r"<RemoveDir\b",
                r"<RemoveDirectory\b",
                r"<Exec\b",
                "dotnet restore $solution",
                '-p:DeployToGame=false -p:DevFolder="$probe"',
                "$probeEntries.Count -ne 0",
                "dotnet build $solution --configuration Release --no-restore "
                "-p:Version=1.2.3",
                "dotnet test $solution --configuration Release --no-build",
            ),
        )
        self.assertIn(
            "dotnet build $solution --configuration Release --no-restore "
            '--no-incremental `\n  -p:Version=1.2.3 -p:DeployToGame=true '
            '-p:DevFolder="$devFolder"',
            text,
        )
        self.assertNotIn(
            "dotnet build $mainProject --configuration Release --no-restore "
            "--no-incremental",
            text,
        )

    def test_migration_backup_and_restore_path_safety(self):
        backup = markdown_section(
            MIGRATION_GUIDE,
            "### Non-Git repository",
            "## Inventory Before Editing",
        )
        restore = markdown_section(
            MIGRATION_GUIDE,
            "### Non-Git restore",
            "## Stop States",
        )

        self.assertIn("function Assert-NoReparsePointAncestor", backup)
        self.assertIn("Get-Item -LiteralPath $path -Force", backup)
        self.assertIn("[IO.FileAttributes]::ReparsePoint", backup)
        self.assertIn("Assert-NoReparsePointAncestor $candidate", backup)
        self.assertIn(
            "Resolve repository reparse points before backup",
            backup,
        )
        self.assertLess(
            backup.find("Assert-NoReparsePointAncestor $candidate"),
            backup.find("New-Item -ItemType Directory"),
        )
        self.assertLess(
            backup.find("Resolve repository reparse points before backup"),
            backup.find("New-Item -ItemType Directory"),
        )

        for marker in (
            "Assert-NoReparsePointAncestor $repo",
            "Assert-NoReparsePointAncestor $backupRoot",
            "Assert-NoReparsePointAncestor $backup",
            "Resolve repository reparse points before restore",
        ):
            self.assertIn(marker, restore)
        self.assertLess(
            restore.find("Assert-NoReparsePointAncestor $repo"),
            restore.find("1. Verify the backup"),
        )
        for marker in (
            "repository-manifest.json",
            "$referenceManifest",
            "Compare-Object",
            "Restore: TESTED",
            "Restore: NOT RUN",
        ):
            self.assertIn(marker, restore)

    def test_migration_inventory_and_powershell_placeholders(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")

        for marker in (
            "rg --files --hidden",
            "Get-ChildItem -LiteralPath .github\\workflows -File -Force",
            "dotnet sln '<solution-path>' add '<test-project-path>'",
            "dotnet sln '<solution-path>' list",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("dotnet sln <solution-path>", text)

    def test_migration_partial_is_not_ticket_closure(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")

        self.assertIn("not a GitHub issue-closure state", text)
        self.assertIn(
            "requires the exact HEAD plus matching evidence",
            text,
        )

    def test_creation_guide_matches_generated_output(self):
        text = CREATE_GUIDE.read_text(encoding="utf-8")
        expected_result = markdown_section(
            CREATE_GUIDE,
            "## Expected Result",
            "## Verify and Record Creation Evidence",
        )

        for marker in ("|-- Example.cs", "|-- Main.cs", "|-- ModInfo.cs"):
            self.assertIn(marker, expected_result)
        self.assertIn("`Example.cs` contains the generated Mod class", text)
        self.assertIn("plugins/Example.dll", text)
        self.assertIn("plugins/Blasphemous.Example.TestMod.dll", text)
        self.assertNotIn("plugins\\Example.dll", text)
        self.assertNotIn("plugins\\Blasphemous.Example.TestMod.dll", text)

    def test_user_and_maintainer_ownership_boundary(self):
        readme = ROOT_README.read_text(encoding="utf-8")
        agents = ROOT_AGENTS.read_text(encoding="utf-8")
        readme_lines = readme.splitlines()
        h1_index = readme_lines.index("# Blasphemous1_TemplateModRepo")
        first_h2_index = next(
            index
            for index, line in enumerate(readme_lines)
            if line.startswith("## ")
        )
        self.assertTrue(
            "".join(readme_lines[h1_index + 1:first_h2_index]).strip()
        )
        readme_headings = level_two_headings(ROOT_README)
        agents_headings = level_two_headings(ROOT_AGENTS)

        self.assertEqual(
            [
                "Clone the Repository",
                "Prerequisites",
                "Choose your path",
                "Contributing",
                "License",
            ],
            readme_headings,
        )
        self.assertIn(
            "git clone https://github.com/EltonZhang777/"
            "Blasphemous1_TemplateModRepo.git",
            readme,
        )
        self.assertIn(
            "[GitHub Issues](https://github.com/EltonZhang777/"
            "Blasphemous1_TemplateModRepo/issues)",
            readme,
        )
        self.assertIn("[LICENSE](LICENSE)", readme)
        for marker in (
            "dotnet new install Blasphemous.Modding.Templates",
            "dotnet pack .\\Templates",
            "python -m unittest discover",
            "BLAS1_DISPOSABLE_TEST_CONTEXT",
            "DeployToGame",
            "blasmodtest",
            "dotnet sln add",
            "AGENTS.md",
            "AGENTS.local.md",
            "GLOSSARY.md",
            "docs/adr",
            "docs/agents",
        ):
            self.assertNotIn(marker, readme)

        for heading in (
            "Documentation ownership",
            "Language",
            "Issue and domain workflow",
            "Maintainer checks",
            "Test Template Package",
        ):
            self.assertIn(heading, agents_headings)
        for marker in (
            "python -m unittest discover -s tests -v",
            "BLAS1_DISPOSABLE_TEST_CONTEXT",
            "Disposable Test Context",
            "dotnet pack .\\Templates\\Blasphemous1.ModTest.Templates",
            "Get-ChildItem .\\Templates\\Blasphemous1.ModTest.Templates",
            "dotnet new install $package.FullName",
            "blasmodtest",
            "dotnet sln add",
            "docs/agents/issue-tracker.md",
            "docs/agents/triage-labels.md",
            "docs/agents/domain.md",
            "GLOSSARY.md",
            "docs/adr/",
            "AGENTS.local.md",
            "Templates/Blasphemous1.ModTest.Templates/README.md",
        ):
            self.assertIn(marker, agents)
        self.assertNotIn("](AGENTS.local.md)", agents)


if __name__ == "__main__":
    unittest.main()
