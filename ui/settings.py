"""Small per-user preferences, independent from project secrets and lead data."""
import json
import os
from pathlib import Path
import tempfile

BROWSER_CHOICES = {
    "Navegador padrão do sistema": "default",
    "Microsoft Edge": "edge",
    "Google Chrome": "chrome",
}


def settings_path():
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Local"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "LoungProspect" / "settings.json"


class UserSettings:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else settings_path()

    def read(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError, UnicodeError):
            return {}

    def browser(self):
        selected = self.read().get("whatsapp_browser", "default")
        return selected if selected in BROWSER_CHOICES.values() else "default"

    def save_browser(self, selected):
        if selected not in BROWSER_CHOICES.values():
            raise ValueError("Navegador inválido.")
        data = self.read()
        data["whatsapp_browser"] = selected
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent,
                                              prefix="settings-", suffix=".tmp", delete=False) as file:
                temporary = Path(file.name)
                json.dump(data, file, ensure_ascii=False, indent=2)
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
