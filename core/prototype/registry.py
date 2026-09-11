"""Local manifest discovery only; no generation or template execution."""

import json
from pathlib import Path

from .models import PrototypeTemplate

DEFAULT_TEMPLATE_DIRECTORY = Path(__file__).resolve().parents[2] / "templates"


class TemplateRegistryError(ValueError):
    """Invalid registry directory, manifest or duplicate identity."""


class TemplateNotFoundError(LookupError):
    """No registered template has the requested ID."""


class TemplateRegistry:
    """Read an explicit root on each query; immediate directories are templates.

    Each directory must contain template.json. Paths are derived locally and
    resolved; manifests cannot supply paths. Symlinks escaping the root are
    rejected. No lead data participates in discovery or path construction.
    """

    def __init__(self, directory: str | Path = DEFAULT_TEMPLATE_DIRECTORY):
        self.directory = Path(directory).resolve()

    def list_templates(self) -> list[PrototypeTemplate]:
        try:
            if not self.directory.is_dir():
                raise TemplateRegistryError(f"Template directory not found: {self.directory}")
            templates = {}
            for directory in sorted(self.directory.iterdir()):
                if not directory.is_dir():
                    continue
                resolved = directory.resolve()
                manifest = (directory / "template.json").resolve()
                if not resolved.is_relative_to(self.directory) or not manifest.is_relative_to(resolved):
                    raise TemplateRegistryError(f"Template path escapes its directory: {directory}")
                try:
                    data = json.loads(manifest.read_text(encoding="utf-8"))
                    required = {"template_id", "name", "segment", "version"}
                    if not isinstance(data, dict) or set(data) != required:
                        raise ValueError("Expected exactly template_id, name, segment and version")
                    template = PrototypeTemplate(**data, template_path=str(resolved))
                except (OSError, UnicodeError, ValueError, TypeError) as error:
                    raise TemplateRegistryError(f"Invalid template manifest {manifest}: {error}") from error
                if template.template_id in templates:
                    raise TemplateRegistryError(f"Duplicate template_id: {template.template_id}")
                templates[template.template_id] = template
            return sorted(templates.values(), key=lambda template: template.template_id)
        except OSError as error:
            raise TemplateRegistryError(f"Cannot read template directory {self.directory}: {error}") from error

    def get_template(self, template_id: str) -> PrototypeTemplate:
        for template in self.list_templates():
            if template.template_id == template_id:
                return template
        raise TemplateNotFoundError(f"Template not found: {template_id}")

    def find_templates_for_segment(self, segment: str) -> list[PrototypeTemplate]:
        normalized = segment.strip().lower()
        return [template for template in self.list_templates()
                if template.segment.strip().lower() == normalized]


def list_templates() -> list[PrototypeTemplate]:
    return TemplateRegistry().list_templates()


def get_template(template_id: str) -> PrototypeTemplate:
    return TemplateRegistry().get_template(template_id)


def find_templates_for_segment(segment: str) -> list[PrototypeTemplate]:
    return TemplateRegistry().find_templates_for_segment(segment)
