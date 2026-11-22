import json
import re
import tempfile
import unittest
from pathlib import Path

from workflow_contract import (
    assert_nuget_release_guards,
    assert_supported_workflow_actions,
    assert_validation_trigger_contract,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
GLOBAL_JSON = REPO_ROOT / "global.json"
VALIDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "validate.yml"
SPEC_VALIDATE_WORKFLOW = (
    REPO_ROOT / ".github" / "workflows" / "spec-validate.yml"
)
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


class RepositoryWorkflowTests(unittest.TestCase):
    def test_dotnet_sdk_is_pinned_to_ten(self):
        sdk = json.loads(GLOBAL_JSON.read_text(encoding="utf-8"))["sdk"]

        self.assertEqual(sdk["version"], "10.0.100")
        self.assertEqual(sdk["rollForward"], "latestFeature")
        self.assertFalse(sdk["allowPrerelease"])

    def test_all_workflows_use_supported_external_actions(self):
        workflows = assert_supported_workflow_actions(REPO_ROOT)

        self.assertEqual(
            {path.relative_to(REPO_ROOT).as_posix() for path in workflows},
            {
                ".github/workflows/release.yml",
                ".github/workflows/spec-validate.yml",
                ".github/workflows/validate.yml",
                "TemplateRepo/.github/workflows/build.yml",
                "TemplateRepo/.github/workflows/discord.yml",
                "TemplateRepo/.github/workflows/release.yml",
            },
        )

    def test_validation_workflow_trigger_contract(self):
        workflow = VALIDATE_WORKFLOW.read_text(encoding="utf-8")
        assert_validation_trigger_contract(workflow)

    def test_validation_workflow_trigger_contract_rejects_bad_branches(self):
        workflow = (
            "on:\n"
            "  pull_request:\n"
            "    branches: [main, test-ci]\n"
            "  push:\n"
            "    branches:\n"
            "      - main\n"
            "      - test-ci\n"
            "jobs:\n"
        )
        assert_validation_trigger_contract(workflow)
        invalid_branch_lists = (
            "    branches: [main]",
            "    branches: [main, test-ci, release]",
            '    branches: [main, "test-ci]',
            "    branches:\n"
            "      - main\n"
            "      - test-ci\n"
            "\n"
            "      - release",
            "    branches:\n"
            "      - main\n"
            "      # comments do not end the branch block\n"
            "      - test-ci\n"
            "      - release",
        )

        for event, valid_branch_list in (
            ("pull_request", "    branches: [main, test-ci]\n"),
            ("push", "    branches:\n      - main\n      - test-ci\n"),
        ):
            for invalid_branch_list in invalid_branch_lists:
                with self.subTest(event=event, branches=invalid_branch_list):
                    invalid_workflow = workflow.replace(
                        valid_branch_list,
                        invalid_branch_list + "\n",
                        1,
                    )
                    with self.assertRaises(AssertionError):
                        assert_validation_trigger_contract(invalid_workflow)

        for event, valid_branch_list in (
            ("pull_request", "    branches: [main, test-ci]\n"),
            ("push", "    branches:\n      - main\n      - test-ci\n"),
        ):
            with self.subTest(event=event, branches="spaced block"):
                spaced_workflow = workflow.replace(
                    valid_branch_list,
                    "    branches:\n"
                    "      - main\n"
                    "\n"
                    "      # a comment inside the list\n"
                    "      - test-ci\n",
                    1,
                )
                assert_validation_trigger_contract(spaced_workflow)

        comment_cases = (
            ("zero", "# zero-indent comment"),
            ("two", "  # two-space comment"),
            ("four", "    # four-space comment"),
            ("six", "      # six-space comment"),
        )
        for name, comment in comment_cases:
            with self.subTest(comment=name, branches="extra after comment"):
                commented_workflow = workflow.replace(
                    "    branches:\n      - main\n      - test-ci\n",
                    "    branches:\n"
                    "      - main\n"
                    f"{comment}\n"
                    "      - test-ci\n"
                    "      - release\n",
                    1,
                )
                with self.assertRaises(AssertionError):
                    assert_validation_trigger_contract(commented_workflow)

        assert_validation_trigger_contract(
            "on:\n"
            "# zero-space comment\n"
            "  pull_request:\n"
            "  # two-space comment\n"
            "    branches: [main, test-ci]\n"
            "  push:\n"
            "  # two-space comment\n"
            "    branches:\n"
            "    # four-space comment\n"
            "      - main\n"
            "      # six-space comment\n"
            "      - test-ci\n"
            "jobs:\n"
        )

    def test_action_contract_rejects_unknown_and_ignores_local_workflows(self):
        artifacts = REPO_ROOT / "tmp"
        artifacts.mkdir(parents=True, exist_ok=True)
        root = Path(tempfile.mkdtemp(dir=artifacts))
        workflow_dir = root / ".github" / "workflows"
        workflow_dir.mkdir(parents=True)
        workflow = workflow_dir / "contract.yml"
        workflow.write_text(
            "jobs:\n  test:\n    steps:\n      - uses: example/action@v1\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(
            AssertionError, "unsupported external action example/action@v1"
        ):
            assert_supported_workflow_actions(root)

        workflow.write_text(
            "jobs:\n  test:\n    uses: ./.github/workflows/reusable.yml\n",
            encoding="utf-8",
        )
        self.assertEqual(
            assert_supported_workflow_actions(root),
            (workflow,),
        )

    def test_validation_workflow_contract(self):
        workflow = VALIDATE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_call:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertIn("Verify checkout HEAD matches event SHA", workflow)
        self.assertIn("git rev-parse HEAD", workflow)
        self.assertIn("$env:GITHUB_SHA", workflow)
        self.assertIn("windows-latest", workflow)
        self.assertIn("dotnet-version: 10.0.x", workflow)
        self.assertIn("python-version: 3.9", workflow)
        self.assertIn('BLAS1_DISPOSABLE_TEST_CONTEXT: "1"', workflow)
        self.assertIn("Check PATH isolation preflight", workflow)
        self.assertLess(
            workflow.index("Check PATH isolation preflight"),
            workflow.index("Download official template packages"),
        )
        self.assertIn("Download official template packages", workflow)
        self.assertNotIn("dotnet new install", workflow)
        self.assertIn("Blasphemous.Modding.Templates.1.4.1.nupkg", workflow)
        self.assertIn("Blasphemous.Modding.Templates.1.4.0.nupkg", workflow)
        self.assertIn("BLAS1_TEMPLATE_PACKAGE", workflow)
        self.assertIn("BLAS1_WRONG_TEMPLATE_PACKAGE", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)
        self.assertIn("Record validation evidence", workflow)
        self.assertIn("$env:GITHUB_RUN_ID", workflow)
        self.assertIn("$env:GITHUB_STEP_SUMMARY", workflow)
        self.assertLess(
            workflow.index("Checkout Repository"),
            workflow.index("Verify checkout HEAD matches event SHA"),
        )
        self.assertLess(
            workflow.index("Verify checkout HEAD matches event SHA"),
            workflow.index("Download official template packages"),
        )
        self.assertLess(
            workflow.index("Run tests"),
            workflow.index("Record validation evidence"),
        )

    def test_spec_validation_workflow_contract(self):
        workflow = SPEC_VALIDATE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("push:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertIn('      - "spec-ci/**"', workflow)
        self.assertIn("uses: ./.github/workflows/validate.yml", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertNotIn("concurrency:", workflow)

    def test_release_workflow_contract(self):
        workflow = RELEASE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn('tags: ["**"]', workflow)
        self.assertIn("uses: ./.github/workflows/validate.yml", workflow)
        self.assertIn("needs: validate", workflow)
        self.assertIn("contents: read", workflow)
        self.assertEqual(workflow.count("id-token: write"), 1)
        self.assertNotIn("contents: write", workflow)
        self.assertIn("windows-latest", workflow)
        self.assertIn("dotnet-version: 10.0.x", workflow)
        self.assertIn("fetch-depth: 0", workflow)
        self.assertIn("git fetch --no-tags origin main", workflow)
        self.assertIn("git merge-base --is-ancestor", workflow)
        self.assertLess(
            workflow.index("git merge-base --is-ancestor"),
            workflow.index("dotnet pack"),
        )
        pattern = re.search(r"\$pattern = '([^']+)'", workflow).group(1)
        self.assertIsNotNone(re.fullmatch(pattern, "v1.2.3"))
        self.assertIsNotNone(re.fullmatch(pattern, "1.2.3-beta.1"))
        self.assertIsNotNone(re.fullmatch(pattern, "v1.2.3+build.7"))
        self.assertIsNone(re.fullmatch(pattern, "release-1.2.3"))
        self.assertIn(
            '"PACKAGE_VERSION=$($tag -creplace \'^v\', \'\')"',
            workflow,
        )
        self.assertIn("Blasphemous1.ModTest.Templates.csproj", workflow)
        self.assertIn("-p:PackageVersion=$env:PACKAGE_VERSION", workflow)
        self.assertIn("Blasphemous1.ModTest.Templates", workflow)
        self.assertIn("NUGET_USERNAME", workflow)

        publish_step = assert_nuget_release_guards(
            workflow, "Publish template package"
        )
        self.assertIn("--skip-duplicate", publish_step)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("secrets.NUGET_API_KEY", workflow)
        self.assertNotIn("gh release", workflow)
        self.assertNotIn("actions/create-release", workflow)
        self.assertNotIn("actions/upload-release-asset", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
