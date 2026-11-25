import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from test_mod_test_template import (
    assert_markdown_contract,
    wayfinding_prerequisite_clauses,
)
from types import SimpleNamespace
from unittest import mock

from path_safety import disposable_dotnet_test
from workflow_contract import (
    assert_nuget_release_guards,
    assert_supported_workflow_actions,
    workflow_step,
)


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

EXPECTED_EDITORCONFIG_GLOBAL = {
    "charset": "utf-8",
    "end_of_line": "crlf",
    "insert_final_newline": "true",
    "trim_trailing_whitespace": "true",
    "indent_style": "space",
    "indent_size": "4",
}
EXPECTED_CSHARP_RULES = {
    "csharp_indent_block_contents": "true",
    "csharp_indent_braces": "false",
    "csharp_indent_case_contents": "true",
    "csharp_indent_case_contents_when_block": "true",
    "csharp_indent_labels": "one_less_than_current",
    "csharp_indent_switch_labels": "true",
    "csharp_new_line_before_catch": "true",
    "csharp_new_line_before_else": "true",
    "csharp_new_line_before_finally": "true",
    "csharp_new_line_before_members_in_anonymous_types": "true",
    "csharp_new_line_before_members_in_object_initializers": "true",
    "csharp_new_line_before_open_brace": "all",
    "csharp_new_line_between_query_expression_clauses": "true",
    "csharp_prefer_braces": "true",
    "csharp_prefer_simple_default_expression": "true",
    "csharp_prefer_simple_using_statement": "true",
    "csharp_prefer_static_anonymous_function": "true",
    "csharp_prefer_static_local_function": "true",
    "csharp_prefer_system_threading_lock": "true",
    "csharp_preferred_modifier_order": "public,private,protected,internal,file,static,extern,new,virtual,abstract,closed,sealed,override,readonly,unsafe,required,volatile,async",
    "csharp_preserve_single_line_blocks": "true",
    "csharp_preserve_single_line_statements": "true",
    "csharp_space_after_cast": "false",
    "csharp_space_after_colon_in_inheritance_clause": "true",
    "csharp_space_after_comma": "true",
    "csharp_space_after_dot": "false",
    "csharp_space_after_keywords_in_control_flow_statements": "true",
    "csharp_space_after_semicolon_in_for_statement": "true",
    "csharp_space_around_binary_operators": "before_and_after",
    "csharp_space_around_declaration_statements": "false",
    "csharp_space_before_colon_in_inheritance_clause": "true",
    "csharp_space_before_comma": "false",
    "csharp_space_before_dot": "false",
    "csharp_space_before_open_square_brackets": "false",
    "csharp_space_before_semicolon_in_for_statement": "false",
    "csharp_space_between_empty_square_brackets": "false",
    "csharp_space_between_method_call_empty_parameter_list_parentheses": "false",
    "csharp_space_between_method_call_name_and_opening_parenthesis": "false",
    "csharp_space_between_method_call_parameter_list_parentheses": "false",
    "csharp_space_between_method_declaration_empty_parameter_list_parentheses": "false",
    "csharp_space_between_method_declaration_name_and_open_parenthesis": "false",
    "csharp_space_between_method_declaration_parameter_list_parentheses": "false",
    "csharp_space_between_parentheses": "false",
    "csharp_space_between_square_brackets": "false",
    "csharp_style_allow_blank_line_after_colon_in_constructor_initializer_experimental": "true",
    "csharp_style_allow_blank_line_after_token_in_arrow_expression_clause_experimental": "true",
    "csharp_style_allow_blank_line_after_token_in_conditional_expression_experimental": "false",
    "csharp_style_allow_blank_lines_between_consecutive_braces_experimental": "false",
    "csharp_style_allow_embedded_statements_on_same_line_experimental": "false",
    "csharp_style_conditional_delegate_call": "true",
    "csharp_style_deconstructed_variable_declaration": "true",
    "csharp_style_expression_bodied_accessors": "true",
    "csharp_style_expression_bodied_constructors": "false",
    "csharp_style_expression_bodied_indexers": "true",
    "csharp_style_expression_bodied_lambdas": "true",
    "csharp_style_expression_bodied_local_functions": "false",
    "csharp_style_expression_bodied_methods": "when_on_single_line",
    "csharp_style_expression_bodied_operators": "false",
    "csharp_style_expression_bodied_properties": "true",
    "csharp_style_implicit_object_creation_when_type_is_apparent": "true",
    "csharp_style_inlined_variable_declaration": "true",
    "csharp_style_namespace_declarations": "file_scoped",
    "csharp_style_pattern_matching_over_as_with_null_check": "true",
    "csharp_style_pattern_matching_over_is_with_cast_check": "true",
    "csharp_style_prefer_extended_property_pattern": "true",
    "csharp_style_prefer_implicitly_typed_lambda_expression": "true",
    "csharp_style_prefer_index_operator": "true",
    "csharp_style_prefer_labeled_jump_statements": "true",
    "csharp_style_prefer_local_over_anonymous_function": "true",
    "csharp_style_prefer_method_group_conversion": "true",
    "csharp_style_prefer_not_pattern": "true",
    "csharp_style_prefer_null_check_over_type_check": "false",
    "csharp_style_prefer_pattern_matching": "true",
    "csharp_style_prefer_primary_constructors": "true",
    "csharp_style_prefer_range_operator": "true",
    "csharp_style_prefer_readonly_struct": "true",
    "csharp_style_prefer_readonly_struct_member": "true",
    "csharp_style_prefer_simple_property_accessors": "true",
    "csharp_style_prefer_switch_expression": "true",
    "csharp_style_prefer_top_level_statements": "true",
    "csharp_style_prefer_tuple_swap": "true",
    "csharp_style_prefer_unbound_generic_type_in_nameof": "true",
    "csharp_style_prefer_utf8_string_literals": "true",
    "csharp_style_throw_expression": "true",
    "csharp_style_unused_value_assignment_preference": "discard_variable",
    "csharp_style_unused_value_expression_statement_preference": "discard_variable",
    "csharp_style_var_elsewhere": "false",
    "csharp_style_var_for_built_in_types": "false",
    "csharp_style_var_when_type_is_apparent": "false",
    "csharp_using_directive_placement": "outside_namespace",
    "dotnet_code_quality_unused_parameters": "non_public",
    "dotnet_hide_advanced_members": "false",
    "dotnet_member_insertion_location": "with_other_members_of_the_same_kind",
    "dotnet_naming_rule.interface_should_be_begins_with_i.severity": "suggestion",
    "dotnet_naming_rule.interface_should_be_begins_with_i.style": "begins_with_i",
    "dotnet_naming_rule.interface_should_be_begins_with_i.symbols": "interface",
    "dotnet_naming_rule.non_field_members_should_be_pascal_case.severity": "suggestion",
    "dotnet_naming_rule.non_field_members_should_be_pascal_case.style": "pascal_case",
    "dotnet_naming_rule.non_field_members_should_be_pascal_case.symbols": "non_field_members",
    "dotnet_naming_rule.types_should_be_pascal_case.severity": "suggestion",
    "dotnet_naming_rule.types_should_be_pascal_case.style": "pascal_case",
    "dotnet_naming_rule.types_should_be_pascal_case.symbols": "types",
    "dotnet_naming_style.begins_with_i.capitalization": "pascal_case",
    "dotnet_naming_style.begins_with_i.required_prefix": "I",
    "dotnet_naming_style.begins_with_i.required_suffix": "",
    "dotnet_naming_style.begins_with_i.word_separator": "",
    "dotnet_naming_style.pascal_case.capitalization": "pascal_case",
    "dotnet_naming_style.pascal_case.required_prefix": "",
    "dotnet_naming_style.pascal_case.required_suffix": "",
    "dotnet_naming_style.pascal_case.word_separator": "",
    "dotnet_naming_symbols.interface.applicable_accessibilities": "public, internal, private, protected, protected_internal, private_protected",
    "dotnet_naming_symbols.interface.applicable_kinds": "interface",
    "dotnet_naming_symbols.interface.required_modifiers": "",
    "dotnet_naming_symbols.non_field_members.applicable_accessibilities": "public, internal, private, protected, protected_internal, private_protected",
    "dotnet_naming_symbols.non_field_members.applicable_kinds": "property, event, method",
    "dotnet_naming_symbols.non_field_members.required_modifiers": "",
    "dotnet_naming_symbols.types.applicable_accessibilities": "public, internal, private, protected, protected_internal, private_protected",
    "dotnet_naming_symbols.types.applicable_kinds": "class, struct, interface, enum",
    "dotnet_naming_symbols.types.required_modifiers": "",
    "dotnet_prefer_system_hash_code": "true",
    "dotnet_property_generation_behavior": "prefer_throwing_properties",
    "dotnet_remove_unnecessary_suppression_exclusions": "none",
    "dotnet_search_reference_assemblies": "true",
    "dotnet_separate_import_directive_groups": "false",
    "dotnet_sort_system_directives_first": "false",
    "dotnet_style_allow_multiple_blank_lines_experimental": "false",
    "dotnet_style_allow_statement_immediately_after_block_experimental": "true",
    "dotnet_style_coalesce_expression": "true",
    "dotnet_style_collection_initializer": "true",
    "dotnet_style_explicit_tuple_names": "true",
    "dotnet_style_namespace_match_folder": "true",
    "dotnet_style_null_propagation": "true",
    "dotnet_style_object_initializer": "true",
    "dotnet_style_operator_placement_when_wrapping": "beginning_of_line",
    "dotnet_style_parentheses_in_arithmetic_binary_operators": "always_for_clarity",
    "dotnet_style_parentheses_in_other_binary_operators": "always_for_clarity",
    "dotnet_style_parentheses_in_other_operators": "never_if_unnecessary",
    "dotnet_style_parentheses_in_relational_binary_operators": "always_for_clarity",
    "dotnet_style_predefined_type_for_locals_parameters_members": "true",
    "dotnet_style_predefined_type_for_member_access": "true",
    "dotnet_style_prefer_auto_properties": "true",
    "dotnet_style_prefer_collection_expression": "when_types_loosely_match",
    "dotnet_style_prefer_compound_assignment": "true",
    "dotnet_style_prefer_conditional_expression_over_assignment": "true",
    "dotnet_style_prefer_conditional_expression_over_return": "true",
    "dotnet_style_prefer_foreach_explicit_cast_in_source": "when_strongly_typed",
    "dotnet_style_prefer_inferred_anonymous_type_member_names": "true",
    "dotnet_style_prefer_inferred_tuple_names": "true",
    "dotnet_style_prefer_is_null_check_over_reference_equality_method": "true",
    "dotnet_style_prefer_non_hidden_explicit_cast_in_source": "true",
    "dotnet_style_prefer_simplified_boolean_expressions": "true",
    "dotnet_style_prefer_simplified_interpolation": "true",
    "dotnet_style_qualification_for_event": "false",
    "dotnet_style_qualification_for_field": "false",
    "dotnet_style_qualification_for_method": "false",
    "dotnet_style_qualification_for_property": "false",
    "dotnet_style_readonly_field": "true",
    "dotnet_style_require_accessibility_modifiers": "for_non_interface_members",
    "end_of_line": "crlf",
    "file_header_template": "unset",
    "indent_size": "4",
    "indent_style": "space",
    "tab_width": "4",
}
EXPECTED_GITIGNORE_RULES = [
    ".vs/",
    "bin/",
    "obj/",
    "publish/",
    "TestResults/",
    "*.user",
    "*.suo",
    "*.userosscache",
    "*.sln.docstates",
    ".vshistory/",
    "*.nupkg",
    "*.snupkg",
    "*.pfx",
    "*.publishsettings",
    ".wt/",
    "tmp/",
    "AGENTS.local.md",
    ".serena/",
    "docs/handoff/",
]
README_IDENTITY_PLACEHOLDERS = (
    "@TITLE@",
    "@PROJECT_NAME@",
    "@MACHINE_IDENTIFIER@",
    "@TITLE_CSHARP@",
    "@AUTHOR@",
    "@AUTHOR_CSHARP@",
)
GENERATED_IDENTITY_PLACEHOLDERS = (
    *README_IDENTITY_PLACEHOLDERS,
    "MOD_TITLE_PLACEHOLDER",
    "MOD_AUTHOR_PLACEHOLDER",
    "TARGET_PROJECT_PLACEHOLDER",
    "Blasphemous1.ModTest",
    "__BLASPHEMOUS_DISPLAY_TITLE__",
    "__BLASPHEMOUS_AUTHOR__",
)
GENERATED_AGENT_DOCUMENTS = (
    Path("AGENTS.md"),
    Path("docs/agents/domain.md"),
    Path("docs/agents/issue-tracker.md"),
    Path("docs/agents/triage-labels.md"),
)
GENERATED_TRIAGE_LABELS = (
    "needs-triage",
    "needs-info",
    "ready-for-agent",
    "ready-for-human",
    "wontfix",
)
GENERATED_SKILL_ENTRYPOINT = re.compile(r"(?<![\w/])/[a-z][a-z0-9-]+\b")
WAYFINDING_GOLDEN = """## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
"""


