import importlib.util
import json
import os
import platform
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from workflow_contract import assert_nuget_release_guards, workflow_step


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "tools" / "new_blas1mod.py"
DEFAULT_PACKAGE = (
    Path.home()
    / ".templateengine"
    / "packages"
    / "Blasphemous.Modding.Templates.1.4.1.nupkg"
)
PACKAGE = Path(os.environ.get("BLAS1_TEMPLATE_PACKAGE", DEFAULT_PACKAGE))
# Only 4.0.67 is published; metadata keeps the override distinct and restorable.
CUSTOM_GAME_VERSION = "4.0.67+tests"
WRONG_PACKAGE = Path(
    os.environ.get(
        "BLAS1_WRONG_TEMPLATE_PACKAGE",
        DEFAULT_PACKAGE.with_name("Blasphemous.Modding.Templates.1.4.0.nupkg"),
    )
)
def load_wrapper_module():
    spec = importlib.util.spec_from_file_location("new_blas1mod", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class WrapperTests(unittest.TestCase):
    def setUp(self):
        artifacts = REPO_ROOT / "tmp"
        artifacts.mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="blas1-wrapper-", dir=str(artifacts)))
        self.hive = self.root / "hive"

    def environment(self):
        env = os.environ.copy()
        env.update(
            {
                "DOTNET_CLI_HOME": str(self.hive),
                "DOTNET_NOLOGO": "1",
                "DOTNET_CLI_TELEMETRY_OPTOUT": "1",
                "PYTHONUTF8": "1",
            }
        )
        return env

    def run_wrapper(self, *args):
        return subprocess.run(
            [sys.executable, str(WRAPPER), *args],
            cwd=str(self.root),
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def install_template_package(self, package):
        self.assertEqual(platform.system(), "Windows")
        self.assertTrue(
            package.is_file(),
            f"Template package not found: {package}",
        )
        version = subprocess.run(
            ["dotnet", "--version"],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(version.returncode, 0, version.stdout + version.stderr)
        self.assertEqual(version.stdout.strip().split(".")[0], "10")
        result = subprocess.run(
            ["dotnet", "new", "install", str(package)],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def install_official_template(self):
        self.install_template_package(PACKAGE)

    def test_missing_template_fails_before_output_creation(self):
        output = self.root / "Blasphemous.Missing"
        result = self.run_wrapper(
            "--name",
            "Missing",
            "--title",
            "Missing Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
        )

        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertIn("Blasphemous.Modding.Templates::1.4.1", result.stdout)

    def test_real_wrong_template_version_fails_before_output_creation(self):
        if not WRONG_PACKAGE.is_file():
            raise unittest.SkipTest(
                "Set BLAS1_WRONG_TEMPLATE_PACKAGE to an official 1.4.0 template package"
            )
        self.install_template_package(WRONG_PACKAGE)
        output = self.root / "Blasphemous.WrongVersion"
        result = self.run_wrapper(
            "--name",
            "WrongVersion",
            "--title",
            "Wrong Version Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
        )

        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())
        self.assertIn("Blasphemous.Modding.Templates::1.4.1", result.stdout)

    def test_template_version_gate_rejects_mismatch(self):
        wrapper = load_wrapper_module()
        fake = SimpleNamespace(
            returncode=0,
            stdout=(
                "Currently installed items:\n"
                "   Blasphemous.Modding.Templates\n"
                "      Version: 1.4.0\n"
            ),
            stderr="",
        )
        output = StringIO()
        with mock.patch.object(wrapper, "run", return_value=fake), redirect_stdout(
            output
        ):
            accepted = wrapper.check_template("dotnet")

        self.assertFalse(accepted)
        self.assertIn("Blasphemous.Modding.Templates::1.4.1", output.getvalue())

    def test_invalid_identity_is_rejected_before_output_creation(self):
        self.install_official_template()
        invalid_names = (
            "x",
            "1Mod",
            "CON",
            "ModTemplate",
            "TemplateMod",
            "Main",
            "ModInfo",
        )
        for name in invalid_names:
            with self.subTest(name=name):
                output = self.root / f"Blasphemous.{name}"
                result = self.run_wrapper(
                    "--name",
                    name,
                    "--title",
                    "Invalid Mod",
                    "--author",
                    "Test Author",
                    "--output",
                    str(output),
                )

                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())

    def test_invalid_text_and_output_paths_are_rejected_before_creation(self):
        self.install_official_template()
        cases = (
            ("--title", "", "Blasphemous.EmptyTitle"),
            ("--title", "@AUTHOR@", "Blasphemous.TokenTitle"),
            ("--title", "Template Mod", "Blasphemous.ReservedTitle"),
            ("--title", "MOD_TITLE_PLACEHOLDER", "Blasphemous.TemplateTitleToken"),
            ("--title", "TARGET_PROJECT_PLACEHOLDER", "Blasphemous.TargetToken"),
            ("--title", "Blasphemous1.ModTest", "Blasphemous.TemplateIdentity"),
            ("--title", "$(Version)", "Blasphemous.PropertyTitle"),
            ("--title", "A%0AB", "Blasphemous.PercentTitle"),
            ("--title", "Bidi\u202eText", "Blasphemous.BidiTitle"),
            ("--title", "A\uFFFE B", "Blasphemous.NoncharacterTitle"),
            ("--title", "\u200d", "Blasphemous.InvisibleTitle"),
            ("--title", "Line\u2028Break", "Blasphemous.UnicodeSeparatorTitle"),
            ("--title", "Trailing\n", "Blasphemous.TrailingLineBreakTitle"),
            ("--author", " ", "Blasphemous.EmptyAuthor"),
            ("--author", "Line\nBreak", "Blasphemous.LineBreak"),
            ("--author", "Line\u2029Break", "Blasphemous.UnicodeSeparatorAuthor"),
            ("--author", "\tLeading", "Blasphemous.LeadingTabAuthor"),
            ("--author", "A%09B", "Blasphemous.PercentAuthor"),
            ("--author", "Bidi\u2066Text", "Blasphemous.BidiAuthor"),
            ("--author", "A\uFFFF B", "Blasphemous.NoncharacterAuthor"),
            ("--author", "\u200c", "Blasphemous.InvisibleAuthor"),
            ("--author", "@TITLE@", "Blasphemous.TokenAuthor"),
            ("--author", "Template Author", "Blasphemous.ReservedAuthor"),
            ("--author", "MOD_AUTHOR_PLACEHOLDER", "Blasphemous.TemplateAuthorToken"),
            ("--author", "$(Version)", "Blasphemous.PropertyAuthor"),
        )
        for argument, value, output_name in cases:
            with self.subTest(argument=argument, value=value):
                output = self.root / output_name
                args = [
                    "--name",
                    "Valid",
                    "--title",
                    "Valid Mod",
                    "--author",
                    "Valid Author",
                    "--output",
                    str(output),
                ]
                args[args.index(argument) + 1] = value
                result = self.run_wrapper(*args)

                self.assertEqual(result.returncode, 2)
                self.assertFalse(output.exists())

        parent_file = self.root / "not-a-directory"
        parent_file.write_text("file", encoding="utf-8")
        output = parent_file / "Blasphemous.InvalidParent"
        result = self.run_wrapper(
            "--name",
            "Valid",
            "--title",
            "Valid Mod",
            "--author",
            "Valid Author",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_display_text_accepts_unicode_joiners_and_combining_marks(self):
        wrapper = load_wrapper_module()
        for value in ("می\u200cخواهم", "👩\u200d💻", "Cafe\u0301"):
            with self.subTest(value=value):
                self.assertEqual(
                    value, wrapper.validate_display_text(value, "Display Title")
                )

    def test_existing_output_is_refused_without_modification(self):
        output = self.root / "Blasphemous.Existing"
        output.mkdir()
        marker = output / "keep.txt"
        marker.write_text("keep", encoding="utf-8")

        result = self.run_wrapper(
            "--name",
            "Existing",
            "--title",
            "Existing Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
        )

        self.assertEqual(result.returncode, 2)
        self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_version_parser_rejects_mismatched_installation(self):
        wrapper = load_wrapper_module()
        output = (
            "Currently installed items:\n"
            "   Blasphemous.Modding.Templates\n"
            "      Version: 1.4.0\n"
        )

        self.assertNotIn("1.4.1", wrapper.parse_installed_versions(output))

    def test_version_parser_ignores_uninstall_and_other_templates(self):
        wrapper = load_wrapper_module()
        output = (
            "Currently installed items:\n"
            "   Blasphemous.Modding.Templates\n"
            "      Version: 1.4.1\n"
            "      Templates:\n"
            "         Blasphemous Mod (blas1mod) C#\n"
            "      Uninstall Command:\n"
            "         dotnet new uninstall Blasphemous.Modding.Templates\n"
            "\n"
            "   BepInEx.Templates\n"
            "      Version: 2.0.0-be.4\n"
            "      Details:\n"
            "         Author: BepInEx\n"
        )

        self.assertEqual(
            wrapper.parse_installed_versions(output), ["1.4.1"]
        )

    def test_valid_generation_modernizes_identity_and_deployment(self):
        self.install_official_template()
        output = self.root / "Blasphemous.Example"
        result = self.run_wrapper(
            "--name",
            "Example",
            "--title",
            "My Mod Template",
            "--author",
            "Example Author",
            "--output",
            str(output),
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project = output / "Blasphemous.Example.csproj"
        main = output / "Main.cs"
        self.assertTrue(project.is_file())
        self.assertTrue(main.is_file())
        self.assertTrue((output / "PackageMod.targets").is_file())
        self.assertTrue((output / "Blasphemous.Example.sln").is_file())
        self.assertTrue(
            (output / "Blasphemous.Example.Tests" / "Blasphemous.Example.Tests.csproj").is_file()
        )
        self.assertTrue(
            (output / "Blasphemous.Example.Tests" / "ModMetadataTests.cs").is_file()
        )
        self.assertTrue((output / "resources").is_dir())
        self.assertTrue((output / "README.md").is_file())
        self.assertTrue((output / "AGENTS.md").is_file())
        self.assertTrue((output / ".editorconfig").is_file())
        self.assertTrue((output / ".gitattributes").is_file())
        self.assertTrue((output / ".gitignore").is_file())
        self.assertIn(
            "*.cs text eol=crlf",
            (output / ".gitattributes").read_text(encoding="utf-8"),
        )
        self.assertTrue((output / ".worktreeinclude").is_file())
        self.assertTrue((output / "dotnet_format.bat").is_file())
        self.assertTrue((output / ".config" / "wt.toml").is_file())
        self.assertTrue((output / "docs" / "agents" / "domain.md").is_file())
        self.assertTrue((output / "docs" / "agents" / "issue-tracker.md").is_file())
        self.assertTrue((output / "docs" / "agents" / "triage-labels.md").is_file())
        workflow_dir = output / ".github" / "workflows"
        self.assertTrue((workflow_dir / "build.yml").is_file())
        self.assertTrue((workflow_dir / "release.yml").is_file())
        self.assertTrue((workflow_dir / "discord.yml").is_file())
        self.assertTrue((output / "scripts" / "check-crlf.ps1").is_file())

        build_workflow = (workflow_dir / "build.yml").read_text(encoding="utf-8")
        self.assertIn("pull_request:", build_workflow)
        self.assertIn("branches: [main]", build_workflow)
        self.assertIn("contents: read", build_workflow)
        self.assertNotIn("contents: write", build_workflow)
        self.assertNotIn("id-token: write", build_workflow)
        self.assertIn("windows-latest", build_workflow)
        self.assertIn("dotnet-version: 10.0.x", build_workflow)
        self.assertIn("./scripts/check-crlf.ps1", build_workflow)
        self.assertIn("dotnet restore", build_workflow)
        build_step = workflow_step(build_workflow, "Build")
        self.assertIn("dotnet build", build_step)
        self.assertIn("-p:DeployToGame=false", build_step)
        self.assertIn("dotnet test", build_workflow)
        self.assertIn("dotnet format whitespace", build_workflow)
        self.assertIn("--severity warn", build_workflow)

        release_workflow = (workflow_dir / "release.yml").read_text(encoding="utf-8")
        self.assertIn('tags: ["**"]', release_workflow)
        self.assertIn("contents: write", release_workflow)
        self.assertIn("id-token: write", release_workflow)
        self.assertIn("NUGET_USERNAME", release_workflow)
        self.assertNotIn("continue-on-error", release_workflow)
        self.assertNotIn("secrets.NUGET_API_KEY", release_workflow)
        self.assertIn("git merge-base --is-ancestor", release_workflow)
        release_build_step = workflow_step(release_workflow, "Build")
        self.assertIn("-p:DeployToGame=false", release_build_step)
        draft_step = workflow_step(release_workflow, "Create or update draft release")
        self.assertIn("if (-not $release.isDraft)", draft_step)
        self.assertIn("already published", draft_step)
        self.assertIn(
            'throw "Release $env:GITHUB_REF_NAME is already published."',
            draft_step,
        )
        self.assertIn(
            'gh release upload $env:GITHUB_REF_NAME "$env:ZIP_FILE" --clobber',
            draft_step,
        )
        self.assertIn("release not found", draft_step)
        self.assertIn("gh release create", draft_step)
        self.assertIn(
            "} else {\n            throw \"Could not inspect the existing release:",
            draft_step,
        )
        self.assertLess(
            draft_step.index("if (-not $release.isDraft)"),
            draft_step.index("gh release upload"),
        )
        self.assertLess(
            draft_step.index("already published."),
            draft_step.index("gh release upload"),
        )
        self.assertLess(
            draft_step.index("release not found"),
            draft_step.index("gh release create"),
        )
        self.assertLess(
            draft_step.index("gh release upload"),
            draft_step.rindex("if ($LASTEXITCODE -ne 0)"),
        )
        nuget_step = assert_nuget_release_guards(release_workflow)
        self.assertIn("--skip-duplicate", nuget_step)
        self.assertIn('Join-Path $PWD "publish" "$targetName.zip"', release_workflow)
        self.assertNotIn("*$targetName.zip", release_workflow)

        discord_workflow = (workflow_dir / "discord.yml").read_text(encoding="utf-8")
        self.assertIn("types: [published]", discord_workflow)
        self.assertIn("WEBHOOK_URL", discord_workflow)
        self.assertIn("if: env.WEBHOOK_URL == ''", discord_workflow)
        self.assertIn("::warning::", discord_workflow)
        self.assertIn("if: env.WEBHOOK_URL != ''", discord_workflow)
        self.assertIn("--fail-with-body", discord_workflow)
        self.assertIn("!github.event.release.prerelease", discord_workflow)

        project_text = project.read_text(encoding="utf-8")
        main_text = main.read_text(encoding="utf-8")
        self.assertIn('<TargetName>Example</TargetName>', project_text)
        self.assertIn('Blasphemous.ModdingAPI" Version="3.0.1"', project_text)
        self.assertIn('Blasphemous.GameLibs" Version="4.0.67"', project_text)
        self.assertIn("DeployToGame", project_text)
        self.assertNotIn("C:\\Program Files (x86)\\Steam", project_text)
        self.assertIn('BepInDependency("Blasphemous.ModdingAPI", "3.0.1")', main_text)
        self.assertNotIn("0.1.0", main_text)
        for placeholder in ("TemplateMod", "Template Mod", "Template Author"):
            self.assertNotIn(placeholder, project_text + main_text)

        test_project_text = (
            output / "Blasphemous.Example.Tests" / "Blasphemous.Example.Tests.csproj"
        ).read_text(encoding="utf-8")
        test_source = (output / "Blasphemous.Example.Tests" / "ModMetadataTests.cs").read_text(
            encoding="utf-8"
        )
        solution_text = (output / "Blasphemous.Example.sln").read_text(encoding="utf-8")
        self.assertIn("<TargetFramework>net48</TargetFramework>", test_project_text)
        self.assertIn("<IsPackable>false</IsPackable>", test_project_text)
        self.assertIn("Blasphemous.Example.csproj", test_project_text)
        self.assertIn(
            '"Blasphemous.Example", "Blasphemous.Example.csproj"', solution_text
        )
        self.assertIn(
            '"Blasphemous.Example.Tests", "Blasphemous.Example.Tests\\Blasphemous.Example.Tests.csproj"',
            solution_text,
        )
        self.assertIn("ModMetadataTests", test_source)
        self.assertIn("typeof(Blasphemous.Example.Example)", test_source)
        self.assertIn("dotnet test", (output / "README.md").read_text(encoding="utf-8"))
        self.assertIn(
            "DeployToGame",
            (output / "README.md").read_text(encoding="utf-8"),
        )
        self.assertIn(
            "DeployToGame",
            (output / "AGENTS.md").read_text(encoding="utf-8"),
        )
        for source in output.rglob("*.cs"):
            self.assertFalse(
                source.read_bytes().startswith(b"\xef\xbb\xbf"),
                str(source),
            )

        for path in output.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (
                ".cs",
                ".csproj",
                ".sln",
                ".md",
                ".xml",
                ".config",
                ".toml",
                ".bat",
                ".yml",
                ".ps1",
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for placeholder in (
                "TemplateMod",
                "Template Mod",
                "Template Author",
                "@PROJECT_NAME@",
                "@MACHINE_IDENTIFIER@",
                "@TITLE@",
                "@AUTHOR@",
            ):
                self.assertNotIn(placeholder, text, str(path))

    def test_custom_game_version_is_applied(self):
        self.install_official_template()
        output = self.root / "Blasphemous.Versioned"
        result = self.run_wrapper(
            "--name",
            "Versioned",
            "--title",
            "Versioned Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
            "--game-version",
            CUSTOM_GAME_VERSION,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project_text = (output / "Blasphemous.Versioned.csproj").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f'Blasphemous.GameLibs" Version="{CUSTOM_GAME_VERSION}"', project_text
        )

    def test_generated_mod_restores_and_builds(self):
        self.install_official_template()
        output = self.root / "Blasphemous.Buildable"
        title = 'A; </Product><Copyright>X</Copyright><Product>B & <T> "Q" \\ E'
        author = 'T </Authors><Company>Injected</Company><Authors> & "Author" \\ Team'
        result = self.run_wrapper(
            "--name",
            "Buildable",
            "--title",
            title,
            "--author",
            author,
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project_text = (output / "Blasphemous.Buildable.csproj").read_text(
            encoding="utf-8"
        )
        project_xml = ET.fromstring(project_text)
        for element_name, expected in (
            ("Title", title),
            ("Product", title),
            ("Authors", author),
            ("Company", author),
        ):
            self.assertEqual(
                [expected],
                [element.text for element in project_xml.iter(element_name)],
            )
        self.assertNotIn("<Copyright>Injected</Copyright>", project_text)
        self.assertNotIn("<Company>Injected</Company>", project_text)
        self.assertIn(
            'public const string MOD_VERSION = "$(Version)"%3B',
            project_text,
        )
        self.assertNotIn('MOD_NAME = "$(Product)"', project_text)
        mod_info_text = (output / "ModInfo.cs").read_text(encoding="utf-8")
        self.assertIn(
            f"public const string MOD_NAME = {json.dumps(title, ensure_ascii=False)};",
            mod_info_text,
        )
        self.assertIn(
            f"public const string MOD_AUTHOR = {json.dumps(author, ensure_ascii=False)};",
            mod_info_text,
        )
        test_text = (output / "Blasphemous.Buildable.Tests" / "ModMetadataTests.cs").read_text(
            encoding="utf-8"
        )
        self.assertIn(json.dumps(title, ensure_ascii=False), test_text)
        self.assertIn(json.dumps(author, ensure_ascii=False), test_text)

        env = self.environment()
        solution = output / "Blasphemous.Buildable.sln"
        restore = subprocess.run(
            ["dotnet", "restore", str(solution)],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(restore.returncode, 0, restore.stdout + restore.stderr)
        build = subprocess.run(
            [
                "dotnet",
                "build",
                str(solution),
                "--configuration",
                "Release",
                "--no-restore",
                "-p:Version=1.2.3",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        test = subprocess.run(
            [
                "dotnet",
                "test",
                str(solution),
                "--configuration",
                "Release",
                "--no-build",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(test.returncode, 0, test.stdout + test.stderr)
        format_whitespace = subprocess.run(
            [
                "dotnet",
                "format",
                "whitespace",
                str(solution),
                "--no-restore",
                "--verify-no-changes",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            format_whitespace.returncode,
            0,
            format_whitespace.stdout + format_whitespace.stderr,
        )
        format_style = subprocess.run(
            [
                "dotnet",
                "format",
                "style",
                str(solution),
                "--no-restore",
                "--severity",
                "warn",
                "--verify-no-changes",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(
            format_style.returncode,
            0,
            format_style.stdout + format_style.stderr,
        )

        nuget_output = output / "release-nuget"
        packed = subprocess.run(
            [
                "dotnet",
                "pack",
                str(output / "Blasphemous.Buildable.csproj"),
                "--configuration",
                "Release",
                "--no-build",
                "--output",
                str(nuget_output),
                "-p:PackageVersion=1.2.3",
            ],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(packed.returncode, 0, packed.stdout + packed.stderr)
        self.assertEqual(
            [path.name for path in nuget_output.glob("*.nupkg")],
            ["Blasphemous.Buildable.1.2.3.nupkg"],
        )

        package = output / "publish" / "Buildable.zip"
        self.assertTrue(package.is_file())
        import zipfile

        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
        self.assertIn("plugins/Buildable.dll", names)
        self.assertFalse(any(".Tests" in name for name in names))
        self.assertFalse((output / "Blasphemous.Buildable.TestMod").exists())

    def test_generated_crlf_gate_rejects_lf_sources(self):
        import shutil

        self.install_official_template()
        output = self.root / "Blasphemous.CrlfGate"
        result = self.run_wrapper(
            "--name",
            "CrlfGate",
            "--title",
            "CRLF Gate",
            "--author",
            "Test Author",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        pwsh = shutil.which("pwsh")
        self.assertIsNotNone(pwsh)
        subprocess.run(
            ["git", "init", "--quiet", str(output)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(output),
                "-c",
                "user.name=Wrapper Tests",
                "-c",
                "user.email=wrapper-tests@example.invalid",
                "add",
                ".",
            ],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(output),
                "-c",
                "user.name=Wrapper Tests",
                "-c",
                "user.email=wrapper-tests@example.invalid",
                "commit",
                "--quiet",
                "-m",
                "baseline",
            ],
            check=True,
            capture_output=True,
        )

        script = output / "scripts" / "check-crlf.ps1"
        accepted = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(script)],
            cwd=str(output),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stdout + accepted.stderr)

        main = output / "Main.cs"
        main.write_bytes(main.read_bytes().replace(b"\r\n", b"\n"))
        rejected = subprocess.run(
            [pwsh, "-NoProfile", "-File", str(script)],
            cwd=str(output),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("Main.cs", rejected.stdout + rejected.stderr)

    def test_main_release_zip_is_exact_when_name_ends_with_testmod(self):
        import zipfile

        self.install_official_template()
        output = self.root / "Blasphemous.TestMod"
        result = self.run_wrapper(
            "--name",
            "TestMod",
            "--title",
            "Test Mod Name",
            "--author",
            "Test Author",
            "--output",
            str(output),
            "--with-test-mod",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        test_mod_project_text = (
            output
            / "Blasphemous.TestMod.TestMod"
            / "Blasphemous.TestMod.TestMod.csproj"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'Blasphemous.GameLibs" Version="4.0.67"', test_mod_project_text
        )

        solution = output / "Blasphemous.TestMod.sln"
        built = subprocess.run(
            ["dotnet", "build", str(solution), "--configuration", "Release"],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)

        main_zip = output / "publish" / "TestMod.zip"
        verification_zip = (
            output
            / "Blasphemous.TestMod.TestMod"
            / "publish"
            / "Blasphemous.TestMod.TestMod.zip"
        )
        self.assertTrue(main_zip.is_file())
        self.assertTrue(verification_zip.is_file())
        with zipfile.ZipFile(main_zip) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {".gitkeep", "plugins/TestMod.dll"},
            )

        release_workflow = (
            output / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")
        self.assertIn('Join-Path $PWD "publish" "$targetName.zip"', release_workflow)

    def test_with_test_mod_generates_and_packages_separate_plugin(self):
        import zipfile

        self.install_official_template()
        output = self.root / "Blasphemous.WithTest"
        title = '验证; </Product> & "Q" \\'
        author = '作者 </Authors> & "A" \\ Team'
        result = self.run_wrapper(
            "--name",
            "WithTest",
            "--title",
            title,
            "--author",
            author,
            "--output",
            str(output),
            "--with-test-mod",
            "--game-version",
            CUSTOM_GAME_VERSION,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        project_name = "Blasphemous.WithTest"
        test_mod_name = f"{project_name}.TestMod"
        test_mod_dir = output / test_mod_name
        test_mod_project = test_mod_dir / f"{test_mod_name}.csproj"
        test_mod_props = test_mod_dir / "TargetProjectReference.props"
        solution_text = (output / f"{project_name}.sln").read_text(
            encoding="utf-8"
        )
        main_project_text = (output / f"{project_name}.csproj").read_text(
            encoding="utf-8"
        )
        test_mod_project_text = test_mod_project.read_text(encoding="utf-8")
        self.assertTrue(test_mod_project.is_file())
        self.assertTrue((test_mod_dir / "Main.cs").is_file())
        self.assertTrue((test_mod_dir / "ModInfo.cs").is_file())
        self.assertTrue(test_mod_props.is_file())
        self.assertFalse((test_mod_dir / ".template.config").exists())
        test_mod_info = (test_mod_dir / "ModInfo.cs").read_text(encoding="utf-8")
        self.assertIn(
            f"internal const string ModName = {json.dumps(title, ensure_ascii=False)};",
            test_mod_info,
        )
        self.assertIn(
            f"internal const string ModAuthor = {json.dumps(author, ensure_ascii=False)};",
            test_mod_info,
        )
        self.assertIn(
            f'"{test_mod_name}", "{test_mod_name}\\{test_mod_name}.csproj"',
            solution_text,
        )
        self.assertIn(f"<Compile Remove=\"{test_mod_name}/**/*.cs\" />", main_project_text)
        self.assertIn(
            f'Blasphemous.GameLibs" Version="{CUSTOM_GAME_VERSION}"',
            main_project_text,
        )
        self.assertIn(
            f'Blasphemous.GameLibs" Version="{CUSTOM_GAME_VERSION}"',
            test_mod_project_text,
        )
        self.assertIn("../Blasphemous.WithTest.csproj", test_mod_props.read_text(encoding="utf-8"))

        solution = output / f"{project_name}.sln"
        restored = subprocess.run(
            ["dotnet", "restore", str(solution)],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(restored.returncode, 0, restored.stdout + restored.stderr)
        built = subprocess.run(
            ["dotnet", "build", str(solution), "--no-restore"],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
        tested = subprocess.run(
            ["dotnet", "test", str(solution), "--no-build"],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(tested.returncode, 0, tested.stdout + tested.stderr)
        for format_args in (
            ("whitespace",),
            ("style", "--severity", "warn"),
        ):
            formatted = subprocess.run(
                [
                    "dotnet",
                    "format",
                    *format_args,
                    str(solution),
                    "--no-restore",
                    "--verify-no-changes",
                ],
                env=self.environment(),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(
                formatted.returncode,
                0,
                formatted.stdout + formatted.stderr,
            )

        main_package = output / "publish" / "WithTest.zip"
        test_mod_package = test_mod_dir / "publish" / f"{test_mod_name}.zip"
        with zipfile.ZipFile(main_package) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {".gitkeep", "plugins/WithTest.dll"},
            )
        with zipfile.ZipFile(test_mod_package) as archive:
            self.assertEqual(
                set(archive.namelist()),
                {
                    f"plugins/{test_mod_name}.dll",
                    "plugins/WithTest.dll",
                },
            )

        main_dll = output / "bin" / "Debug" / "WithTest.dll"
        self.assertNotIn(b"Blasphemous.WithTest.TestMod", main_dll.read_bytes())
        nuget_output = output / "main-nuget"
        packed = subprocess.run(
            [
                "dotnet",
                "pack",
                str(output / f"{project_name}.csproj"),
                "--configuration",
                "Debug",
                "--output",
                str(nuget_output),
            ],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(packed.returncode, 0, packed.stdout + packed.stderr)
        main_nupkg = next(nuget_output.glob("*.nupkg"))
        with zipfile.ZipFile(main_nupkg) as archive:
            self.assertFalse(any("TestMod" in name for name in archive.namelist()))

    def test_with_test_mod_generation_does_not_touch_surrounding_git_metadata(self):
        self.install_official_template()
        self.root.joinpath(".git").mkdir()
        marker = self.root / ".git" / "marker"
        marker.write_text("untouched", encoding="utf-8")
        output = self.root / "Blasphemous.NoGit"

        result = self.run_wrapper(
            "--name",
            "NoGit",
            "--title",
            "No Git Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
            "--with-test-mod",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "untouched")
        self.assertFalse((output / ".git").exists())

        plain_root = Path(tempfile.mkdtemp(prefix="blas1-no-git-"))
        plain_output = plain_root / "Blasphemous.NoGit"
        plain = self.run_wrapper(
            "--name",
            "NoGit",
            "--title",
            "No Git Mod",
            "--author",
            "Test Author",
            "--output",
            str(plain_output),
            "--with-test-mod",
        )
        self.assertEqual(plain.returncode, 0, plain.stdout + plain.stderr)
        self.assertFalse((plain_output / ".git").exists())
        git_files = sorted(
            str(path.relative_to(output))
            for path in output.rglob("*")
            if path.is_file()
        )
        plain_files = sorted(
            str(path.relative_to(plain_output))
            for path in plain_output.rglob("*")
            if path.is_file()
        )
        self.assertEqual(git_files, plain_files)


if __name__ == "__main__":
    unittest.main()
