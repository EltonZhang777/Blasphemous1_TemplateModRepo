# Keep meta-repository and generated-repository documentation independent

## Status

Accepted

## Context

The meta-repository root and `TemplateRepo/` contain files with the same names, including `AGENTS.md`, `README.md`, and files under `docs/agents/`. Their audiences, commands, and operational boundaries differ: root documents govern the meta-repository, while Overlay documents become the documentation of a generated Mod repository. Treating the same-named files as mirrors produced synchronization and equality requirements that obscured those different contexts.

## Decision

- Treat root documentation as Meta-Repository Documentation and Overlay documentation as Generated Repository Documentation.
- Do not require same-named documents across those contexts to be synchronized, byte-identical, or semantically equivalent.
- Apply the single-authority rule within each documentation context rather than across contexts.
- Require each context to validate its own local links and commands.
- Keep generated documentation independent of the parent repository and do not add cross-context mirroring tests.

## Considered Options

- **Cross-context mirroring or equality checks**: Rejected because a mirror must either contain meta-repository-only commands or remove context needed by the other audience.
- **Independent contexts with local validation**: Chosen because each repository can document the commands and boundaries its readers actually use.
- **Selected semantic-marker checks across copies**: Rejected because matching markers do not establish that differently scoped documents are equivalent.

## Consequences

Maintainers and agents must edit and review each documentation context against its own purpose; a change in one context does not imply a change in the other. Similar-looking text may diverge, so any future proposal to reintroduce cross-context synchronization or equality tests requires superseding this decision.
