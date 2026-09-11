"""Open an explicitly selected, trusted local prototype; no server or generation.

The browser renders the local document normally, including its scripts. This is
not an HTML sandbox: callers must use trusted generated content. This module
does not fetch scripts or resources, nor inspect arbitrary HTML dependencies.
"""

from pathlib import Path
import webbrowser

from .models import PrototypeResult, PrototypeStatus


class PrototypePreviewError(ValueError):
    """Invalid preview result/path or failure to dispatch to the browser."""


def get_preview_path(result: PrototypeResult) -> Path:
    """Return a validated absolute index path contained in the output directory.

    Reject traversal components and a symlink/junction at the selected root or
    index. No global output root is assumed: generation permits configured roots.
    """
    if not isinstance(result, PrototypeResult) or result.status != PrototypeStatus.CREATED:
        raise PrototypePreviewError("Preview requires a created PrototypeResult")
    if not result.output_path:
        raise PrototypePreviewError("Missing output_path")
    try:
        output = Path(result.output_path)
        if ".." in output.parts:
            raise PrototypePreviewError("Traversal components are not allowed in output_path")
        if output.is_symlink() or output.is_junction():
            raise PrototypePreviewError("Prototype directory cannot be a link/junction")
        root = output.resolve(strict=True)
        if not root.is_dir():
            raise PrototypePreviewError("output_path must be a directory")
        index = root / "index.html"
        if index.is_symlink() or index.is_junction():
            raise PrototypePreviewError("index.html cannot be a link/junction")
        resolved = index.resolve(strict=True)
        if not resolved.is_relative_to(root) or not resolved.is_file():
            raise PrototypePreviewError("index.html must be a file inside the prototype directory")
        return resolved
    except (OSError, RuntimeError) as error:
        raise PrototypePreviewError(f"Cannot locate local prototype preview: {error}") from error


def open_preview(result: PrototypeResult) -> None:
    """Dispatch a file URI to the default browser; a false return is an error."""
    path = get_preview_path(result)
    try:
        opened = webbrowser.open(path.as_uri(), new=2)
    except Exception as error:
        raise PrototypePreviewError(f"Could not open prototype preview: {error}") from error
    if not opened:
        raise PrototypePreviewError("Default browser did not accept the preview request")
