"""Offline deterministic text and headless UI callbacks."""
from copy import deepcopy
from itertools import product
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.outreach import OutreachContext, OutreachRequest, OutreachResult, TemplateOutreachGenerator, context_from_lead
from core.outreach.builder import sender_name
from core.outreach.models import CHANNELS, OBJECTIVES, TONES
from core.outreach.templates import normalize_segment, segment_display


@pytest.mark.parametrize("segment", ["dentista", "estetica", "veterinario", "advogado", "restaurante", "desconhecido"])
def test_all_template_combinations(segment):
    context = OutreachContext(company_name="São José & Filhos", segment=segment, city="Taubaté",
                              website="https://example.test", opportunity="website", rating="5.0", review_count=999)
    engine = TemplateOutreachGenerator()
    for channel, objective, tone in product(CHANNELS, OBJECTIVES, TONES):
        results = [engine.generate(OutreachRequest(context, channel, objective, tone, i)) for i in range(3)]
        assert len({r.message for r in results}) == 3
        assert len({r.template_id for r in results}) == 3
        for i, result in enumerate(results):
            assert result == engine.generate(OutreachRequest(context, channel, objective, tone, i))
            if objective == "first_contact" or channel == "phone":
                assert "São José & Filhos" in result.message
            assert "Fernando, da Loung Tech" in result.message
            assert not result.warnings
            assert result.channel == channel and result.objective == objective and result.tone == tone
            assert "v1" in result.template_id
            for forbidden in ("site está ruim", "perdendo clientes", "Instagram", "precisam de", "não têm site", "analisei", "dei uma olhada", "conversamos", "999", "https://", "5.0"):
                assert forbidden not in result.message
            if channel == "phone":
                assert "Abertura:" in result.message and "Se não houver interesse:" in result.message
            else:
                assert len(result.message) <= (450 if channel == "whatsapp" else 350)
            assert "Taubaté" not in result.message
            for artificial in ("considerando", "com a equipe de", "Seria um bom momento para conversar?", "Podemos falar sobre"):
                assert artificial not in result.message


def test_full_context_and_nonmutation():
    row = dict(empresa="Clínica", segmento="dentista", cidade="Santos", site="example.test", telefone="123",
               whatsapp="456", avaliacao="4", quantidade_avaliacoes=10, qualification_score=80,
               priority="high", opportunity="website", responsavel="Ana", status="Novo", extra=[1])
    original = deepcopy(row)
    context = context_from_lead(row)
    assert context == OutreachContext("Clínica", "dentista", "Santos", "example.test", "123", "456", "4", 10, 80, "high", "website", "Ana")
    result = TemplateOutreachGenerator().generate(OutreachRequest(context))
    assert "Sou Ana" in result.message
    assert row == original


def test_minimal_context_and_missing_fields():
    context = context_from_lead({})
    assert context == OutreachContext()
    result = TemplateOutreachGenerator().generate(OutreachRequest(context))
    assert "None" not in result.message and "Fernando" in result.message
    assert "negócio" in result.message and result.warnings


@pytest.mark.parametrize("value,expected", [(" Estética ", "estetica"), ("VETERINÁRIO", "veterinario"), ("advocacia", "advogado"), (None, "generic"), ("restaurante", "restaurante")])
def test_segment_normalization(value, expected):
    assert normalize_segment(value) == expected
    assert segment_display(value)


@pytest.mark.parametrize("value", [None, "", "  ", "Não atribuído", "123", "—"])
def test_configurable_sender(value):
    assert sender_name(value, "Marina") == "Marina"


@pytest.mark.parametrize("kwargs", [{"channel": "email"}, {"objective": "sell"}, {"tone": "urgent"}, {"variation": -1}, {"variation": 3}, {"variation": True}])
def test_invalid_request(kwargs):
    with pytest.raises(ValueError):
        OutreachRequest(OutreachContext(), **kwargs)


def test_score_validation_and_warnings_not_shared():
    with pytest.raises(ValueError):
        OutreachContext(qualification_score=101)
    warnings = ["Revisar"]
    result = OutreachResult("texto", "phone", "first_contact", "direct", "id", warnings)
    warnings.append("Outra")
    assert result.warnings == ("Revisar",)


def test_long_input_warns_without_truncation():
    name = "Á" * 600
    result = TemplateOutreachGenerator().generate(OutreachRequest(OutreachContext(company_name=name)))
    assert name in result.message and any("caracteres" in warning for warning in result.warnings)


@pytest.mark.parametrize('channel', CHANNELS)
def test_restaurant_name_regression(channel):
    name = 'Restaurante da Fazenda São Bernardo do Campo'
    context = OutreachContext(company_name=name, city='São Bernardo do Campo', segment='restaurante')
    engine = TemplateOutreachGenerator()
    for tone, variation in product(TONES, range(3)):
        result = engine.generate(OutreachRequest(context, channel=channel, tone=tone, variation=variation))
        assert name in result.message
        assert result.message.count('São Bernardo do Campo') == 1
        assert 'Fernando' in result.message and 'Loung Tech' in result.message
        for forbidden in ('em são bernardo', 'considerando', 'com a equipe de restaurante', 'seria um bom momento para conversar?'):
            assert forbidden not in result.message.lower()
        if channel == 'whatsapp':
            assert 180 <= len(result.message) <= 380
        if channel == 'instagram':
            whatsapp = engine.generate(OutreachRequest(context, tone=tone, variation=variation))
            assert len(result.message) < len(whatsapp.message)


@pytest.mark.parametrize('segment', ['dentista', 'estetica', 'veterinario', 'advogado', 'restaurante', 'outro'])
def test_city_not_verbalized_and_no_brand_article_guessing(segment):
    engine = TemplateOutreachGenerator()
    first = OutreachContext(company_name='XYZ & Filhos', segment=segment, city='Taubaté')
    second = OutreachContext(company_name='XYZ & Filhos', segment=segment, city='Santos')
    for channel, tone, variation in product(CHANNELS, TONES, range(3)):
        result = engine.generate(OutreachRequest(first, channel=channel, tone=tone, variation=variation))
        assert result == engine.generate(OutreachRequest(second, channel=channel, tone=tone, variation=variation))
        assert 'a XYZ' not in result.message and 'o XYZ' not in result.message


@pytest.mark.parametrize('objective', ['follow_up', 'reactivation'])
def test_continuations_do_not_reintroduce_the_company(objective):
    context = OutreachContext(company_name='Restaurante Teste', segment='restaurante', city='Santos')
    for variation in range(3):
        result = TemplateOutreachGenerator().generate(OutreachRequest(context, objective=objective, variation=variation))
        assert 'Encontrei' not in result.message
        assert 'Santos' not in result.message
        assert 'Restaurante Teste' not in result.message
        assert 'mensagem anterior' in result.message or 'mensagem' in result.message or objective == 'reactivation'
