import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VALIDATE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "validate.yml"


class RepositoryWorkflowTests(unittest.TestCase):
    def test_validation_workflow_contract(self):
        workflow = VALIDATE_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("push:", workflow)
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


if __name__ == "__main__":
    unittest.main()
