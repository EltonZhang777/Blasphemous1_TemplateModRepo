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
MARKDOWN_REFERENCE_DEFINITION = re.compile(
    r"^ {0,3}\[([^\]]+)\]:\s*(?:<([^>]+)>|(\S+))"
)
MARKDOWN_REFERENCE_LINK = re.compile(
    r"\[([^\]\n]+)\](?:\[([^\]\n]*)\])?"
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
def normalize_reference_label(label):
    return " ".join(label.split()).casefold()


def reference_definitions(document):
    definitions = {}
    for line in markdown_prose(document):
        match = MARKDOWN_REFERENCE_DEFINITION.match(line)
        if match:
            destination = match.group(2) or match.group(3)
            definitions[normalize_reference_label(match.group(1))] = destination
    return definitions


def link_target(document, destination):
    if destination.lower().startswith(("http://", "https://", "mailto:")):
        return None
    relative_path, _, anchor = destination.partition("#")
    if relative_path:
        path = Path(relative_path)
        target = document.parent / path
    else:
        path = None
        target = document
    return path, target, anchor
def local_link_targets(document):
    definitions = reference_definitions(document)
    for line in markdown_prose(document):
        for match in MARKDOWN_LOCAL_LINK.finditer(line):
            resolved = link_target(document, match.group(1))
            if resolved is not None:
                yield resolved
        if MARKDOWN_REFERENCE_DEFINITION.match(line):
            continue
        for match in MARKDOWN_REFERENCE_LINK.finditer(line):
            link_text, explicit_label = match.groups()
            if explicit_label is None and line[match.end() :].startswith("("):
                continue
            label = link_text if explicit_label in (None, "") else explicit_label
            destination = definitions.get(normalize_reference_label(label))
            if destination is None:
                continue
            resolved = link_target(document, destination)
            if resolved is not None:
                yield resolved


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
        self.assertIn("standalone `Blasphemous1.ModTest.Templates`", readme)
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
