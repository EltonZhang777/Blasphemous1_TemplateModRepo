#!/usr/bin/env python3
"""Generate a Blasphemous 1 Mod repository from the official 1.4.1 template."""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path


REQUIRED_TEMPLATE = "Blasphemous.Modding.Templates"
REQUIRED_VERSION = "1.4.1"
MODDING_API_VERSION = "3.0.1"
DEFAULT_GAME_VERSION = "4.0.67"
REFERENCE_ASSEMBLIES_VERSION = "1.0.3"

CSHARP_KEYWORDS = {
    "abstract",
    "as",
    "base",
    "bool",
    "break",
    "byte",
    "case",
    "catch",
    "char",
    "checked",
    "class",
    "const",
    "continue",
    "decimal",
    "default",
    "delegate",
    "do",
    "double",
    "else",
    "enum",
    "event",
    "explicit",
    "extern",
    "false",
    "finally",
    "fixed",
    "float",
    "for",
    "foreach",
    "goto",
    "if",
    "implicit",
    "in",
    "int",
    "interface",
    "internal",
    "is",
    "lock",
    "long",
    "namespace",
    "new",
    "null",
    "object",
    "operator",
    "out",
    "override",
    "params",
    "private",
    "protected",
    "public",
    "readonly",
    "ref",
    "return",
    "sbyte",
    "sealed",
    "short",
    "sizeof",
    "stackalloc",
    "static",
    "string",
    "struct",
    "switch",
    "this",
    "throw",
    "true",
    "try",
    "typeof",
    "uint",
    "ulong",
    "unchecked",
    "unsafe",
    "ushort",
    "using",
    "virtual",
    "void",
    "volatile",
    "while",
}

RESERVED_DEVICE_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}

COLLIDING_PROJECT_NAMES = {"Main", "ModInfo", "ModTemplate", "TemplateMod"}
RESERVED_DISPLAY_TEXT = {
    "Mod Creator",
    "Mod Template",
    "Template Author",
    "Template Mod",
    "TemplateMod",
    "ModTemplate",
}
IDENTITY_TOKENS = (
    "@PROJECT_NAME@",
    "@MACHINE_IDENTIFIER@",
    "@TITLE@",
    "@AUTHOR@",
)
OVERLAY_ROOT = Path(__file__).resolve().parent.parent / "TemplateRepo"
OVERLAY_FILES = (
    "README.md",
    "AGENTS.md",
    ".editorconfig",
    ".gitignore",
    ".worktreeinclude",
    "NuGet.Config",
    "dotnet_format.bat",
    ".config/wt.toml",
    "docs/agents/domain.md",
    "docs/agents/issue-tracker.md",
    "docs/agents/triage-labels.md",
    "resources/.gitkeep",
)
TEST_PROJECT_SOURCE = "Blasphemous.Template.Tests"


def parse_installed_versions(output):
    """Return versions reported for the official template package."""
    lines = output.splitlines()
    versions = []
    for index, line in enumerate(lines):
        if line.strip() != REQUIRED_TEMPLATE:
            continue
        for detail in lines[index + 1 : index + 8]:
            match = re.search(r"\bVersion:\s*([^\s]+)", detail)
            if match:
                versions.append(match.group(1))
                break
    return versions


def validate_machine_identifier(value):
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]{1,63}", value):
        raise ValueError(
            "Machine Identifier must be 2-64 ASCII letters/digits, start with "
            "an uppercase letter, and contain no separators."
        )
    if value.lower() in CSHARP_KEYWORDS:
        raise ValueError("Machine Identifier must not be a C# keyword.")
    if value.upper() in RESERVED_DEVICE_NAMES:
        raise ValueError("Machine Identifier must not be a Windows device name.")
    if value in COLLIDING_PROJECT_NAMES:
        raise ValueError(
            "Machine Identifier collides with a generated type or template placeholder."
        )


def validate_display_text(value, label):
    value = value.strip()
    if not 1 <= len(value) <= 80:
        raise ValueError(f"{label} must be between 1 and 80 characters after trimming.")
    if any(
        character in "\r\n\t\u2028\u2029&<>\"\\"
        or unicodedata.category(character).startswith("C")
        for character in value
    ):
        raise ValueError(
            f"{label} must not contain control characters, XML delimiters, "
            "quotes, or backslashes."
        )
    if value in RESERVED_DISPLAY_TEXT:
        raise ValueError(f"{label} must not reuse a template placeholder identity.")
    if any(token in value for token in IDENTITY_TOKENS):
        raise ValueError(f"{label} must not contain reserved overlay tokens.")
    return value


def validate_game_version(value):
    value = value.strip()
    if not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}", value):
        raise ValueError("Game version must be a non-empty version string.")
    return value


