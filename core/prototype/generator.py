"""Copy a locally selected template and render its root index.html; no preview."""

import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .models import PrototypeManifest, PrototypeRequest, PrototypeResult
from .renderer import render_index


def safe_slug(company_name: str) -> str:
    text = unicodedata.normalize("NFKD", company_name).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:64].rstrip("-")
    if not slug:
        return "prototype"
    if slug in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}:
        return "prototype-" + slug
    return slug


def serialize_manifest(manifest: PrototypeManifest) -> str:
    """Explicit UTF-8-ready JSON text, stable ordering and ISO 8601 timestamp."""
    return json.dumps({
        "prototype_id": manifest.prototype_id,
        "company_name": manifest.company_name,
        "segment": manifest.segment,
        "template_id": manifest.template_id,
        "template_version": manifest.template_version,
        "created_at": manifest.created_at.isoformat(),
        "source": manifest.source,
        "qualification_score": manifest.qualification_score,
    }, ensure_ascii=False, indent=2) + "\n"


def _reject_links(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise ValueError(f"Links/junctions are not allowed: {path}")


def generate_prototype(request: PrototypeRequest) -> PrototypeResult:
    """Generate only upon an explicit call. Never overwrite an existing directory.

    All template symlinks/junctions are rejected, including internal ones. A
    failure removes only this call's newly-created child directory. The output
    root may remain empty. Cleanup failure is reported with the remaining path.
    Local directories are assumed not to be modified concurrently by an attacker.
    """
    destination = None
    root = None
    prototype_id = None
    created = False
    try:
        if not isinstance(request, PrototypeRequest):
            raise TypeError("Expected PrototypeRequest")
        source_path = Path(request.template.template_path)
        _reject_links(source_path)
        source = source_path.resolve(strict=True)
        if not source.is_dir():
            raise ValueError("Template path must be a directory")
        root = Path(request.output_directory).resolve()
        if root.is_relative_to(source) or source.is_relative_to(root):
            raise ValueError("Template and output directories must not overlap")
        entries = []

        def inspect(directory):
            for entry in sorted(directory.iterdir()):
                _reject_links(entry)
                if not entry.resolve().is_relative_to(source):
                    raise ValueError(f"Template entry escapes root: {entry}")
                if entry.name.lower() == "prototype.json" and entry.parent == source:
                    raise ValueError("prototype.json is reserved for the generated manifest")
                if entry.is_dir():
                    entries.append((entry, True))
                    inspect(entry)
                elif entry.is_file():
                    if entry != source / "template.json":
                        entries.append((entry, False))
                else:
                    raise ValueError(f"Unsupported template entry: {entry}")

        inspect(source)
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve(strict=True)
        prototype_id = str(uuid4())
        destination = root / f"{safe_slug(request.lead.company_name)}-{prototype_id}"
        if destination.resolve().parent != root:
            raise ValueError("Unsafe output path")
        destination.mkdir(exist_ok=False)
        created = True
        for entry, is_directory in entries:
            _reject_links(entry)
            target = destination / entry.relative_to(source)
            if is_directory:
                target.mkdir()
            elif entry == source / "index.html":
                target.write_text(render_index(entry.read_text(encoding="utf-8"), request.lead), encoding="utf-8")
            else:
                shutil.copy2(entry, target)
        manifest = PrototypeManifest(
            prototype_id=prototype_id, company_name=request.lead.company_name,
            segment=request.lead.segment, template_id=request.template.template_id,
            template_version=request.template.version, created_at=datetime.now(timezone.utc),
            source="loung_prospect", qualification_score=request.lead.qualification_score,
        )
        with (destination / "prototype.json").open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(serialize_manifest(manifest))
        return PrototypeResult("created", prototype_id, str(destination), manifest)
    except Exception as error:
        warnings = []
        remaining = None
        if created:
            try:
                _reject_links(destination)
                if destination.resolve().parent != root:
                    raise ValueError("Rollback path escaped output root")
                shutil.rmtree(destination)
            except Exception as cleanup_error:
                remaining = str(destination)
                warnings.append(f"rollback_failed: {type(cleanup_error).__name__}: {cleanup_error}")
        return PrototypeResult(
            "failed", prototype_id=prototype_id, output_path=remaining,
            errors=[f"generation_failed: {type(error).__name__}: {error}"], warnings=warnings,
        )
