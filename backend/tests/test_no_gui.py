"""The local API must start even when Python GUI packages cannot be imported."""
import os
from pathlib import Path
import subprocess
import sys


def test_local_api_starts_with_gui_imports_blocked(tmp_path):
    code = '''
import importlib.abc
import sys
from pathlib import Path
class NoGui(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'tkinter', 'customtkinter', 'ui', 'app'}:
            raise AssertionError('GUI import attempted: ' + fullname)
sys.meta_path.insert(0, NoGui())
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
settings = Settings(Path(sys.argv[1]), True, mode='local', initialize_local=True)
for _ in range(2):
    with TestClient(create_app(settings)) as client:
        assert client.get('/health').status_code == 200
        assert client.get('/v1/leads').json()['total'] == 0
assert not any(name.split('.')[0] in {'tkinter', 'customtkinter', 'ui', 'app'} for name in sys.modules)
'''
    env = {k: v for k, v in os.environ.items() if k not in (
        'VERCEL', 'RENDER', 'RAILWAY_ENVIRONMENT', 'WEBSITE_INSTANCE_ID',
        'K_SERVICE', 'FLY_APP_NAME', 'AWS_EXECUTION_ENV', 'PYTHONPATH')}
    result = subprocess.run([sys.executable, '-c', code, str(tmp_path / 'synthetic.db')],
                            cwd=Path(__file__).resolve().parents[2], env=env,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
