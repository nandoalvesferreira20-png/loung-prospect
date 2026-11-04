from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import scraper
from core.qualification.models import QualificationResult


def test_empty_qualification_aggregates(harness):
    harness.links.return_value = []
    summary = harness.run(qualification_enabled=True)
    assert summary["qualification_summary"] == dict(qualified=0, insufficient_data=0, error=0, website_opportunities=0)
