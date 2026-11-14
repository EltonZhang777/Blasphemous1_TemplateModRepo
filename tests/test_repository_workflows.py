import re
import unittest
from pathlib import Path

from workflow_contract import workflow_step


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "validate.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "release.yml"


class RepositoryWorkflowTests(unittest.TestCase):
    def test_validation_workflow_contract(self):
        workflow = VALIDATE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("push:", workflow)
        self.assertIn("workflow_call:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertNotIn("contents: write", workflow)
        self.assertNotIn("id-token: write", workflow)
        self.assertIn("windows-latest", workflow)
        self.assertIn("dotnet-version: 10.0.x", workflow)
        self.assertIn("python-version: 3.9", workflow)
        self.assertIn("official-template-hive", workflow)
        self.assertIn("dotnet new install $official", workflow)
        self.assertIn("Blasphemous.Modding.Templates.1.4.1.nupkg", workflow)
        self.assertIn("Blasphemous.Modding.Templates.1.4.0.nupkg", workflow)
        self.assertIn("BLAS1_TEMPLATE_PACKAGE", workflow)
        self.assertIn("BLAS1_WRONG_TEMPLATE_PACKAGE", workflow)
        self.assertIn("python -m unittest discover -s tests -v", workflow)

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
        self.assertIn("NuGet/login@v1", workflow)
        self.assertIn("NUGET_USERNAME", workflow)
        self.assertEqual(workflow.count("if: env.NUGET_USERNAME == ''"), 1)
        self.assertIn("Write-Warning", workflow)
        self.assertEqual(workflow.count("if: env.NUGET_USERNAME != ''"), 2)
        self.assertIn("steps.nuget_login.outputs.NUGET_API_KEY", workflow)
        publish_step = workflow_step(workflow, "Publish template package")
        self.assertIn("dotnet nuget push", publish_step)
        self.assertIn("--skip-duplicate", publish_step)
        self.assertNotIn("continue-on-error", workflow)
        self.assertNotIn("secrets.NUGET_API_KEY", workflow)
        self.assertNotIn("gh release", workflow)
        self.assertNotIn("actions/create-release", workflow)
        self.assertNotIn("actions/upload-release-asset", workflow)
        self.assertNotIn("softprops/action-gh-release", workflow)


if __name__ == "__main__":
    unittest.main()
