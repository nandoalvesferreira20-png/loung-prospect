"""Presentation contracts, independent of providers and databases."""
from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from ui.sdr_formatting import draft_label, local_date, confidence_badge, feedback_tone
from ui.sdr_components import Stepper, StatusBar
from ui.theme import COLORS, SPACING


def test_draft_label_converts_utc_without_mutating_row():
    row = dict(id=6, criado_em="2026-10-15T22:05:22+00:00", status="GERADA")
    original = row.copy()
    assert draft_label(row) == "#6 · 15/10 às 19:05 · Gerada"
    assert row == original


def test_local_date_handles_day_rollover_and_historic_dst():
    assert local_date("2026-10-15T01:00:00Z") == "14/10/2026 às 22:00"
    assert local_date("2018-12-01T12:00:00Z") == "01/12/2018 às 10:00"


@pytest.mark.parametrize("value,expected", [(None,"Data indisponível"), ("invalid","Data indisponível"),
                                          ("2026-10-15T12:00:00","Data sem fuso")])
def test_invalid_date_never_exposes_raw_value(value, expected):
    assert local_date(value) == expected


@pytest.mark.parametrize("value,text,tone", [(.49,"49%","danger"),(.5,"50%","warning"),
    (.7,"70%","warning"),(.75,"75%","warning"),(.76,"76%","success"), (1,"100%","success")])
def test_confidence_is_only_display_formatting(value, text, tone):
    label, actual = confidence_badge(value)
    assert text in label and actual == tone


@pytest.mark.parametrize("value", [None, float("nan"), 4])
def test_unknown_confidence(value):
    assert confidence_badge(value) == ("Confiança não informada", "neutral")


def test_stepper_only_changes_visual_configuration():
    steps = [Mock(), Mock(), Mock()]
    Stepper.set(SimpleNamespace(steps=steps), 1)
    assert steps[1].configure.call_args.kwargs["fg_color"] == COLORS["selected"]
    assert steps[0].configure.call_args.kwargs["fg_color"] == "transparent"


def test_feedback_semantics():
    assert feedback_tone("Rascunho salvo.") == "success"
    assert feedback_tone("Não foi possível salvar.") == "danger"
    assert feedback_tone("Gerando rascunho…") == "info"


def test_tokens_have_requested_aliases():
    assert {"bg_base", "bg_surface", "bg_elevated", "border", "text_primary", "text_secondary",
            "text_muted", "accent", "success", "warning", "danger", "info"} <= COLORS.keys()
    assert {4, 8, 12, 16, 24, 32} <= set(SPACING.values())


@pytest.mark.parametrize("foreground,background", [("text_primary","bg_base"),
    ("text_secondary","bg_surface"),("text_muted","bg_elevated"),
    ("text_primary","primary"),("draft","draft_surface"),
    ("success","bg_elevated"),("warning","bg_elevated"),("danger","bg_elevated")])
def test_normal_text_palette_meets_aa(foreground, background):
    def luminance(color):
        channels = [int(color[i:i+2],16)/255 for i in (1,3,5)]
        linear = [c/12.92 if c <= .04045 else ((c+.055)/1.055)**2.4 for c in channels]
        return sum(c*w for c,w in zip(linear,(.2126,.7152,.0722)))
    light,dark = sorted((luminance(COLORS[foreground]),luminance(COLORS[background])),reverse=True)
    assert (light+.05)/(dark+.05) >= 4.5


def test_statusbar_cancels_expiry_before_destroy(monkeypatch):
    monkeypatch.setattr("customtkinter.CTkLabel.destroy", Mock())
    # Invoke with a real class instance without creating Tcl widgets.
    bar = object.__new__(StatusBar)
    bar.expiry = "pending"
    bar.after_cancel = Mock()
    StatusBar.destroy(bar)
    bar.after_cancel.assert_called_once_with("pending")
