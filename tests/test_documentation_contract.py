import unittest
from pathlib import Path

from test_mod_test_template import assert_markdown_contract


REPO_ROOT = Path(__file__).resolve().parents[1]
ADR_0004 = REPO_ROOT / "docs" / "adr" / "0004-isolate-template-tests-from-user-path.md"
ADR_0007 = REPO_ROOT / "docs" / "adr" / "0007-use-disposable-spec-ci-lanes.md"
GLOSSARY = REPO_ROOT / "GLOSSARY.md"
ROOT_AGENTS = REPO_ROOT / "AGENTS.md"
PATH_SAFETY = REPO_ROOT / "tests" / "path_safety.py"
TEST_TEMPLATE_README = (
    REPO_ROOT / "Templates" / "Blasphemous1.ModTest.Templates" / "README.md"
)


class DocumentationContractTests(unittest.TestCase):
    def test_path_safety_documentation_links_resolve(self):
        assert_markdown_contract(
            self,
            context="Meta-Repository Documentation",
            owner_root=REPO_ROOT,
            sources=(ADR_0004, ADR_0007, GLOSSARY),
        )

    def test_path_safety_artifact_pointer_resolves(self):
        self.assertIn(
            "[tests/path_safety.py](../../tests/path_safety.py)",
            ADR_0004.read_text(encoding="utf-8"),
        )
        self.assertTrue(PATH_SAFETY.is_file())

    def test_meta_documentation_keeps_canonical_test_template_usage(self):
        self.assertIn(
            "[Test Template Package README]"
            "(Templates/Blasphemous1.ModTest.Templates/README.md)",
            ROOT_AGENTS.read_text(encoding="utf-8"),
        )
        self.assertRegex(
            TEST_TEMPLATE_README.read_text(encoding="utf-8"),
            r"(?m)^dotnet new blasmodtest -n\b",
        )

        self.assertIn(
            "The `blasmodtest` dotnet template",
            GLOSSARY.read_text(encoding="utf-8"),
        )


if __name__ == "__main__":
    unittest.main()
