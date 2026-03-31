"""Template registry — alias-indexed in-memory template store.

Scans a templates directory at startup, parses and validates all *.rpt.md
files, and builds a case-insensitive alias-to-LoadedTemplate index.

Per D-01: Invalid templates cause a fatal startup error.
Per D-02: All validation errors are collected before raising.
Per D-04: Empty or missing directory is fatal.
Per D-09: Registry is a class instance constructed with a path.
Per D-10: get_template() returns a LoadedTemplate (parsed once, cached).
Per D-11: reload() re-scans for debugging. No hot-reload.
"""

import pathlib

from .composer import compose_template
from .loader import LoadedTemplate, load_template, discover_templates
from .exceptions import (
    TemplateNotFoundError,
    TemplateValidationError,
    TemplateLoadError,
)


class TemplateRegistry:
    """In-memory template index built at startup.

    Scans templates_dir recursively for *.rpt.md files, parses and validates
    all templates, builds a case-insensitive alias-to-template index.

    Args:
        templates_dir: Path to the templates root directory.

    Raises:
        TemplateValidationError: If any template fails validation,
            if duplicate aliases exist, or if no templates are found.
    """

    def __init__(self, templates_dir: str | pathlib.Path) -> None:
        self._templates_dir = pathlib.Path(templates_dir)
        self._alias_index: dict[str, LoadedTemplate] = {}
        self._load_all()

    def _load_all(self) -> None:
        """Scan, parse, validate all templates and build alias index.

        Two-pass loading: first pass loads all templates and registers base
        template aliases. Second pass composes composite templates (those with
        composable_from) via compose_template() and registers their aliases.

        Per D-02: Collects ALL errors across all templates before raising.
        Per D-04: Raises if no *.rpt.md files found.
        Per D-12: Duplicate aliases across files are fatal, naming both files.
        """
        errors: list[TemplateLoadError] = []

        # discover_templates raises if dir doesn't exist (D-04)
        paths = discover_templates(self._templates_dir)

        # D-04: No templates found is fatal
        if not paths:
            raise TemplateValidationError(
                [TemplateLoadError(
                    str(self._templates_dir),
                    "No *.rpt.md templates found in directory"
                )]
            )

        alias_sources: dict[str, str] = {}  # normalized alias -> source file path
        new_index: dict[str, LoadedTemplate] = {}
        base_templates: dict[str, LoadedTemplate] = {}  # rel_path -> template
        composite_raws: list[tuple[pathlib.Path, LoadedTemplate]] = []

        # First pass: load all, separate bases from composites
        for path in paths:
            try:
                template = load_template(path)
            except TemplateValidationError as e:
                errors.extend(e.errors)
                continue

            rel_path = path.relative_to(self._templates_dir).as_posix()
            if template.schema.composable_from is not None:
                composite_raws.append((path, template))
            else:
                base_templates[rel_path] = template
                # Register base aliases with collision detection (D-12)
                for alias in template.schema.aliases:
                    key = alias.strip().lower()  # D-08: case-insensitive
                    if key in alias_sources:
                        errors.append(TemplateLoadError(
                            str(path),
                            f"Alias '{key}' conflicts with {alias_sources[key]}"
                        ))
                    else:
                        alias_sources[key] = str(path)
                        new_index[key] = template

        # Second pass: compose composites
        for path, raw_template in composite_raws:
            try:
                composed = compose_template(raw_template, base_templates)
            except TemplateValidationError as e:
                errors.extend(e.errors)
                continue
            except Exception as e:
                errors.append(TemplateLoadError(str(path), str(e)))
                continue

            # Register composite aliases with collision detection (D-12)
            for alias in composed.schema.aliases:
                key = alias.strip().lower()
                if key in alias_sources:
                    errors.append(TemplateLoadError(
                        str(path),
                        f"Alias '{key}' conflicts with {alias_sources[key]}"
                    ))
                else:
                    alias_sources[key] = str(path)
                    new_index[key] = composed

        # D-01/D-02: Raise all collected errors at once
        if errors:
            raise TemplateValidationError(errors)

        self._alias_index = new_index

    def get_template(self, alias: str) -> LoadedTemplate:
        """Look up a template by study type alias.

        Per D-08: Case-insensitive matching (both stored and queried lowercase).
        Per D-20: Raises TemplateNotFoundError on miss.

        Args:
            alias: Study type alias string (e.g. "ct ap", "CT Thorax").

        Returns:
            The cached LoadedTemplate for the matching alias.

        Raises:
            TemplateNotFoundError: If no template matches the alias.
        """
        key = alias.strip().lower()
        if key not in self._alias_index:
            raise TemplateNotFoundError(alias, self.get_known_aliases())
        return self._alias_index[key]

    def get_known_aliases(self) -> list[str]:
        """Return a sorted list of all registered aliases.

        Per D-05: Exposes alias list for LLM classification stage 1
        to constrain against. The registry does NOT own the LLM call.

        Returns:
            Sorted list of lowercase alias strings.
        """
        return sorted(self._alias_index.keys())

    def reload(self) -> None:
        """Re-scan and rebuild the alias index.

        Per D-11: For debugging only. Production use is load-once-at-startup.
        Raises TemplateValidationError on any validation failure, same as __init__.
        """
        self._load_all()
