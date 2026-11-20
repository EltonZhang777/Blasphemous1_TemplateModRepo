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
TEMPLATE_REPO = REPO_ROOT / "TemplateRepo"
TEMPLATE_PACKAGE_TARGETS = TEMPLATE_REPO / "PackageMod.targets"
TEMPLATE_TEST_PROJECT = (
    TEMPLATE_REPO
    / "Blasphemous.Template.Tests"
    / "Blasphemous.Template.Tests.csproj"
)
WRAPPER = REPO_ROOT / "tools" / "new_blas1mod.py"
ROOT_README = REPO_ROOT / "README.md"
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
DOMAIN_GUIDE = REPO_ROOT / "docs" / "agents" / "domain.md"
ISSUE_TRACKER = REPO_ROOT / "docs" / "agents" / "issue-tracker.md"
TRIAGE_LABELS = REPO_ROOT / "docs" / "agents" / "triage-labels.md"
CREATE_GUIDE = REPO_ROOT / "docs" / "create-mod-repository.md"
MIGRATION_GUIDE = REPO_ROOT / "docs" / "migrate-mod-repository.md"
MARKDOWN_LOCAL_LINK = re.compile(
    r"\[[^\]]+\]\((?!(?:https?://|mailto:))([^)]+)\)"
)
WAYFINDING_PREREQUISITE_TERM = re.compile(
    r"(?i)\b(?:install(?:s|ed|ing|ation)?|setup|set up|set-up|"
    r"setting up|require(?:s|d)?|prerequisite)\b"
)
ROOT_WAYFINDING_GOLDEN = """## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
"""


def local_link_targets(document):
    for line in markdown_prose(document):
        for match in MARKDOWN_LOCAL_LINK.finditer(line):
            relative_path, _, anchor = match.group(1).partition("#")
            if relative_path:
                path = Path(relative_path)
                target = document.parent / path
            else:
                path = None
                target = document
            yield path, target, anchor


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


def wayfinding_prerequisite_clauses(document):
    return tuple(
        clause.strip()
        for clause in re.split(r"[.!?;]+", document)
        if "/wayfinder" in clause.lower()
        and WAYFINDING_PREREQUISITE_TERM.search(clause)
    )


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


def assert_markdown_contract(test_case, *, context, owner_root, sources):
    boundary = owner_root.resolve()
    for source in sources:
        source_path = source.resolve()
        with test_case.subTest(
            context=context,
            source=str(source_path),
            contract="source-boundary",
        ):
            test_case.assertTrue(
                source_path.is_relative_to(boundary),
                f"{context}: source escapes its documentation boundary: "
                f"{source_path}",
            )
            test_case.assertTrue(
                source_path.is_file(),
                f"{context}: source document does not exist: {source_path}",
            )
        for relative_path, target, anchor in local_link_targets(source):
            with test_case.subTest(
                context=context,
                source=str(source_path),
                target=str(target),
                contract="local-link",
            ):
                if relative_path is not None:
                    test_case.assertFalse(
                        relative_path.is_absolute(),
                        f"{context}: local link must be relative: {relative_path}",
                    )
                test_case.assertTrue(
                    target.resolve().is_relative_to(boundary),
                    f"{context}: local link escapes its documentation boundary: "
                    f"{target}",
                )
                test_case.assertTrue(
                    target.exists(),
                    f"{context}: local link target does not exist: {target}",
                )
                if anchor:
                    test_case.assertIn(
                        anchor,
                        heading_anchors(target),
                        f"{context}: missing link anchor #{anchor} in {target}",
                    )


def assert_guide_contract(test_case, guide, root_link, headings):
    root_readme = ROOT_README.read_text(encoding="utf-8")
    test_case.assertIn(root_link, root_readme)
    test_case.assertTrue(guide.is_file())
    prose = "\n".join(markdown_prose(guide))
    for heading in headings:
        test_case.assertIn(f"\n## {heading}\n", prose)


