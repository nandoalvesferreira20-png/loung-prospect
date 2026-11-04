"""Per-user settings, Windows discovery and asynchronous fallback without external IO."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import browser_launcher as launcher


@pytest.mark.parametrize("browser,relative,executable", [
    ("edge", "Microsoft/Edge/Application", "msedge.exe"),
    ("chrome", "Google/Chrome/Application", "chrome.exe")])
@pytest.mark.parametrize("variable", ["LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"])
def test_common_windows_installations(tmp_path, monkeypatch, browser, relative, executable, variable):
    path = tmp_path / "Program Files With Spaces" / relative / executable
    path.parent.mkdir(parents=True)
    path.touch()
    monkeypatch.setattr(launcher, "registry_paths", lambda executable: iter(()))
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: None)
    assert launcher.find_browser(browser, environ={variable: str(tmp_path / "Program Files With Spaces")}) == path


def test_registry_and_path_discovery(tmp_path, monkeypatch):
    path = tmp_path / "msedge.exe"
    path.touch()
    monkeypatch.setattr(launcher, "registry_paths", lambda executable: iter([path]))
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: None)
    assert launcher.find_browser("edge", environ={}) == path
    monkeypatch.setattr(launcher, "registry_paths", lambda executable: iter([tmp_path / "missing.exe"]))
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: str(path))
    assert launcher.find_browser("edge", environ={}) == path
    monkeypatch.setattr(launcher.shutil, "which", lambda executable: None)
    assert launcher.find_browser("edge", environ={}) is None


def test_registry_reads_user_machine_and_both_views(monkeypatch, tmp_path):
    winreg = pytest.importorskip("winreg")
    opened = Mock()
    opened.return_value.__enter__ = Mock(return_value="handle")
    opened.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(winreg, "OpenKey", opened)
    monkeypatch.setenv("SYNTHETIC_BROWSER_ROOT", str(tmp_path))
    monkeypatch.setattr(winreg, "QueryValueEx", lambda *args: ('"%SYNTHETIC_BROWSER_ROOT%\\msedge.exe"', winreg.REG_SZ))
    assert list(launcher.registry_paths("msedge.exe")) == [tmp_path / "msedge.exe"] * 4
    assert {call.args[0] for call in opened.call_args_list} == {winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE}
    assert {call.args[3] for call in opened.call_args_list} == {
        winreg.KEY_READ | winreg.KEY_WOW64_64KEY, winreg.KEY_READ | winreg.KEY_WOW64_32KEY}


@pytest.mark.parametrize("browser", ["edge", "chrome"])
def test_named_browser_uses_argument_list_and_keeps_url_intact(tmp_path, monkeypatch, browser):
    path = tmp_path / "Program Files" / "browser.exe"
    monkeypatch.setattr(launcher, "find_browser", lambda selected: path)
    process = Mock()
    monkeypatch.setattr(launcher.subprocess, "Popen", process)
    url = "https://wa.me/5511999991234?text=Ol%C3%A1%21%0ACaf%C3%A9+%26+ideias"
    assert launcher.open_browser(url, browser)
    process.assert_called_once_with([str(path), url], shell=False, close_fds=True)


def test_default_and_missing_browsers(tmp_path, monkeypatch):
    default = Mock(return_value=True)
    monkeypatch.setattr(launcher.webbrowser, "open", default)
    assert launcher.open_browser("https://wa.me/example")
    default.assert_called_once_with("https://wa.me/example", new=2)
    monkeypatch.setattr(launcher, "find_browser", lambda selected: None)
    with pytest.raises(launcher.BrowserNotFoundError):
        launcher.open_browser("https://wa.me/example", "edge")
    monkeypatch.setattr(launcher, "find_browser", lambda selected: tmp_path / "chrome.exe")
    monkeypatch.setattr(launcher.subprocess, "Popen", Mock(side_effect=FileNotFoundError()))
    with pytest.raises(launcher.BrowserNotFoundError):
        launcher.open_browser("https://wa.me/example", "chrome")
    with pytest.raises(ValueError):
        launcher.open_browser("https://wa.me/example", "unknown")