def normalize_markdown_newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse_editorconfig(text):
    root_values = {}
    sections = {}
    current = root_values
    current_section = "<root>"
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(("#", ";")):
            continue
        if line.startswith("[") and line.endswith("]"):
            if line in sections:
                raise ValueError(f"Duplicate EditorConfig section {line!r}.")
            current_section = line
            current = sections[line] = {}
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip().lower()
            if key in current:
                raise ValueError(
                    f"Duplicate EditorConfig key {key!r} in {current_section}."
                )
            current[key] = value.strip()
    return root_values, sections


def editorconfig_value(sections, section, key):
    values = sections[section]
    if key in values:
        return values[key]
    return sections.get("[*]", {}).get(key)


def parse_ignore_rules(text):
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_wrapper_module():
    spec = importlib.util.spec_from_file_location("new_blas1mod", WRAPPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EditorConfigParserTests(unittest.TestCase):
    def test_expected_csharp_rules_match_checked_in_overlay(self):
        _, sections = parse_editorconfig(
            (REPO_ROOT / "TemplateRepo" / ".editorconfig").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(sections["[*.cs]"], EXPECTED_CSHARP_RULES)

    def test_duplicate_sections_are_rejected_before_merge(self):
        text = "[*.other]\nfirst = one\n[*.other]\nsecond = two\n"

        with self.assertRaisesRegex(ValueError, "Duplicate EditorConfig section"):
            parse_editorconfig(text)

    def test_duplicate_keys_within_a_section_are_rejected(self):
        text = "[*.other]\nindent_size = 2\nindent_size = 4\n"

        with self.assertRaisesRegex(ValueError, "Duplicate EditorConfig key"):
            parse_editorconfig(text)

    def test_case_variant_duplicate_keys_within_a_section_are_rejected(self):
        text = "[*.other]\nindent_size = 2\nINDENT_SIZE = 4\n"

        with self.assertRaisesRegex(ValueError, "Duplicate EditorConfig key"):
            parse_editorconfig(text)

    def test_values_preserve_case_and_trim_surrounding_whitespace(self):
        _, sections = parse_editorconfig(
            "[*.cs]\ninsert_final_newline =  TRUE  \n"
        )

        self.assertEqual(sections["[*.cs]"]["insert_final_newline"], "TRUE")

    def test_required_interface_prefix_preserves_uppercase_i(self):
        _, sections = parse_editorconfig(
            "[*.cs]\n"
            "DOTNET_NAMING_STYLE.BEGINS_WITH_I.REQUIRED_PREFIX = I\n"
        )

        self.assertEqual(
            sections["[*.cs]"],
            {"dotnet_naming_style.begins_with_i.required_prefix": "I"},
        )

    def test_required_interface_prefix_rejects_lowercase_i(self):
        _, sections = parse_editorconfig(
            "[*.cs]\n"
            "DOTNET_NAMING_STYLE.BEGINS_WITH_I.REQUIRED_PREFIX = i\n"
        )

        self.assertEqual(
            sections["[*.cs]"],
            {"dotnet_naming_style.begins_with_i.required_prefix": "i"},
        )
        self.assertNotEqual(
            sections["[*.cs]"],
            {"dotnet_naming_style.begins_with_i.required_prefix": "I"},
        )

    def test_same_key_in_different_sections_is_valid(self):
        _, sections = parse_editorconfig(
            "[*.cs]\nindent_size = 4\n[*.xml]\nindent_size = 2\n"
        )

        self.assertEqual(sections["[*.cs]"]["indent_size"], "4")
        self.assertEqual(sections["[*.xml]"]["indent_size"], "2")


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

    def assert_author_readme(
        self,
        readme,
        project_name,
        machine_identifier,
        title,
        *,
        verification_mod_project_exists,
    ):
        context = "Generated Repository Documentation"
        self.assertTrue(
            readme.is_file(),
            f"{context}: generated README does not exist: {readme}",
        )
        text = readme.read_text(encoding="utf-8")
        self.assertTrue(
            text.strip(),
            f"{context}: generated README is empty: {readme}",
        )
        lines = text.splitlines()
        self.assertEqual(
            lines[0],
            f"# {title}",
            f"{context}: generated README title contract failed",
        )
        self.assertEqual(
            sum(line.startswith("# ") for line in lines),
            1,
            f"{context}: generated README must have one top-level heading",
        )

        headings = [
            "## Requirements",
            "### Development prerequisites",
            "### In-game testing prerequisites",
            "## Build and test",
            "## Development deployment",
            "## Resources and Mod Package",
            "## Verification Mod",
            "## CI and releases",
        ]
        for heading in headings:
            with self.subTest(
                context=context,
                contract="generated-readme-heading",
                heading=heading,
            ):
                self.assertIn(
                    heading,
                    lines,
                    f"{context}: missing README heading: {heading}",
                )
        self.assertEqual(
            [lines.index(heading) for heading in headings],
            sorted(lines.index(heading) for heading in headings),
            f"{context}: generated README headings are out of order",
        )

        required = (
            "dotnet --version",
            "Blasphemous 1",
            "BepInEx",
            "ModdingAPI 3.0.1",
            f"dotnet restore {project_name}.sln",
            f"dotnet build {project_name}.sln --no-restore",
            f"dotnet test {project_name}.sln --no-build",
            "net48",
            "xUnit",
            "net35",
            "does not require Blasphemous, Unity, or BepInEx",
            ".\\dotnet_format.bat",
            "changes tracked source files",
            f"dotnet format whitespace {project_name}.sln --no-restore "
            "--verify-no-changes",
            f"dotnet format style {project_name}.sln --no-restore "
            "--severity warn --verify-no-changes",
            "read-only validation",
            "-p:DeployToGame=true",
            '-p:DevFolder="C:\\path\\to\\Blasphemous\\Modding"',
            "must already exist",
            f"plugins/{machine_identifier}.dll",
            "visually confirm",
            "resources/",
            f"publish/{machine_identifier}.zip",
            "entry assembly",
            "relative directory layout",
            "every file under `resources/`",
            "including `.gitkeep` when `resources/` is otherwise empty",
            "Automated Test Project outputs are not included",
            "Dependency DLLs are not included",
            f"same `publish/{machine_identifier}.zip` package",
            f"If `{project_name}.TestMod/{project_name}.TestMod.csproj` exists",
            "No Verification Mod directory is expected when that project file is absent",
            f"{project_name}.TestMod/publish/{project_name}.TestMod.zip",
            f"plugins/{project_name}.TestMod.dll",
            "STARTUP_READY",
            "extract the Verification Mod archive",
            "manual in-game verification",
            "SemVer",
            "draft",
            "replaces the asset in an existing draft",
            "already published release is refused",
            "git tag 1.2.3",
            "git push origin 1.2.3",
            "only the main Mod Package",
            "Windows with .NET 10",
            "builds in Release",
            "formatting verification",
            "[Build workflow](.github/workflows/build.yml)",
            "[Release workflow](.github/workflows/release.yml)",
            "CRLF",
            "NuGet",
            "Discord",
            "warn",
            "skip",
        )
        for value in required:
            with self.subTest(
                context=context,
                contract="generated-readme-required-fact",
                marker=value,
            ):
                self.assertIn(
                    value,
                    text,
                    f"{context}: generated README required fact is missing: "
                    f"{value}",
                )

        forbidden = (
            "Official Template Baseline",
            "Blasphemous.Modding.Templates",
            "dotnet new install",
            "AGENTS.md",
            "docs/agents",
            "git clone",
            "## License",
            "## Contributing",
            "When generated with the optional Verification Mod",
            "../",
            "..\\",
            "Blasphemous1_TemplateModRepo",
            "tools/new_blas1mod.py",
        )
        for value in forbidden:
            with self.subTest(
                context=context,
                contract="generated-readme-self-containment",
                marker=value,
            ):
                self.assertNotIn(
                    value,
                    text,
                    f"{context}: generated README contains forbidden "
                    f"repository dependency: {value}",
                )

        ordered_command_groups = (
            (
                "restore-build-test",
                (
                    f"dotnet restore {project_name}.sln",
                    f"dotnet build {project_name}.sln --no-restore",
                    f"dotnet test {project_name}.sln --no-build",
                ),
            ),
            (
                "push-main-create-tag-push-tag",
                (
                    "git push origin main",
                    "git tag 1.2.3",
                    "git push origin 1.2.3",
                ),
            ),
        )
        for contract, commands in ordered_command_groups:
            positions = tuple(text.find(command) for command in commands)
            with self.subTest(context=context, contract=contract):
                self.assertNotIn(
                    -1,
                    positions,
                    f"{context}: ordered command is missing for {contract}: "
                    f"{commands}",
                )
                self.assertEqual(
                    tuple(sorted(positions)),
                    positions,
                    f"{context}: commands are out of order for {contract}: "
                    f"{' -> '.join(commands)}",
                )

        verification_project = (
            readme.parent
            / f"{project_name}.TestMod"
            / f"{project_name}.TestMod.csproj"
        )
        if verification_mod_project_exists is not None:
            existence_assert = (
                self.assertTrue
                if verification_mod_project_exists
                else self.assertFalse
            )
            existence_assert(
                verification_project.is_file(),
                f"{context}: Verification Mod project presence does not match "
                f"the generated repository: {verification_project}",
            )
        self.assertNotIn(
            f"]({project_name}.TestMod",
            text,
            f"{context}: Verification Mod directory must not be a mandatory "
            "local link",
        )
        assert_markdown_contract(
            self,
            context=context,
            owner_root=readme.parent,
            sources=(readme,),
        )
        return text

    def assert_no_readme_placeholders(self, text):
        for placeholder in README_IDENTITY_PLACEHOLDERS:
            with self.subTest(
                context="Generated Repository Documentation",
                contract="identity-substitution",
                placeholder=placeholder,
            ):
                self.assertNotIn(
                    placeholder,
                    text,
                    "Generated Repository Documentation: unresolved identity "
                    f"placeholder: {placeholder}",
                )

    def assert_generated_agent_guidance(
        self, owner_root, project_name, *, generated
    ):
        context = "Generated Repository Documentation"
        sources = tuple(owner_root / relative for relative in GENERATED_AGENT_DOCUMENTS)
        missing = tuple(str(source) for source in sources if not source.is_file())
        if missing:
            self.fail(
                f"{context}: agent-document-exists: missing generated agent "
                f"documents: {', '.join(missing)}"
            )

        agents = (owner_root / "AGENTS.md").read_text(encoding="utf-8")
        domain = (owner_root / "docs" / "agents" / "domain.md").read_text(
            encoding="utf-8"
        )
        issue_tracker = (
            owner_root / "docs" / "agents" / "issue-tracker.md"
        ).read_text(encoding="utf-8")
        triage = (owner_root / "docs" / "agents" / "triage-labels.md").read_text(
            encoding="utf-8"
        )

        agent_required = (
            f"# {project_name}",
            "[README.md](README.md)",
            "complete commands and workflow conditions",
            "AGENTS.local.md",
            "not required",
            "Game deployment is opt-in",
            "DeployToGame",
            f"`{project_name}.csproj`",
            f"`{project_name}.Tests`",
            "non-packable",
            "resources/",
            "Automated Test Project output and dependency DLLs",
            "Mod Package",
        )
        for marker in agent_required:
            with self.subTest(
                context=context,
                contract="agent-guidance-required",
                marker=marker,
            ):
                self.assertIn(
                    marker,
                    agents,
                    f"{context}: generated agent guidance is missing: {marker}",
                )
        self.assertNotIn(
            "```",
            agents,
            f"{context}: complete workflow command blocks belong in README.md",
        )
        for command in (
            "dotnet restore",
            "dotnet build",
            "dotnet test",
            ".\\dotnet_format.bat",
            "-p:DeployToGame=true",
            "-p:DevFolder=",
        ):
            self.assertNotIn(
                command,
                agents,
                f"{context}: generated agent guidance repeats a README "
                f"command: {command}",
            )
        self.assertNotIn(
            "](AGENTS.local.md)",
            agents,
            f"{context}: AGENTS.local.md must remain an optional natural-language "
            "reference",
        )

        domain_required = (
            "`README.md`",
            "`AGENTS.md`",
            f"`{project_name}.csproj`",
            f"`{project_name}.Tests`",
            "`resources/`",
            "`docs/agents/`",
        )
        for marker in domain_required:
            with self.subTest(
                context=context,
                contract="domain-routing-required",
                marker=marker,
            ):
                self.assertIn(
                    marker,
                    domain,
                    f"{context}: generated domain routing is missing: {marker}",
                )
        for marker in (
            "GLOSSARY.md",
            "GLOSSARY-MAP.md",
            "docs/adr/",
            "src/",
            "ordering",
            "billing",
            "multi-context",
            "Single-context repo",
            "Multi-context repo",
            "/domain-modeling",
            "/grill-with-docs",
            "/improve-codebase-architecture",
        ):
            self.assertNotIn(
                marker,
                domain,
                f"{context}: generated domain routing contains an unavailable "
                f"path or entrypoint: {marker}",
            )

        self.assertIn(
            "## Wayfinding operations",
            issue_tracker,
            f"{context}: retained Wayfinding section is missing",
        )
        normalized_issue_tracker = normalize_markdown_newlines(issue_tracker)
        operations, wayfinding = normalized_issue_tracker.split(
            "## Wayfinding operations", 1
        )
        operation_headings = (
            "### Create an issue",
            "### Read an issue",
            "### List issues",
            "### Comment on an issue",
            "### Add a label",
            "### Close an issue",
        )
        issue_required = (
            "$IssueNumber",
            "@'\n## Summary",
            'gh issue create --title "..." --body-file -',
            "gh issue view $IssueNumber --json "
            "number,title,body,state,labels,comments,parent,subIssues",
            "gh issue list --state open --json "
            "number,title,body,state,labels,comments,parent,subIssues",
            "gh issue comment $IssueNumber --body-file .\\comment.md",
            'gh issue edit $IssueNumber --add-label "ready-for-agent"',
            'gh issue close $IssueNumber --reason completed --comment "..."',
            "Pull requests are not a feature-request surface.",
        )
        for marker in issue_required:
            with self.subTest(
                context=context,
                contract="issue-tracker-required",
                marker=marker,
            ):
                self.assertIn(
                    marker,
                    operations,
                    f"{context}: generated issue tracker is missing: {marker}",
                )
        for heading in operation_headings:
            self.assertEqual(
                1,
                operations.count(heading),
                f"{context}: issue operation must have one canonical "
                f"description: {heading}",
            )
        for marker in (
            "Use a heredoc",
            "When set to",
            "gh pr ",
            "## When a skill says",
            "Read or fetch",
            "--remove-label",
        ):
            self.assertNotIn(
                marker,
                operations,
                f"{context}: generated issue tracker contains a duplicate, "
                f"placeholder, or unavailable operation: {marker}",
            )
        self.assertEqual(
            0,
            operations.count("/wayfinder"),
            f"{context}: Wayfinding text must remain after its heading",
        )
        self.assertIn(
            "Used by `/wayfinder`.",
            wayfinding,
            f"{context}: retained Wayfinding guidance is missing",
        )
        self.assertEqual(
            WAYFINDING_GOLDEN,
            f"## Wayfinding operations{wayfinding}",
            f"{context}: retained Wayfinding guidance changed",
        )
        self.assertEqual(
            (),
            wayfinding_prerequisite_clauses(wayfinding),
            f"{context}: Wayfinding must not add an installation prerequisite",
        )

        for label in GENERATED_TRIAGE_LABELS:
            with self.subTest(
                context=context,
                contract="triage-label-authority",
                label=label,
            ):
                self.assertEqual(
                    1,
                    triage.count(f"`{label}`"),
                    f"{context}: triage labels must be a direct unique list: "
                    f"{label}",
                )
        for marker in (
            "mattpocock",
            "| Label",
            "The skills speak",
            "Edit the right-hand column",
            "/triage",
        ):
            self.assertNotIn(
                marker,
                triage,
                f"{context}: triage labels must not delegate to another "
                f"authority: {marker}",
            )

        combined = "\n".join((agents, domain, issue_tracker, triage))
        outside_wayfinding = "\n".join((agents, domain, operations, triage))
        self.assertEqual(
            [],
            GENERATED_SKILL_ENTRYPOINT.findall(outside_wayfinding),
            f"{context}: unavailable skill entrypoints remain in generated "
            "agent guidance",
        )
        for marker in (
            "../",
            "..\\",
            "TemplateRepo",
            "Overlay Root",
            "Blasphemous1_TemplateModRepo",
            "tools/new_blas1mod.py",
            "docs/create-mod-repository.md",
            "AGENTS.delivery.md",
        ):
            self.assertNotIn(
                marker,
                combined,
                f"{context}: generated agent guidance depends on the parent "
                f"repository: {marker}",
            )
        if generated:
            for placeholder in GENERATED_IDENTITY_PLACEHOLDERS:
                self.assertNotIn(
                    placeholder,
                    combined,
                    f"{context}: unresolved identity placeholder in generated "
                    f"agent guidance: {placeholder}",
                )

        assert_markdown_contract(
            self,
            context=context,
            owner_root=owner_root,
            sources=sources,
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

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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
            "Modinfo",
            "MODINFO",
            "MAIN",
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

    @disposable_dotnet_test
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

    def test_run_forces_english_cli_language(self):
        wrapper = load_wrapper_module()
        completed = subprocess.CompletedProcess(["dotnet"], 0, "", "")
        with mock.patch.object(
            wrapper.subprocess, "run", return_value=completed
        ) as run:
            wrapper.run(["dotnet", "new", "uninstall"])

        self.assertEqual(
            run.call_args.kwargs["env"]["DOTNET_CLI_UI_LANGUAGE"], "en-US"
        )

    def test_colliding_project_names_are_case_insensitive(self):
        wrapper = load_wrapper_module()
        for name in (
            "Modinfo",
            "MODINFO",
            "MAIN",
            "Modtemplate",
            "Templatemod",
        ):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    wrapper.validate_machine_identifier(name)

    def test_overlay_readme_preserves_author_contract(self):
        readme = REPO_ROOT / "TemplateRepo" / "README.md"
        self.assert_author_readme(
            readme,
            "@PROJECT_NAME@",
            "@MACHINE_IDENTIFIER@",
            "@TITLE@",
            verification_mod_project_exists=None,
        )

    def test_overlay_agent_guidance_is_self_contained(self):
        self.assert_generated_agent_guidance(
            REPO_ROOT / "TemplateRepo",
            "@PROJECT_NAME@",
            generated=False,
        )

    @disposable_dotnet_test
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
        self.assertTrue((output / ".editorconfig").is_file())
        self.assertTrue((output / ".gitattributes").is_file())
        self.assertTrue((output / ".gitignore").is_file())
        editorconfig_root, editorconfig_sections = parse_editorconfig(
            (output / ".editorconfig").read_text(encoding="utf-8")
        )
        self.assertEqual(editorconfig_root, {"root": "true"})
        self.assertEqual(
            editorconfig_sections["[*]"], EXPECTED_EDITORCONFIG_GLOBAL
        )
        csharp_rules = editorconfig_sections["[*.cs]"]
        self.assertEqual(csharp_rules, EXPECTED_CSHARP_RULES)
        self.assertEqual(
            editorconfig_value(
                editorconfig_sections,
                "[*.cs]",
                "insert_final_newline",
            ),
            "true",
        )
        self.assertEqual(
            editorconfig_sections["[*.{sln,csproj,xml,props,targets}]"],
            {"indent_size": "2"},
        )
        ignore_rules = parse_ignore_rules(
            (output / ".gitignore").read_text(encoding="utf-8")
        )
        self.assertEqual(ignore_rules, EXPECTED_GITIGNORE_RULES)
        self.assertEqual(len(ignore_rules), 19)
        self.assertIn(
            "*.cs text eol=crlf",
            (output / ".gitattributes").read_text(encoding="utf-8"),
        )
        self.assertTrue((output / ".worktreeinclude").is_file())
        self.assertTrue((output / "dotnet_format.bat").is_file())
        self.assertTrue((output / ".config" / "wt.toml").is_file())
        workflow_dir = output / ".github" / "workflows"
        self.assertTrue((workflow_dir / "build.yml").is_file())
        self.assertTrue((workflow_dir / "release.yml").is_file())
        self.assertTrue((workflow_dir / "discord.yml").is_file())
        self.assertEqual(
            assert_supported_workflow_actions(output),
            (
                workflow_dir / "build.yml",
                workflow_dir / "discord.yml",
                workflow_dir / "release.yml",
            ),
        )
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
        readme = output / "README.md"
        readme_text = self.assert_author_readme(
            readme,
            "Blasphemous.Example",
            "Example",
            "My Mod Template",
            verification_mod_project_exists=False,
        )
        self.assert_no_readme_placeholders(readme_text)
        self.assert_generated_agent_guidance(
            output,
            "Blasphemous.Example",
            generated=True,
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
                *README_IDENTITY_PLACEHOLDERS,
            ):
                self.assertNotIn(placeholder, text, str(path))

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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

    @disposable_dotnet_test
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
        readme = output / "README.md"
        readme_text = self.assert_author_readme(
            readme,
            project_name,
            "WithTest",
            title,
            verification_mod_project_exists=True,
        )
        self.assert_no_readme_placeholders(readme_text)
        self.assert_generated_agent_guidance(
            output,
            project_name,
            generated=True,
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

    @disposable_dotnet_test
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