def assert_consumer_safety_warning(test_case, section):
    warning = "custom .NET CLI home"
    test_case.assertLess(section.index(warning), section.index("dotnet new install"))
    for marker in ("fixed", "disposable context", "per invocation", "not a guarantee"):
        with test_case.subTest(marker=marker):
            test_case.assertIn(marker, section)


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

    def test_documentation_covers_manual_startup_verification(self):
        readme = TEMPLATE_README.read_text(encoding="utf-8")
        prerequisites = markdown_section(
            TEMPLATE_README,
            "## Prerequisites",
            "## Install and generate",
        )
        install = markdown_section(
            TEMPLATE_README,
            "## Install and generate",
            "## Reference an existing project",
        )
        target_project = markdown_section(
            TEMPLATE_README,
            "## Reference an existing project",
            "## Wire the solution manually",
        )
        manual_wiring = markdown_section(
            TEMPLATE_README,
            "## Wire the solution manually",
            "## Verify startup in-game",
        )
        verification = markdown_section(
            TEMPLATE_README,
            "## Verify startup in-game",
            "## What startup proves",
        )
        startup_evidence = markdown_section(
            TEMPLATE_README,
            "## What startup proves",
            "## Troubleshooting",
        )
        troubleshooting = readme.partition("## Troubleshooting")[2]

        for marker in (
            "Windows",
            ".NET SDK 10",
            "NuGet access",
            "existing compatible Blasphemous 1 Mod or class-library repository",
            "Blasphemous 1",
            "BepInEx",
            "existing `Modding` folder",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, prerequisites)

        assert_consumer_safety_warning(self, install)

        for marker in (
            "--targetProject",
            "ProjectReference",
            "builds the target project",
            "includes its assembly in the archive below",
            "does not call target APIs",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, target_project)
        for marker in (
            "dotnet build",
            "`publish\\<project>.zip`",
            "plugins/",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, manual_wiring)
        self.assertIn("`[<generated name>] STARTUP_READY`", verification)
        self.assertIn(
            "`[Blasphemous.Example.TestMod] STARTUP_READY`",
            verification,
        )
        assert_ordered(
            self,
            verification,
            (
                "Close Blasphemous 1 and confirm it has exited.",
                "Rename any existing BepInEx log to a non-colliding backup name.",
                "Extract the archive directly into the game's `Modding` folder.",
                "Confirm the generated Verification Mod assembly is in the game's `Modding/plugins` directory.",
                "Start Blasphemous 1.",
                "Wait until loading completes.",
                "Inspect only the newly created BepInEx log",
            ),
        )
        for marker in (
            "only proves that the Verification Mod reached its startup log",
            "does not prove the target assembly was loaded",
            "target public API",
            "target runtime behavior",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, startup_evidence)
        for marker in (
            "archive",
            "plugins/<generated name>.dll",
            "Modding` folder's `plugins` directory",
            "BepInEx",
            "new BepInEx log",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, troubleshooting)


