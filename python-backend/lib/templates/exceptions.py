"""Custom exceptions for the template loader and registry."""

from dataclasses import dataclass


@dataclass
class TemplateLoadError:
    """A single template validation failure."""
    file_path: str
    error: str


class TemplateValidationError(Exception):
    """Raised when one or more templates fail validation at startup.

    Per D-01: Invalid templates cause a fatal startup error.
    Per D-02: All errors are collected before raising.
    """
    def __init__(self, errors: list[TemplateLoadError]):
        self.errors = errors
        lines = [f"{len(errors)} template validation error(s):"]
        for e in errors:
            lines.append(f"  [{e.file_path}] {e.error}")
        super().__init__("\n".join(lines))


class TemplateNotFoundError(Exception):
    """Raised when an alias lookup finds no matching template.

    Per D-20: Caller must handle explicitly.
    """
    def __init__(self, alias: str, known_aliases: list[str]):
        self.alias = alias
        self.known_aliases = known_aliases
        super().__init__(
            f"No template found for alias '{alias}'. "
            f"Known aliases: {', '.join(known_aliases[:20])}"
        )
