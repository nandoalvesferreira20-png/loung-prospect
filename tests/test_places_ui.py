"""Headless UI lifecycle checks: no Tk root, thread, browser or API."""

import queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.prospecting.service import ProspectingSummary
from core.providers.google_places import GooglePlacesConfigurationError


def test_environment_loader_is_shared_and_does_not_override(
    tmp_path,
    monkeypatch,
):
    import sys

    from core.providers import environment
    from scripts import test_google_places_real

    (
        tmp_path / ".env"
    ).write_text(
        "GOOGLE_PLACES_API_KEY=",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        environment,
        "ROOT",
        tmp_path,
    )

    loader = Mock()

    monkeypatch.setitem(
        sys.modules,
        "dotenv",
        SimpleNamespace(
            load_dotenv=loader
        ),
    )

    environment.load_environment()

    loader.assert_called_once_with(
        dotenv_path=tmp_path / ".env",
        override=False,
        interpolate=False,
    )

    assert (
        test_google_places_real.load_environment
        is environment.load_environment
    )
