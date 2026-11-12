# Blasphemous 1 Mod Template

The cloneable Blasphemous 1 Mod template under `TemplateRepo/` and the language used to initialize and release a Mod made from it.

## Language

**Template Root**:
The directory that contains the complete cloneable template and is the command-line initializer's only supported working directory.
_Avoid_: template folder, repository root

**Template Content**:
The files and paths that belong to the cloneable template and can become part of a new Mod repository.
_Avoid_: template files

**Template-owned file**:
A file or path listed by the template as safe for initialization to inspect, change, or rename.
_Avoid_: project file

**Initialization**:
The confirmed conversion of Template Content and Placeholder Identity into one complete Mod Identity.
_Avoid_: rename, scaffold

**Placeholder Identity**:
The template's reserved machine name, display title, and author metadata that Initialization replaces.
_Avoid_: default name

**Mod Identity**:
The machine identifier, display title, and author selected for a Mod, together with the project, namespace, solution, test, and plugin names derived from them.
_Avoid_: project name

**Machine Identifier**:
The identifier-safe Mod name used for the project, namespace, solution, test, and plugin assembly names.
_Avoid_: slug, namespace

**Display Title**:
The human-readable Mod name used in metadata and documentation.
_Avoid_: mod name

**Mod Package**:
The release ZIP whose `plugins/<TargetName>.dll` file is the Mod entry assembly.
_Avoid_: release, bundle
