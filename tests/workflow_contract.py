import re
from pathlib import Path


# Audited 2026-11-17: these action majors declare the Node 24 runtime.
SUPPORTED_EXTERNAL_ACTIONS = frozenset(
    {
        "actions/checkout@v7",
        "actions/setup-dotnet@v6",
        "actions/setup-python@v7",
        "NuGet/login@v1",
    }
)


def assert_supported_workflow_actions(repository_root):
    root = Path(repository_root)
    workflow_paths = []
    for relative_directory in (
        Path(".github") / "workflows",
        Path("TemplateRepo") / ".github" / "workflows",
    ):
        directory = root / relative_directory
        if not directory.is_dir():
            continue
        workflow_paths.extend(
            path
            for path in sorted(directory.iterdir())
            if path.is_file() and path.suffix in {".yml", ".yaml"}
        )

    for path in workflow_paths:
        workflow = path.read_text(encoding="utf-8")
        for reference in re.findall(
            r"(?m)^\s*(?:-\s*)?uses:\s+([^\s#]+)",
            workflow,
        ):
            if reference.startswith("./"):
                continue
            if reference not in SUPPORTED_EXTERNAL_ACTIONS:
                raise AssertionError(
                    f"{path}: unsupported external action {reference}"
                )
    return tuple(workflow_paths)


def workflow_step(workflow, name):
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(.*?)(?=^      - name: |\Z)",
        workflow,
    )
    if not match:
        raise AssertionError(f"Workflow step not found: {name}")
    return match.group(1)


def assert_nuget_release_guards(workflow, publish_name="Publish NuGet package"):
    warning_step = workflow_step(workflow, "Warn when NuGet username is missing")
    login_step = workflow_step(workflow, "NuGet login")
    publish_step = workflow_step(workflow, publish_name)

    if "if: env.NUGET_USERNAME == ''" not in warning_step:
        raise AssertionError("The missing-username warning step lost its guard.")
    if "if: env.NUGET_USERNAME != ''" in warning_step:
        raise AssertionError("The warning step has the publish guard.")
    if "Write-Warning" not in warning_step:
        raise AssertionError("The warning step no longer warns.")

    if "if: env.NUGET_USERNAME != ''" not in login_step:
        raise AssertionError("The NuGet login step lost its guard.")
    if "if: env.NUGET_USERNAME == ''" in login_step:
        raise AssertionError("The login step has the missing-username guard.")
    if "id: nuget_login" not in login_step:
        raise AssertionError("The login step lost its id.")
    if "NuGet/login@v1" not in login_step:
        raise AssertionError("The login step no longer uses NuGet/login.")

    if "if: env.NUGET_USERNAME != ''" not in publish_step:
        raise AssertionError("The NuGet publish step lost its guard.")
    if "if: env.NUGET_USERNAME == ''" in publish_step:
        raise AssertionError("The publish step has the missing-username guard.")
    if "dotnet nuget push" not in publish_step:
        raise AssertionError("The publish step no longer pushes NuGet.")
    if "steps.nuget_login.outputs.NUGET_API_KEY" not in publish_step:
        raise AssertionError("The publish step lost the login output.")
    for swallowing in (
        "continue-on-error",
        "|| true",
        "2>$null",
        "-ErrorAction SilentlyContinue",
    ):
        if swallowing in publish_step:
            raise AssertionError(
                f"The NuGet publish step can swallow failures with {swallowing!r}."
            )
    return publish_step
