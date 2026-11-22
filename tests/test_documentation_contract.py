from contextlib import nullcontext
import tempfile
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


class _NonSwallowingAssertions(unittest.TestCase):
    def subTest(self, **kwargs):
        return nullcontext()


class DocumentationContractTests(unittest.TestCase):
    def test_reference_style_local_links_resolve(self):
        context = "Meta-Repository Documentation"
        with tempfile.TemporaryDirectory() as temporary:
            owner_root = Path(temporary)
            target = owner_root / "target.md"
            target.write_text("# Existing Heading\n", encoding="utf-8")
            source = owner_root / "index.md"
            source.write_text(
                "[Inline](target.md#existing-heading)\n"
                "[Full reference][full]\n"
                "[collapsed][]\n"
                "[shortcut]\n"
                "[HTTP][http]\n"
                "[HTTPS][https]\n"
                "[mail][mail]\n"
                "\n"
                "[full]: target.md#existing-heading\n"
                "[collapsed]: target.md#existing-heading\n"
                "[shortcut]: target.md#existing-heading\n"
                "[http]: http://example.com\n"
                "[https]: https://example.com\n"
                "[mail]: mailto:maintainer@example.com\n",
                encoding="utf-8",
            )

            assert_markdown_contract(
                self,
                context=context,
                owner_root=owner_root,
                sources=(source,),
            )

    def test_reference_style_links_cannot_escape_owner_root(self):
        context = "Meta-Repository Documentation"
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary)
            owner_root = workspace / "meta"
            docs = owner_root / "docs"
            docs.mkdir(parents=True)
            (workspace / "generated").mkdir()
            outside_target = workspace / "generated" / "outside.md"
            outside_target.write_text("# Outside\n", encoding="utf-8")
            source = docs / "index.md"
            source.write_text(
                "[Outside][outside]\n"
                "\n"
                "[outside]: ../../generated/outside.md#outside\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                AssertionError,
                f"{context}: local link escapes its documentation boundary",
            ):
                assert_markdown_contract(
                    _NonSwallowingAssertions(),
                    context=context,
                    owner_root=owner_root,
                    sources=(source,),
                )

    def test_reference_style_links_report_missing_anchors(self):
        context = "Generated Repository Documentation"
        with tempfile.TemporaryDirectory() as temporary:
            owner_root = Path(temporary)
            target = owner_root / "target.md"
            target.write_text("# Existing Heading\n", encoding="utf-8")
            source = owner_root / "index.md"
            source.write_text(
                "[Missing anchor][target]\n"
                "\n"
                "[target]: target.md#missing-heading\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                AssertionError,
                f"{context}: missing link anchor #missing-heading",
            ):
                assert_markdown_contract(
                    _NonSwallowingAssertions(),
                    context=context,
                    owner_root=owner_root,
                    sources=(source,),
                )

    def test_reference_style_links_use_first_duplicate_definition(self):
        context = "Focused Documentation"
        with tempfile.TemporaryDirectory() as temporary:
            owner_root = Path(temporary)
            (owner_root / "valid.md").write_text("# Valid\n", encoding="utf-8")
            source = owner_root / "index.md"
            source.write_text(
                "[Duplicate][target]\n"
                "\n"
                "[target]: missing.md\n"
                "[target]: valid.md\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                AssertionError,
                f"{context}: local link target does not exist",
            ):
                assert_markdown_contract(
                    _NonSwallowingAssertions(),
                    context=context,
                    owner_root=owner_root,
                    sources=(source,),
                )

    def test_reference_style_links_report_missing_targets(self):
        context = "Focused Documentation"
        links = {
            "full": "[Full reference][missing]",
            "collapsed": "[missing][]",
            "shortcut": "[missing]",
        }

        with tempfile.TemporaryDirectory() as temporary:
            owner_root = Path(temporary)
            source = owner_root / "index.md"
            for style, link in links.items():
                with self.subTest(style=style):
                    source.write_text(
                        f"{link}\n\n[missing]: missing.md\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        AssertionError,
                        f"{context}: local link target does not exist",
                    ):
                        assert_markdown_contract(
                            _NonSwallowingAssertions(),
                            context=context,
                            owner_root=owner_root,
                            sources=(source,),
                        )

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
