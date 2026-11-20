# Issue tracker: GitHub

Issues and specs for this repo live as GitHub issues. Use the `gh` CLI for all operations.

Run these commands from the repository checkout. `gh` infers the repository from the Git remote. Set `$IssueNumber` to the target issue before running commands that use it.

## Issue operations

### Create an issue

Supply a multiline body through PowerShell standard input with explicit body-file mode:

```powershell
@'
## Summary

Describe the problem.
'@ | gh issue create --title "..." --body-file -
```

### Read an issue

Read the issue with structured JSON, including comments and parent or sub-issue relationships:

```powershell
gh issue view $IssueNumber --json number,title,body,state,labels,comments,parent,subIssues
```

### List issues

```powershell
gh issue list --state open --json number,title,body,state,labels,comments,parent,subIssues
```

### Comment on an issue

```powershell
gh issue comment $IssueNumber --body-file .\comment.md
```

### Add a label

```powershell
gh issue edit $IssueNumber --add-label "ready-for-agent"
```

### Close an issue

```powershell
gh issue close $IssueNumber --reason completed --comment "..."
```

## Pull requests

Pull requests are not a feature-request surface.

## Wayfinding operations

Used by `/wayfinder`. The **map** is a single issue with **child** issues as tickets.

- **Map**: a single issue labelled `wayfinder:map`, holding the Notes / Decisions-so-far / Fog body. `gh issue create --label wayfinder:map`.
- **Child ticket**: an issue linked to the map as a GitHub sub-issue (`gh api` on the sub-issues endpoint). Where sub-issues aren't enabled, add the child to a task list in the map body and put `Part of #<map>` at the top of the child body. Labels: `wayfinder:<type>` (`research`/`prototype`/`grilling`/`task`). Once claimed, the ticket is assigned to the driving dev.
- **Blocking**: GitHub's **native issue dependencies**, the canonical, UI-visible representation. Add an edge with `gh api --method POST repos/<owner>/<repo>/issues/<child>/dependencies/blocked_by -F issue_id=<blocker-db-id>`, where `<blocker-db-id>` is the blocker's numeric **database id** (`gh api repos/<owner>/<repo>/issues/<n> --jq .id`, _not_ the `#number` or `node_id`). GitHub reports `issue_dependencies_summary.blocked_by` (open blockers only, the live gate). Where dependencies aren't available, fall back to a `Blocked by: #<n>, #<n>` line at the top of the child body. A ticket is unblocked when every blocker is closed.
- **Frontier query**: list the map's open children (`gh issue list --state open`, scoped to the map's sub-issues / task list), drop any with an open blocker (`issue_dependencies_summary.blocked_by > 0`, or an open issue in the `Blocked by` line) or an assignee; first in map order wins.
- **Claim**: `gh issue edit <n> --add-assignee @me`, the session's first write.
- **Resolve**: `gh issue comment <n> --body "<answer>"`, then `gh issue close <n>`, then append a context pointer (gist + link) to the map's Decisions-so-far.
