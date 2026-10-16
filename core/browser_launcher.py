"""Locate installed browsers and launch a URL with argument lists, never a shell."""
import os
from pathlib import Path
import shutil
import subprocess
import webbrowser

BROWSERS = {"edge": ("msedge.exe", Path("Microsoft") / "Edge" / "Application"),
            "chrome": ("chrome.exe", Path("Google") / "Chrome" / "Application")}


class BrowserNotFoundError(RuntimeError):
    pass


def registry_paths(executable):
    if os.name != "nt":
        return
    import winreg
    key = rf"Software\Microsoft\Windows\CurrentVersion\App Paths\{executable}"
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, key, 0, winreg.KEY_READ | view) as handle:
                    value, _ = winreg.QueryValueEx(handle, "")
                    if isinstance(value, str):
                        yield Path(os.path.expandvars(value.strip().strip('"')))
            except OSError:
                continue


def find_browser(browser, *, environ=None):
    executable, relative = BROWSERS[browser]
    candidates = list(registry_paths(executable))
    on_path = shutil.which(executable)
    if on_path:
        candidates.append(Path(on_path))
    env = os.environ if environ is None else environ
    for variable in ("LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432"):
        if env.get(variable):
            candidates.append(Path(env[variable]) / relative / executable)
    return next((path for path in candidates if path.name.casefold() == executable and path.is_file()), None)


def open_browser(url, browser="default"):
    if browser == "default":
        return bool(webbrowser.open(url, new=2))
    if browser not in BROWSERS:
        raise ValueError("Navegador inválido.")
    executable = find_browser(browser)
    if executable is None:
        raise BrowserNotFoundError(browser)
    # Keep the complete encoded URL as one argument; no command concatenation.
    try:
        subprocess.Popen([str(executable), url], shell=False, close_fds=True)
    except FileNotFoundError:
        raise BrowserNotFoundError(browser) from None
    return True
