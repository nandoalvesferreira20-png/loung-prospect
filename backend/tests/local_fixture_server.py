"""Synthetic loopback browser fixture; never reads real env/database/providers."""
from pathlib import Path
from uuid import uuid4
from backend.config import Settings
from backend.main import create_app
from backend.tests.test_sdr_api import Provider
from core.providers.google_places import GooglePlacesProvider
import json
import os


def factory():
    os.environ['GOOGLE_PLACES_API_KEY'] = 'synthetic-browser-key'
    path = Path(__file__).resolve().parents[2] / 'temp' / ('local-browser-' + uuid4().hex) / 'synthetic.db'
    def transport(*_):
        return 200, json.dumps({'places':[{'id':'synthetic-browser-place', 'displayName':{'text':'Synthetic Places Company'},
            'formattedAddress':'Synthetic address', 'nationalPhoneNumber':'(11) 99999-0000'}]}).encode()
    return create_app(Settings(path, True, mode='local', initialize_local=True),
                      provider_factory=lambda:GooglePlacesProvider(transport=transport),
                      sdr_provider_factory=Provider)
