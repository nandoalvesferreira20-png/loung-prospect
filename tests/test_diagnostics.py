import json
from unittest.mock import Mock

from core.diagnostics import diagnostic_logging, trace


def test_trace_is_opt_in_and_context_resets():
    log = Mock()
    with diagnostic_logging(log):
        trace("TEST", site="https://example.test")
    trace("OFF")
    log.assert_called_once()
    assert json.loads(log.call_args.args[0].split("] ", 1)[1])["site"] == "https://example.test"


def test_broken_callback_does_not_interrupt():
    with diagnostic_logging(Mock(side_effect=RuntimeError("log unavailable"))):
        trace("TEST", value=1)


def test_scraper_trace_carries_metadata_and_actual_stages(harness, monkeypatch):
    monkeypatch.setenv("LOUNG_WEBSITE_DEBUG", "1")
    log = Mock()
    summary = harness.run(qualification_enabled=True, log=log)
    messages = [call.args[0] for call in log.call_args_list]
    for stage in ("SCRAPER_EXTRACT", "EXTRACTED", "PRE_QUALIFY", "ADAPTER", "DIGITAL_PRESENCE", "RULES"):
        assert any(message.startswith(f"[DIAG {stage}]") for message in messages)
    assert summary["leads"] == 1