def validate_output_path(value):
    if not value.strip():
        raise ValueError("Output path must not be empty.")
    try:
        output = Path(value).expanduser().resolve()
    except (OSError, ValueError) as error:
        raise ValueError(f"Output path is invalid: {error}") from error
    if output.parent.exists() and not output.parent.is_dir():
        raise ValueError(f"Output parent is not a directory: {output.parent}")
    if os.path.lexists(output):
        raise ValueError(f"Output path already exists: {output}")
    return output


def run(command):
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def check_template(dotnet):
    result = run([dotnet, "new", "uninstall"])
    versions = parse_installed_versions(result.stdout + result.stderr)
    if result.returncode != 0 or versions != [REQUIRED_VERSION]:
        print(
            f"{REQUIRED_TEMPLATE} {REQUIRED_VERSION} is required. "
            f"Install it with: dotnet new install {REQUIRED_TEMPLATE}::{REQUIRED_VERSION}"
        )
        return False
    return True


def replace_once(text, pattern, replacement, label):
    updated, replacements = re.subn(pattern, replacement, text, count=1)
    if replacements != 1:
        raise RuntimeError(f"Could not apply the {label} overlay.")
    return updated


def replace_identity(text, project_name, machine_identifier, title, author):
    values = {
        "@PROJECT_NAME@": project_name,
        "@MACHINE_IDENTIFIER@": machine_identifier,
        "@TITLE@": title,
        "@AUTHOR@": author,
    }
    return re.sub(
        "|".join(re.escape(token) for token in values),
        lambda match: values[match.group(0)],
        text,
    )


def copy_overlay_files(project_dir, project_name, machine_identifier, title, author):
    for relative in OVERLAY_FILES:
        source = OVERLAY_ROOT / relative
        if not source.is_file():
            raise RuntimeError(f"The overlay file is missing: {source}")
        target = project_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source.read_text(encoding="utf-8-sig")
        target.write_text(
            replace_identity(text, project_name, machine_identifier, title, author),
            encoding="utf-8",
        )

    source = OVERLAY_ROOT / "PackageMod.targets"
    if not source.is_file():
        raise RuntimeError(f"The overlay file is missing: {source}")
    shutil.copy2(source, project_dir / source.name)

    source_tests = OVERLAY_ROOT / TEST_PROJECT_SOURCE
    target_tests = project_dir / f"{project_name}.Tests"
    if not source_tests.is_dir():
        raise RuntimeError(f"The overlay test project is missing: {source_tests}")
    if target_tests.exists():
        raise RuntimeError(f"The generated test project path is occupied: {target_tests}")
    shutil.copytree(source_tests, target_tests)
    for path in target_tests.rglob("*"):
        if path.suffix in (".cs", ".csproj"):
            text = path.read_text(encoding="utf-8-sig")
            path.write_text(
                replace_identity(text, project_name, machine_identifier, title, author),
                encoding="utf-8",
            )
    project = target_tests / f"{TEST_PROJECT_SOURCE}.csproj"
    project.rename(target_tests / f"{project_name}.Tests.csproj")


def create_solution(dotnet, project_dir, project_name):
    solution = project_dir / f"{project_name}.sln"
    created = run(
        [
            dotnet,
            "new",
            "sln",
            "--name",
            project_name,
            "--format",
            "sln",
            "--output",
            str(project_dir),
        ]
    )
    if created.returncode != 0:
        raise RuntimeError(
            "dotnet new sln failed.\n" + created.stdout + created.stderr
        )

    added = run(
        [
            dotnet,
            "sln",
            str(solution),
            "add",
            str(project_dir / f"{project_name}.csproj"),
            str(project_dir / f"{project_name}.Tests" / f"{project_name}.Tests.csproj"),
        ]
    )
    if added.returncode != 0:
        raise RuntimeError("dotnet sln add failed.\n" + added.stdout + added.stderr)
    if not solution.is_file():
        raise RuntimeError("The generated solution file is missing.")
    return solution