class RootDocumentationTests(unittest.TestCase):
    def test_root_owns_common_setup_and_primary_paths(self):
        readme = ROOT_README.read_text(encoding="utf-8")
        headings = level_two_headings(ROOT_README)
        self.assertLess(
            headings.index("Prerequisites"),
            headings.index("Clone the Repository"),
        )
        self.assertLess(
            headings.index("Clone the Repository"),
            headings.index("Choose your path"),
        )

        prerequisites = markdown_section(
            ROOT_README,
            "## Prerequisites",
            "## Clone the Repository",
        )
        for marker in (
            "common host prerequisites",
            "Windows",
            ".NET SDK 10",
            "Python 3.9 or later",
            "Git",
            "NuGet access",
            "[System.Environment]::OSVersion.Version",
            "dotnet --version",
            "python --version",
            "git --version",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, prerequisites)

        clone = markdown_section(
            ROOT_README,
            "## Clone the Repository",
            "## Choose your path",
        )
        self.assertIn(
            "git clone https://github.com/EltonZhang777/"
            "Blasphemous1_TemplateModRepo.git",
            clone,
        )

        paths = markdown_section(
            ROOT_README,
            "## Choose your path",
            "## Contributing",
        )
        create_link = "[Create a new Mod repository](docs/create-mod-repository.md)"
        migration_link = (
            "[Migrate an existing Mod repository]"
            "(docs/migrate-mod-repository.md)"
        )
        package_link = (
            "[Test Template Package verification journey]"
            "(Templates/Blasphemous1.ModTest.Templates/README.md)"
        )
        self.assertLess(paths.index(create_link), paths.index(migration_link))
        self.assertLess(paths.index(migration_link), paths.index(package_link))
        self.assertIn(
            "The Generator Command creates new Mod repositories only.",
            readme,
        )
        self.assertIn("Existing repositories use the in-place migration path.", readme)
        self.assertIn(
            "preserves Mod Identity and layout by default and permits only an "
            "approved structural refactor required by a failing gate",
            paths,
        )

        create_guide = CREATE_GUIDE.read_text(encoding="utf-8")
        for root_setup_link in (
            "[common host prerequisites](../README.md#prerequisites)",
            "[clone this repository](../README.md#clone-the-repository)",
        ):
            with self.subTest(root_setup_link=root_setup_link):
                self.assertIn(root_setup_link, create_guide)
        migration_guide = MIGRATION_GUIDE.read_text(encoding="utf-8")
        for root_setup_link in (
            "[common host prerequisites](../README.md#prerequisites)",
            "[clone this repository](../README.md#clone-the-repository)",
        ):
            with self.subTest(root_setup_link=root_setup_link):
                self.assertIn(root_setup_link, migration_guide)
        for guide in (CREATE_GUIDE, MIGRATION_GUIDE):
            text = guide.read_text(encoding="utf-8")
            for duplicated_setup in (
                "git clone https://github.com/EltonZhang777/",
                "[System.Environment]::OSVersion.Version",
                "dotnet --version",
                "python --version",
                "git --version",
            ):
                with self.subTest(guide=guide.name, marker=duplicated_setup):
                    self.assertNotIn(duplicated_setup, text)

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

    def test_meta_repository_markdown_links_resolve_locally(self):
        context = "Meta-Repository Documentation"
        listed = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md"],
            cwd=str(REPO_ROOT),
            capture_output=True,
        )
        self.assertEqual(
            0,
            listed.returncode,
            f"{context}: git ls-files failed: {listed.stderr!r}",
        )
        tracked_markdown = tuple(
            sorted(
                Path(os.fsdecode(path))
                for path in listed.stdout.split(b"\0")
                if path
            )
        )
        sources = tuple(
            REPO_ROOT / path
            for path in tracked_markdown
            if path.parts[0] != "TemplateRepo"
        )

        self.assertTrue(
            any(path.parts[0] == "TemplateRepo" for path in tracked_markdown),
            f"{context}: generated Repository Documentation was not discovered",
        )
        self.assertFalse(
            any(source.parts[0] == "TemplateRepo" for source in sources),
            f"{context}: generated Repository Documentation entered the scan",
        )
        for required in (
            Path("GLOSSARY.md"),
            Path("docs/adr/0006-separate-documentation-contexts.md"),
            Path("Templates/Blasphemous1.ModTest.Templates/README.md"),
        ):
            self.assertIn(
                required,
                tracked_markdown,
                f"{context}: required Markdown document missing from scan: "
                f"{required}",
            )

        assert_markdown_contract(
            self,
            context=context,
            owner_root=REPO_ROOT,
            sources=sources,
        )

    def test_domain_routing_uses_repository_layout_and_stops_adr_conflicts(self):
        domain = DOMAIN_GUIDE.read_text(encoding="utf-8")

        for marker in (
            "`GLOSSARY.md`",
            "`docs/adr/`",
            "accepted, non-superseded architecture decision",
            "record it in a new file under `docs/adr/`",
            "Stop only the affected change",
            "Cite the decision and the contradiction",
            "revise the proposal",
            "explicitly supersede the decision",
            "abandon the conflicting part",
        ):
            self.assertIn(marker, domain)
        for marker in (
            "GLOSSARY-MAP.md",
            "src/<context>/docs/adr/",
            "0001-event-sourced-orders.md",
            "0002-postgres-for-write-model.md",
            "Single-context repo (most repos)",
            "Multi-context repo",
            "/domain-modeling",
            "/grill-with-docs",
            "/improve-codebase-architecture",
        ):
            self.assertNotIn(marker, domain)

    def test_issue_tracker_is_powershell_canonical(self):
        context = "Meta-Repository Documentation"
        text = ISSUE_TRACKER.read_text(encoding="utf-8")
        operations = text.split("## Wayfinding operations", 1)[0]

        for marker in (
            "### Create an issue",
            "@'\n## Summary",
            "gh issue create --title \"...\" --body-file -",
            "gh issue create --title \"...\" --body-file .\\issue-body.md",
            "### Read an issue",
            "gh issue view $IssueNumber --json "
            "number,title,body,state,labels,comments,parent,subIssues",
            "### List issues",
            "gh issue list --state open --json "
            "number,title,body,state,labels,comments,parent,subIssues",
            "### Comment on an issue",
            "gh issue comment $IssueNumber --body-file .\\comment.md",
            "### Add a label",
            "gh issue edit $IssueNumber --add-label \"ready-for-agent\"",
            "### Close an issue",
            "gh issue close $IssueNumber --reason completed --comment \"...\"",
            "Pull requests are not a feature-request surface.",
        ):
            self.assertIn(marker, operations)
        for marker in (
            "Use a heredoc",
            "When set to",
            "gh pr ",
            "## When a skill says",
            "fetching labels",
            "<number>",
            "Read or fetch",
            "--remove-label",
        ):
            self.assertNotIn(marker, operations)

        before_wayfinding, wayfinding = text.split(
            "## Wayfinding operations", 1
        )
        self.assertEqual(
            ROOT_WAYFINDING_GOLDEN,
            f"## Wayfinding operations{wayfinding}",
            f"{context}: retained Wayfinding guidance changed",
        )
        self.assertEqual(0, before_wayfinding.count("/wayfinder"))
        self.assertIn("Used by `/wayfinder`.", wayfinding)
        self.assertTrue(wayfinding.startswith("\n\nUsed by `/wayfinder`."))
        self.assertEqual(1, wayfinding.count("/wayfinder"))
        self.assertNotIn("```", wayfinding)
        self.assertEqual((), wayfinding_prerequisite_clauses(wayfinding))
        self.assertEqual(
            (
                "Install /wayfinder first",
                "Install\n/wayfinder first",
                "Setting up /wayfinder",
            ),
            wayfinding_prerequisite_clauses(
                "Install /wayfinder first. "
                "Install\n/wayfinder first. "
                "Setting up /wayfinder..."
            ),
        )
        self.assertEqual(
            (),
            wayfinding_prerequisite_clauses(
                "Setup status is unrelated; /wayfinder maps the work."
            ),
        )

    def test_root_guidance_preserves_release_safety_boundary(self):
        context = "Meta-Repository Documentation"
        agents = ROOT_AGENTS.read_text(encoding="utf-8")

        for marker in (
            "Publishing happens only through "
            "[`.github/workflows/release.yml`](.github/workflows/release.yml)",
            "secret values must never be recorded",
            "checked-out tag commit is an ancestor of the current `main` branch",
        ):
            self.assertIn(
                marker,
                agents,
                f"{context}: missing release safety contract: {marker}",
            )
        self.assertNotIn(
            "trusted publishing",
            agents,
            f"{context}: root guidance repeats release publication mechanics",
        )

    def test_triage_labels_are_the_direct_authority(self):
        text = TRIAGE_LABELS.read_text(encoding="utf-8")

        for label, meaning in (
            ("needs-triage", "Maintainer needs to evaluate this issue"),
            ("needs-info", "Waiting on reporter for more information"),
            ("ready-for-agent", "Fully specified, ready for an AFK agent"),
            ("ready-for-human", "Requires human implementation"),
            ("wontfix", "Will not be actioned"),
        ):
            self.assertIn(f"`{label}`", text)
            self.assertIn(meaning, text)
        for marker in (
            "mattpocock",
            "Label in our tracker",
            "corresponding label",
            "Edit the right-hand column",
        ):
            self.assertNotIn(marker, text)

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
                r"<Import\b",
                r"<UsingTask\b",
                "dotnet restore $solution -p:Configuration=Release",
                "dotnet msbuild $mainProject",
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
            "| Module boundaries |",
            "dotnet sln '<solution-path>' add '<test-project-path>'",
            "dotnet sln '<solution-path>' list",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("dotnet sln <solution-path>", text)

    def test_git_recovery_and_revert_are_approval_gated(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")
        git_recovery = markdown_section(
            MIGRATION_GUIDE,
            "### Git repository",
            "### Non-Git repository",
        )
        after_merge = markdown_section(
            MIGRATION_GUIDE,
            "### After merge",
            "### Non-Git restore",
        )

        self.assertIn("verified external backup", git_recovery)
        self.assertIn("A branch and SHA do not restore", git_recovery)
        self.assertIn("git revert --no-commit -m 1 '<merge-commit>'", after_merge)
        self.assertIn(
            "git revert --no-commit '<squash-commit>'",
            after_merge,
        )
        self.assertIn(
            "git diff --cached '<recorded-start-sha>' --",
            after_merge,
        )
        self.assertIn("Request separate explicit approval", after_merge)
        self.assertNotIn("git revert -m 1 '<merge-commit>'", after_merge)
        self.assertIn("correct one-commit, squash, or merge revert path", text)

    def test_migration_partial_is_not_ticket_closure(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")

        self.assertIn("not a GitHub issue-closure state", text)
        self.assertIn(
            "requires the exact HEAD plus matching evidence",
            text,
        )

    def test_creation_guide_owns_inputs_and_recovery(self):
        text = CREATE_GUIDE.read_text(encoding="utf-8")
        prerequisites = markdown_section(
            CREATE_GUIDE,
            "## Prerequisites",
            "## Install the Official Template Baseline",
        )
        for root_setup_link in (
            "[common host prerequisites](../README.md#prerequisites)",
            "[clone this repository](../README.md#clone-the-repository)",
        ):
            self.assertIn(root_setup_link, prerequisites)
        for repeated_setup in (
            "[System.Environment]::OSVersion.Version",
            "dotnet --version",
            "python --version",
            "git --version",
            "git clone https://github.com/EltonZhang777/",
        ):
            with self.subTest(repeated_setup=repeated_setup):
                self.assertNotIn(repeated_setup, text)

        install = markdown_section(
            CREATE_GUIDE,
            "## Install the Official Template Baseline",
            "## Create the Mod Repository",
        )
        assert_consumer_safety_warning(self, install)

        create = markdown_section(
            CREATE_GUIDE,
            "## Create the Mod Repository",
            "## Expected Result",
        )
        command = "python tools/new_blas1mod.py"
        constraints = "The parameter constraints are:"
        self.assertEqual(1, text.count(command))
        self.assertLess(create.index(command), create.index(constraints))
        for constraint in (
            "`--name` is the Machine Identifier",
            "`--title` is the Display Title",
            "`--author` is the author name",
            "`--output` is a new directory path",
            "`--game-version`, which defaults to `4.0.67`",
        ):
            with self.subTest(constraint=constraint):
                self.assertIn(constraint, create[create.index(constraints):])
        self.assertNotIn("The required inputs are", text)
        self.assertNotIn("The optional inputs are", text)
        self.assertNotIn("--with-test-mod", create)
        self.assertNotIn("Linux and macOS", text)

        optional = markdown_section(
            CREATE_GUIDE,
            "## Optional Verification Mod",
            "## Recover from Common Failures",
        )
        self.assertEqual(1, text.count("--with-test-mod"))
        self.assertIn("Choose this option before generation", optional)
        self.assertNotIn(command, optional)

        recovery_start = text.index("## Recover from Common Failures")
        normal_flow = text[:recovery_start]
        recovery = text[recovery_start:text.index("## Stop Before Git")]
        for recovery_only in (
            "Inspect that path for the failing files",
            "Correct the reported problem",
            "inspect the diff",
        ):
            with self.subTest(recovery_only=recovery_only):
                self.assertNotIn(recovery_only, normal_flow)
        for marker in (
            "Read the preceding error",
            "inspect the preserved staging directory",
            "fix that cause",
            r".\dotnet_format.bat .\Blasphemous.Example.sln",
            "repeat both format verification commands",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, recovery)
        self.assertNotIn("git diff", text)
        self.assertNotIn("inspect the diff", text)

    def test_creation_guide_claims_match_template_sources(self):
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
        self.assertIn(
            "dotnet restore .\\Blasphemous.Example.sln -p:Configuration=Release",
            text,
        )

        package_targets = TEMPLATE_PACKAGE_TARGETS.read_text(encoding="utf-8")
        self.assertIn("resources\\**\\*.*", package_targets)
        self.assertIn(
            "DestinationFolder=\"$(PackageStagingFolder)\\plugins\"",
            package_targets,
        )

        test_project = TEMPLATE_TEST_PROJECT.read_text(encoding="utf-8")
        self.assertIn("<TargetFramework>net48</TargetFramework>", test_project)
        self.assertIn("<IsPackable>false</IsPackable>", test_project)

        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('REQUIRED_VERSION = "1.4.1"', wrapper)
        self.assertIn('DEFAULT_GAME_VERSION = "4.0.67"', wrapper)
        self.assertIn("Blasphemous.Modding.Templates::1.4.1", text)
        self.assertIn("--game-version 4.0.67", text)

    def test_migration_guide_matches_template_and_representative_shape(self):
        text = MIGRATION_GUIDE.read_text(encoding="utf-8")
        package_targets = TEMPLATE_PACKAGE_TARGETS.read_text(encoding="utf-8")
        test_project = TEMPLATE_TEST_PROJECT.read_text(encoding="utf-8")

        self.assertIn("$(TargetName).zip", package_targets)
        self.assertIn("<TargetFramework>net48</TargetFramework>", test_project)
        self.assertIn("<IsPackable>false</IsPackable>", test_project)

        for marker in (
            "plugins/<TargetName>.dll",
            "No Automated Test Project or test assembly",
            "`net48` xUnit Automated Test Project",
            "`net35` project in a subdirectory of a",
            "no adjacent Automated Test Project",
            "inline build and deployment",
        ):
            self.assertIn(marker, text)

    def test_integrated_consumer_documentation_contract(self):
        root = ROOT_README.read_text(encoding="utf-8")
        agents = ROOT_AGENTS.read_text(encoding="utf-8")
        creation = CREATE_GUIDE.read_text(encoding="utf-8")
        migration = MIGRATION_GUIDE.read_text(encoding="utf-8")
        package = TEMPLATE_README.read_text(encoding="utf-8")

        root_headings = level_two_headings(ROOT_README)
        self.assertEqual(1, root_headings.count("Prerequisites"))
        self.assertEqual(1, root_headings.count("Clone the Repository"))
        self.assertLess(
            root_headings.index("Prerequisites"),
            root_headings.index("Clone the Repository"),
        )
        self.assertLess(
            root_headings.index("Clone the Repository"),
            root_headings.index("Choose your path"),
        )

        root_paths = markdown_section(
            ROOT_README,
            "## Choose your path",
            "## Contributing",
        )
        create_path = "[Create a new Mod repository](docs/create-mod-repository.md)"
        migration_path = (
            "[Migrate an existing Mod repository]"
            "(docs/migrate-mod-repository.md)"
        )
        package_path = (
            "[Test Template Package verification journey]"
            "(Templates/Blasphemous1.ModTest.Templates/README.md)"
        )
        self.assertLess(root_paths.index(create_path), root_paths.index(migration_path))
        self.assertLess(root_paths.index(migration_path), root_paths.index(package_path))
        self.assertIn(
            "The Generator Command creates new Mod repositories only.",
            root,
        )
        self.assertIn("Existing repositories use the in-place migration path.", root)
        self.assertIn(
            "preserves Mod Identity and layout by default and permits only an "
            "approved structural refactor required by a failing gate",
            root_paths,
        )
        self.assertIn(
            "- [Test Template Package](Templates/Blasphemous1.ModTest.Templates/"
            "README.md) is the supported supplemental user-document path",
            agents,
        )
        for product_command in (
            "dotnet new install",
            "python tools/new_blas1mod.py",
            "dotnet new blasmodtest",
            "dotnet pack",
            "dotnet sln add",
        ):
            with self.subTest(product_command=product_command):
                self.assertNotIn(product_command, root)

        creation_prerequisites = markdown_section(
            CREATE_GUIDE,
            "## Prerequisites",
            "## Install the Official Template Baseline",
        )
        for root_setup_link in (
            "[common host prerequisites](../README.md#prerequisites)",
            "[clone this repository](../README.md#clone-the-repository)",
        ):
            self.assertIn(root_setup_link, creation_prerequisites)
        for repeated_setup in (
            "[System.Environment]::OSVersion.Version",
            "dotnet --version",
            "python --version",
            "git --version",
            "git clone https://github.com/EltonZhang777/",
        ):
            with self.subTest(repeated_setup=repeated_setup):
                self.assertNotIn(repeated_setup, creation)
        creation_command = "python tools/new_blas1mod.py"
        self.assertEqual(1, creation.count(creation_command))
        self.assertIn("The parameter constraints are:", creation)
        self.assertEqual(1, creation.count("--with-test-mod"))
        optional = markdown_section(
            CREATE_GUIDE,
            "## Optional Verification Mod",
            "## Recover from Common Failures",
        )
        self.assertIn("--with-test-mod", optional)
        self.assertIn("Choose this option before generation", optional)
        self.assertNotIn(creation_command, optional)
        self.assertNotIn("Linux and macOS", creation)
        self.assertNotIn("git diff", creation)
        self.assertNotIn("inspect the diff", creation)

        self.assertIn(
            "preserves Mod Identity, public contracts, and the existing layout by default",
            migration,
        )
        self.assertIn("Structural Refactor Gate", migration)
        self.assertIn("git diff --cached", migration)

        package_prerequisites = markdown_section(
            TEMPLATE_README,
            "## Prerequisites",
            "## Install and generate",
        )
        for package_prerequisite in (
            "Windows",
            ".NET SDK 10",
            "NuGet access",
            "existing compatible Blasphemous 1 Mod or class-library repository",
            "BepInEx",
            "existing `Modding` folder",
        ):
            self.assertIn(package_prerequisite, package_prerequisites)
        verification = markdown_section(
            TEMPLATE_README,
            "## Verify startup in-game",
            "## What startup proves",
        )
        evidence = markdown_section(
            TEMPLATE_README,
            "## What startup proves",
            "## Troubleshooting",
        )
        troubleshooting = package.partition("## Troubleshooting")[2]
        self.assertIn("`[<generated name>] STARTUP_READY`", verification)
        self.assertIn(
            "`[Blasphemous.Example.TestMod] STARTUP_READY`",
            verification,
        )
        assert_ordered(
            self,
            verification,
            (
                "Close Blasphemous 1 and confirm it has exited.",
                "Rename any existing BepInEx log to a non-colliding backup name.",
                "Extract the archive directly into the game's `Modding` folder.",
                "Start Blasphemous 1.",
                "Wait until loading completes.",
                "Inspect only the newly created BepInEx log",
            ),
        )
        for evidence_boundary in (
            "only proves that the Verification Mod reached its startup log",
            "does not prove the target assembly was loaded",
            "target public API",
            "target runtime behavior",
        ):
            self.assertIn(evidence_boundary, evidence)
        for diagnostic in (
            "archive",
            "plugins/<generated name>.dll",
            "plugins` directory",
            "BepInEx",
            "new BepInEx log",
        ):
            self.assertIn(diagnostic, troubleshooting)
        self.assertNotIn("STARTUP_READY was observed", package)

        creation_install = markdown_section(
            CREATE_GUIDE,
            "## Install the Official Template Baseline",
            "## Create the Mod Repository",
        )
        package_install = markdown_section(
            TEMPLATE_README,
            "## Install and generate",
            "## Reference an existing project",
        )
        assert_consumer_safety_warning(self, creation_install)
        assert_consumer_safety_warning(self, package_install)

        assert_markdown_contract(
            self,
            context="Meta-Repository Documentation",
            owner_root=REPO_ROOT,
            sources=(
                ROOT_README,
                ROOT_AGENTS,
                CREATE_GUIDE,
                MIGRATION_GUIDE,
                TEMPLATE_README,
            ),
        )

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
                "Prerequisites",
                "Clone the Repository",
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
        self.assertIn(
            "[Test Template Package verification journey]"
            "(Templates/Blasphemous1.ModTest.Templates/README.md)",
            readme,
        )
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
            "Conditional references",
            "Maintainer checks",
        ):
            self.assertIn(heading, agents_headings)
        for marker in (
            "python -m unittest discover -s tests -v",
            "BLAS1_DISPOSABLE_TEST_CONTEXT",
            "Disposable Test Context",
            "docs/agents/issue-tracker.md",
            "docs/agents/triage-labels.md",
            "docs/agents/domain.md",
            "GLOSSARY.md",
            "docs/adr/",
            "AGENTS.local.md",
            "Templates/Blasphemous1.ModTest.Templates/README.md",
            "supported supplemental user-document path",
            ".github/workflows/release.yml",
            "checked-out tag commit is an ancestor of the current `main` branch",
            "Publishing happens only through "
            "[`.github/workflows/release.yml`](.github/workflows/release.yml)",
            "secret values must never be recorded",
        ):
            self.assertIn(marker, agents)
        for marker in (
            "dotnet pack .\\Templates\\Blasphemous1.ModTest.Templates",
            "Get-ChildItem .\\Templates\\Blasphemous1.ModTest.Templates",
            "dotnet new install $package.FullName",
            "dotnet new blasmodtest",
            "dotnet sln add",
            "trusted publishing",
        ):
            self.assertNotIn(marker, agents)
        self.assertNotIn("](AGENTS.local.md)", agents)


if __name__ == "__main__":
    unittest.main()
