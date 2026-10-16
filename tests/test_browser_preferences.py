"""Per-user settings, Windows discovery and asynchronous fallback without external IO."""
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import browser_launcher as launcher
from ui import settings
from ui.browser_action import BrowserAction
from ui.sales_workspace import ContactPanel, SalesWorkspacePage


@pytest.mark.parametrize("selected", ["default", "edge", "chrome"])
def test_preference_persists_and_preserves_other_settings(tmp_path, selected):
    path = tmp_path / "user" / "settings.json"
    store = settings.UserSettings(path)
    assert store.browser() == "default" and not path.exists()
    path.parent.mkdir()
    path.write_text(json.dumps({"another_setting": 42}), encoding="utf-8")
    store.save_browser(selected)
    assert settings.UserSettings(path).browser() == selected
    assert json.loads(path.read_text(encoding="utf-8"))["another_setting"] == 42
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("content", ["invalid json", "[]", "null", '{"whatsapp_browser":"unknown"}', '{"whatsapp_browser":[]}'])
def test_invalid_settings_fall_back_to_system_default(tmp_path, content):
    path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")
    assert settings.UserSettings(path).browser() == "default"


def test_failed_atomic_save_keeps_existing_preferences(tmp_path, monkeypatch):
    path = tmp_path / "settings.json"
    store = settings.UserSettings(path)
    store.save_browser("edge")
    before = path.read_bytes()
    monkeypatch.setattr(settings.os, "replace", Mock(side_effect=PermissionError("denied")))
    with pytest.raises(OSError):
        store.save_browser("chrome")
    assert path.read_bytes() == before
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError):
        store.save_browser("not-a-browser")


def test_windows_settings_belong_to_current_user(tmp_path, monkeypatch):
    if settings.os.name != "nt":
        pytest.skip("Windows profile path")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert settings.settings_path() == tmp_path / "LoungProspect" / "settings.json"


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


def test_browser_missing_is_offered_from_ui_thread_and_choice_is_snapshotted(monkeypatch):
    from ui import browser_action as module
    threads = []
    monkeypatch.setattr(module.threading, "Thread", lambda **kw: threads.append(kw) or Mock())
    launch = Mock(side_effect=launcher.BrowserNotFoundError())
    monkeypatch.setattr(module, "open_browser", launch)
    choice = {"browser": "edge"}
    owner, done, unavailable = Mock(), Mock(), Mock()
    action = BrowserAction(owner, done, browser=lambda: choice["browser"], unavailable=unavailable)
    action.open("https://wa.me/example")
    choice["browser"] = "chrome"
    owner.reset_mock()
    threads[0]["target"]()
    assert not owner.mock_calls
    unavailable.assert_not_called()
    launch.assert_called_once_with("https://wa.me/example", "edge")
    action.poll()
    unavailable.assert_called_once_with()
    done.assert_not_called()


@pytest.mark.parametrize("accept", [True, False])
def test_fallback_is_explicit_and_does_not_change_preference(monkeypatch, accept):
    monkeypatch.setattr("ui.sales_workspace.messagebox.askyesno", Mock(return_value=accept))
    page = SimpleNamespace(update_availability=Mock(), winfo_toplevel=Mock(),
        browser_action=Mock(requested_browser="edge", open=Mock(return_value=True)),
        current_url=Mock(return_value="https://wa.me/current-message"), notice=Mock(), settings=Mock())
    ContactPanel.browser_unavailable(page)
    if accept:
        page.browser_action.open.assert_called_once_with("https://wa.me/current-message", browser="default")
    else:
        page.browser_action.open.assert_not_called()
        assert "Escolha outro navegador" in page.notice.configure.call_args.kwargs["text"]
    assert not page.settings.mock_calls


def test_save_failure_keeps_session_preference_and_explains(monkeypatch):
    page = SimpleNamespace(browser_preference="default", settings=Mock(save_browser=Mock(side_effect=OSError())),
                           preference_notice=Mock())
    SalesWorkspacePage.choose_browser(page, "Google Chrome")
    assert page.browser_preference == "chrome"
    assert "nesta sessão" in page.preference_notice.configure.call_args.kwargs["text"]