def validate_generated(project_dir, machine_identifier, game_version):
    project_name = f"Blasphemous.{machine_identifier}"
    project = project_dir / f"{project_name}.csproj"
    main = project_dir / "Main.cs"
    targets = project_dir / "PackageMod.targets"
    test_dir = project_dir / f"{project_name}.Tests"
    test_project = test_dir / f"{project_name}.Tests.csproj"
    test_source = test_dir / "ModMetadataTests.cs"
    solution = project_dir / f"{project_name}.sln"
    required = (
        project,
        main,
        targets,
        test_project,
        test_source,
        solution,
        project_dir / "resources",
        *(project_dir / relative for relative in OVERLAY_FILES),
    )
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError("The generated overlay is incomplete: " + ", ".join(missing))

    root = ET.parse(project).getroot()
    property_group = root.find("PropertyGroup")
    if property_group is None or property_group.findtext("TargetName") != machine_identifier:
        raise RuntimeError("The generated project has an invalid TargetName.")
    if property_group.findtext("DeployToGame") != "false":
        raise RuntimeError("Game deployment is not disabled by default.")

    packages = {
        item.attrib.get("Include"): item.attrib.get("Version")
        for item in root.findall(".//PackageReference")
    }
    if packages.get("Blasphemous.ModdingAPI") != MODDING_API_VERSION:
        raise RuntimeError("The generated project has an invalid ModdingAPI version.")
    if packages.get("Blasphemous.GameLibs") != game_version:
        raise RuntimeError("The generated project has an invalid GameLibs version.")
    if "Microsoft.NETFramework.ReferenceAssemblies.net35" not in packages:
        raise RuntimeError("The generated project is missing net35 reference assemblies.")

    imports = [item.attrib.get("Project", "") for item in root.findall(".//Import")]
    if not any(item.endswith("PackageMod.targets") for item in imports):
        raise RuntimeError("The generated project is missing its package target.")

    test_root = ET.parse(test_project).getroot()
    test_property_group = test_root.find("PropertyGroup")
    if (
        test_property_group is None
        or test_property_group.findtext("TargetFramework") != "net48"
    ):
        raise RuntimeError("The generated test project has an invalid target framework.")
    if test_property_group.findtext("IsPackable") != "false":
        raise RuntimeError("The generated test project is packable.")
    test_references = [
        item.attrib.get("Include", "") for item in test_root.findall(".//ProjectReference")
    ]
    if not any(
        item.replace("\\", "/").endswith(f"../{project_name}.csproj")
        for item in test_references
    ):
        raise RuntimeError("The generated test project does not reference the Mod.")

    solution_text = solution.read_text(encoding="utf-8")
    if f'"{project_name}", "{project_name}.csproj"' not in solution_text:
        raise RuntimeError("The generated solution is missing the Mod project.")
    test_relative = f"{project_name}.Tests\\{project_name}.Tests.csproj"
    if (
        f'"{project_name}.Tests", "{test_relative}"' not in solution_text
        and f'"{project_name}.Tests", "{test_relative.replace(chr(92), "/")}"'
        not in solution_text
    ):
        raise RuntimeError("The generated solution is missing the test project.")

    main_text = main.read_text(encoding="utf-8-sig")
    if (
        f'BepInDependency("Blasphemous.ModdingAPI", "{MODDING_API_VERSION}")'
        not in main_text
    ):
        raise RuntimeError("The generated plugin has an invalid BepInDependency version.")

    test_text = test_source.read_text(encoding="utf-8-sig")
    if f"typeof({project_name}.{machine_identifier})" not in test_text:
        raise RuntimeError("The generated test does not reference the Mod type.")

    text_files = [
        path
        for path in project_dir.rglob("*")
        if path.is_file()
        and (
            path.suffix.lower()
            in {
                ".cs",
                ".csproj",
                ".sln",
                ".md",
                ".xml",
                ".config",
                ".toml",
                ".bat",
                ".targets",
                ".props",
                ".json",
                ".yml",
                ".yaml",
            }
            or path.name in {".editorconfig", ".gitignore", ".worktreeinclude"}
        )
    ]
    placeholders = (*RESERVED_DISPLAY_TEXT, *IDENTITY_TOKENS)
    for path in text_files:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        for placeholder in placeholders:
            if placeholder in text:
                raise RuntimeError(
                    "Template placeholder remains in generated output: "
                    f"{placeholder} in {path.relative_to(project_dir)}"
                )


