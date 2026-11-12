import importlib.util
import os
import platform
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER = REPO_ROOT / "tools" / "new_blas1mod.py"
DEFAULT_PACKAGE = (
    Path.home()
    / ".templateengine"
    / "packages"
    / "Blasphemous.Modding.Templates.1.4.1.nupkg"
)
PACKAGE = Path(os.environ.get("BLAS1_TEMPLATE_PACKAGE", DEFAULT_PACKAGE))


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

    def install_official_template(self):
        self.assertEqual(platform.system(), "Windows")
        self.assertTrue(
            PACKAGE.is_file(),
            "Set BLAS1_TEMPLATE_PACKAGE to the official 1.4.1 template package",
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
            ["dotnet", "new", "install", str(PACKAGE)],
            env=self.environment(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
        invalid_names = ("x", "1Mod", "CON", "ModTemplate", "Main", "ModInfo")
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
        cases = (
            ("--title", "", "Blasphemous.EmptyTitle"),
            ("--title", "Bad & Title", "Blasphemous.BadTitle"),
            ("--title", 'Bad "Title"', "Blasphemous.BadQuoteTitle"),
            ("--title", "Bad\\Title", "Blasphemous.BadBackslashTitle"),
            ("--title", "@AUTHOR@", "Blasphemous.TokenTitle"),
            ("--title", "Template Mod", "Blasphemous.ReservedTitle"),
            ("--title", "Line\u2028Break", "Blasphemous.UnicodeSeparatorTitle"),
            ("--author", " ", "Blasphemous.EmptyAuthor"),
            ("--author", "Line\nBreak", "Blasphemous.LineBreak"),
            ("--author", "Line\u2029Break", "Blasphemous.UnicodeSeparatorAuthor"),
            ("--author", 'Bad "Author"', "Blasphemous.BadQuoteAuthor"),
            ("--author", "Bad\\Author", "Blasphemous.BadBackslashAuthor"),
            ("--author", "@TITLE@", "Blasphemous.TokenAuthor"),
            ("--author", "Template Author", "Blasphemous.ReservedAuthor"),
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
            "Example Mod",
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
        self.assertTrue((output / ".gitignore").is_file())
        self.assertTrue((output / ".worktreeinclude").is_file())
        self.assertTrue((output / "dotnet_format.bat").is_file())
        self.assertTrue((output / ".config" / "wt.toml").is_file())
        self.assertTrue((output / "docs" / "agents" / "domain.md").is_file())
        self.assertTrue((output / "docs" / "agents" / "issue-tracker.md").is_file())
        self.assertTrue((output / "docs" / "agents" / "triage-labels.md").is_file())

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

        for path in output.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix not in (".cs", ".csproj", ".sln", ".md", ".xml", ".config", ".toml", ".bat"):
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
            "4.0.68",
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        project_text = (output / "Blasphemous.Versioned.csproj").read_text(
            encoding="utf-8"
        )
        self.assertIn('Blasphemous.GameLibs" Version="4.0.68"', project_text)

    def test_generated_mod_restores_and_builds(self):
        self.install_official_template()
        output = self.root / "Blasphemous.Buildable"
        result = self.run_wrapper(
            "--name",
            "Buildable",
            "--title",
            "Buildable Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

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
            ["dotnet", "build", str(solution), "--no-restore"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
        test = subprocess.run(
            ["dotnet", "test", str(solution), "--no-build"],
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self.assertEqual(test.returncode, 0, test.stdout + test.stderr)

        package = output / "publish" / "Buildable.zip"
        self.assertTrue(package.is_file())
        import zipfile

        with zipfile.ZipFile(package) as archive:
            names = archive.namelist()
        self.assertIn("plugins/Buildable.dll", names)
        self.assertFalse(any(".Tests" in name for name in names))

    def test_unavailable_verification_mod_fails_without_output(self):
        output = self.root / "Blasphemous.WithTest"
        result = self.run_wrapper(
            "--name",
            "WithTest",
            "--title",
            "With Test Mod",
            "--author",
            "Test Author",
            "--output",
            str(output),
            "--with-test-mod",
        )

        self.assertEqual(result.returncode, 2)
        self.assertFalse(output.exists())

    def test_generation_does_not_touch_surrounding_git_metadata(self):
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
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(marker.read_text(encoding="utf-8"), "untouched")
        self.assertFalse((output / ".git").exists())


if __name__ == "__main__":
    unittest.main()
