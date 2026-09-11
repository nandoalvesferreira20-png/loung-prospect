from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from core.prototype.models import PrototypeManifest, PrototypeResult
from core.prototype import preview


def result_for(path):
    manifest = PrototypeManifest("id", "Empresa", "dentista", "template", "1.0",
                                 datetime(2026, 1, 1, tzinfo=timezone.utc))
    return PrototypeResult("created", "id", str(path), manifest)


@pytest.fixture
def ready(tmp_path):
    folder = tmp_path / "Clínica São José"
    folder.mkdir()
    (folder / "index.html").write_text("<!doctype html><title>Teste</title>", encoding="utf-8")
    return result_for(folder)


def test_valid_path_and_nonmutation(ready):
    before = deepcopy(ready)
    assert preview.get_preview_path(ready) == Path(ready.output_path).resolve() / "index.html"
    assert ready == before


def test_failed_result():
    with pytest.raises(preview.PrototypePreviewError, match="created"):
        preview.get_preview_path(PrototypeResult("failed"))


def test_missing_output(tmp_path):
    with pytest.raises(preview.PrototypePreviewError, match="Cannot locate"):
        preview.get_preview_path(result_for(tmp_path / "missing"))


def test_output_is_file(tmp_path):
    file = tmp_path / "file"
    file.write_text("test")
    with pytest.raises(preview.PrototypePreviewError, match="directory"):
        preview.get_preview_path(result_for(file))


def test_missing_index(tmp_path):
    with pytest.raises(preview.PrototypePreviewError, match="Cannot locate"):
        preview.get_preview_path(result_for(tmp_path))


def test_index_is_directory(tmp_path):
    (tmp_path / "index.html").mkdir()
    with pytest.raises(preview.PrototypePreviewError, match="must be a file"):
        preview.get_preview_path(result_for(tmp_path))


def test_traversal_rejected(tmp_path):
    with pytest.raises(preview.PrototypePreviewError, match="Traversal"):
        preview.get_preview_path(result_for(tmp_path / "child" / ".."))


def test_index_link_rejected(ready, monkeypatch):
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path.name == "index.html" or original(path))
    with pytest.raises(preview.PrototypePreviewError, match="link"):
        preview.get_preview_path(ready)


def test_resolved_index_escape_rejected(ready, tmp_path, monkeypatch):
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda path, *args, **kwargs:
                        tmp_path / "outside.html" if path.name == "index.html" else original(path, *args, **kwargs))
    with pytest.raises(preview.PrototypePreviewError, match="inside"):
        preview.get_preview_path(ready)


def test_unicode_file_uri_and_mock_browser(ready, monkeypatch):
    browser = Mock(return_value=True)
    monkeypatch.setattr(preview.webbrowser, "open", browser)
    before = deepcopy(ready)
    assert preview.open_preview(ready) is None
    expected = (Path(ready.output_path) / "index.html").as_uri()
    browser.assert_called_once_with(expected, new=2)
    assert expected.startswith("file://") and "%20" in expected and "%C3" in expected
    assert ready == before


@pytest.mark.parametrize("failure", [False, RuntimeError("browser unavailable")])
def test_browser_failure(ready, monkeypatch, failure):
    browser = Mock(side_effect=failure) if isinstance(failure, Exception) else Mock(return_value=False)
    monkeypatch.setattr(preview.webbrowser, "open", browser)
    with pytest.raises(preview.PrototypePreviewError):
        preview.open_preview(ready)


def test_invalid_path_never_opens_browser(tmp_path, monkeypatch):
    browser = Mock()
    monkeypatch.setattr(preview.webbrowser, "open", browser)
    with pytest.raises(preview.PrototypePreviewError):
        preview.open_preview(result_for(tmp_path))
    browser.assert_not_called()