def apply_overlay(project_dir, machine_identifier, game_version, title, author, dotnet):
    project_name = f"Blasphemous.{machine_identifier}"
    project = project_dir / f"{project_name}.csproj"
    main = project_dir / "Main.cs"
    if not project.is_file() or not main.is_file():
        raise RuntimeError("The official template output is missing its project files.")

    project_text = project.read_text(encoding="utf-8-sig")
    project_text = replace_once(
        project_text,
        r'(<PackageReference Include="Blasphemous\.ModdingAPI" Version=")[^"]+(")',
        lambda match: f"{match.group(1)}{MODDING_API_VERSION}{match.group(2)}",
        "ModdingAPI version",
    )
    project_text = replace_once(
        project_text,
        r'(<PackageReference Include="Blasphemous\.GameLibs" Version=")[^"]+(")',
        lambda match: f"{match.group(1)}{game_version}{match.group(2)}",
        "GameLibs version",
    )
    project_text = replace_once(
        project_text,
        r"<TargetName>[^<]*</TargetName>",
        lambda _match: f"<TargetName>{machine_identifier}</TargetName>",
        "TargetName",
    )
    project_text = replace_once(
        project_text,
        r"\s*<RepositoryUrl>https://github\.com/Example</RepositoryUrl>",
        lambda _match: "",
        "repository URL",
    )
    project_text = replace_once(
        project_text,
        r"(    <TargetFramework>net35</TargetFramework>\n)",
        lambda match: (
            match.group(1)
            + "    <DeployToGame Condition=\"'$(DeployToGame)' == ''\">false</DeployToGame>\n"
            + "    <DevFolder Condition=\"'$(DevFolder)' == ''\"></DevFolder>\n"
        ),
        "deployment properties",
    )
    project_text = replace_once(
        project_text,
        r"</Project>",
        lambda _match: (
            "  <ItemGroup>\n"
            f'    <PackageReference Include="Microsoft.NETFramework.ReferenceAssemblies.net35" '
            f'Version="{REFERENCE_ASSEMBLIES_VERSION}" PrivateAssets="all" />\n'
            f'    <Compile Remove="{project_name}.Tests/**/*.cs" />\n'
            "  </ItemGroup>\n\n"
            "</Project>"
        ),
        "test source exclusion",
    )

    development_pattern = re.compile(
        r"\s*<Target Name=\"Development\" AfterTargets=\"PostBuildEvent\">.*?</Target>",
        re.DOTALL,
    )
    project_text = replace_once(
        project_text,
        development_pattern,
        lambda _match: (
            "  <Import Project=\"$(MSBuildProjectDirectory)\\PackageMod.targets\" />\n"
        ),
        "development target",
    )

    main_text = main.read_text(encoding="utf-8-sig")
    main_text = replace_once(
        main_text,
        r'(BepInDependency\("Blasphemous\.ModdingAPI",\s*")[^"]+(")',
        lambda match: f"{match.group(1)}{MODDING_API_VERSION}{match.group(2)}",
        "BepInDependency version",
    )

    combined = project_text + main_text
    for placeholder in ("Mod Template", "Mod Creator", "TemplateMod", "ModTemplate"):
        if placeholder in combined:
            raise RuntimeError(f"Template placeholder remains in generated output: {placeholder}")

    project.write_text(project_text, encoding="utf-8")
    main.write_text(main_text, encoding="utf-8")
    copy_overlay_files(
        project_dir, project_name, machine_identifier, title, author
    )
    create_solution(dotnet, project_dir, project_name)
    validate_generated(project_dir, machine_identifier, game_version)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Generate a Blasphemous 1 Mod repository from the official template."
    )
    parser.add_argument("--name", required=True, help="Machine Identifier")
    parser.add_argument("--title", required=True, help="Display Title")
    parser.add_argument("--author", required=True, help="Author")
    parser.add_argument("--output", required=True, help="New output directory")
    parser.add_argument("--game-version", default=DEFAULT_GAME_VERSION)
    parser.add_argument("--with-test-mod", action="store_true")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        validate_machine_identifier(args.name)
        title = validate_display_text(args.title, "Display Title")
        author = validate_display_text(args.author, "Author")
        game_version = validate_game_version(args.game_version)
        output = validate_output_path(args.output)
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.with_test_mod:
        print(
            "error: --with-test-mod is not available yet; generate the base Mod first.",
            file=sys.stderr,
        )
        return 2

    dotnet = shutil.which("dotnet")
    if not dotnet:
        print("error: dotnet was not found on PATH.", file=sys.stderr)
        return 1
    if not check_template(dotnet):
        return 2

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        staging = Path(
            tempfile.mkdtemp(prefix=f".{output.name}-", dir=str(output.parent))
        )
    except OSError as error:
        print(f"error: could not create the staging directory: {error}", file=sys.stderr)
        return 1

    try:
        generated = run(
            [
                dotnet,
                "new",
                "blas1mod",
                "-n",
                f"Blasphemous.{args.name}",
                "-m",
                title,
                "-au",
                author,
                "-o",
                str(staging),
            ]
        )
        if generated.returncode != 0:
            print(generated.stdout, file=sys.stderr, end="")
            print(generated.stderr, file=sys.stderr, end="")
            raise RuntimeError("dotnet new blas1mod failed.")

        apply_overlay(staging, args.name, game_version, title, author, dotnet)

        if os.path.lexists(output):
            raise RuntimeError(f"Output path appeared during generation: {output}")
        # The wrapper stays offline; restore/build verification belongs to tests.
        staging.rename(output)
    except (OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        if staging.exists():
            failed = staging.with_name(f"{staging.name}.failed")
            index = 1
            while failed.exists():
                failed = staging.with_name(f"{staging.name}.failed-{index}")
                index += 1
            try:
                staging.rename(failed)
                print(f"staging preserved at {failed}", file=sys.stderr)
            except OSError as error:
                print(f"error: could not preserve staging: {error}", file=sys.stderr)

    print(f"Created {output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
