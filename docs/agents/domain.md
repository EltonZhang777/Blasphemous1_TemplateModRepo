# Domain Docs

Use this repository's vocabulary and architecture decisions while exploring or changing the codebase.

## Before exploring, read these

- Read **`GLOSSARY.md`** at the repository root.
- Read the accepted decisions under **`docs/adr/`** that touch the area you will work on.

This meta-repository keeps its domain vocabulary at `GLOSSARY.md` and its architecture decisions at `docs/adr/`. The files under `TemplateRepo/` become Generated Repository Documentation after generation and are a separate documentation context.

Do not create a glossary or architecture decision in advance. If a file relevant to the task does not exist, continue without it.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `GLOSSARY.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need is absent, reconsider whether you are inventing terminology. If the current task resolves a real vocabulary gap, update `GLOSSARY.md` directly in the same change.

## Record decisions

If the current task resolves a qualifying architecture decision, record it in a new file under `docs/adr/` using the existing numbered format and state its status.

## Flag ADR conflicts

If a proposed change contradicts an accepted, non-superseded architecture decision:

1. Stop only the affected change. Unaffected work may continue.
2. Cite the decision and the contradiction.
3. Ask the maintainer whether to revise the proposal, explicitly supersede the decision, or abandon the conflicting part.
4. Do not silently edit the decision or claim the affected work complete.
