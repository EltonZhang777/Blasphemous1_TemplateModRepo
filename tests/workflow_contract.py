import re


def workflow_step(workflow, name):
    match = re.search(
        rf"(?ms)^      - name: {re.escape(name)}\n(.*?)(?=^      - name: |\Z)",
        workflow,
    )
    if not match:
        raise AssertionError(f"Workflow step not found: {name}")
    return match.group(1)
