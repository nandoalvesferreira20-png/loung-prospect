"""Niche routing, per-lead overrides and real Groq SDK payloads, fully offline."""
from copy import deepcopy
import json
from types import SimpleNamespace
from unittest.mock import Mock

import groq
import httpx
import pytest

from core.database import LeadRepository, initialize_database
from core.database.contact_preference_repository import ContactPreferenceRepository
from core.sales.agent import SalesAgent
from core.sales.contact_routing import classify_contact, normalize_niche, CONTACT_GUIDANCE
from core.sales.groq_provider import GroqSalesProvider
from core.sales.prompts import SYSTEM_PROMPT
from ui.sales_panel import SalesPanel


@pytest.mark.parametrize("segment,expected", [
    ("Clínica odontológica", "recepcao_equipe"), (" CLÍNICA_ODONTOLÓGICA ", "recepcao_equipe"),
    ("Clínicas de odontologia", "recepcao_equipe"), ("Clínica dentária", "recepcao_equipe"),
    ("Clínicas médicas", "recepcao_equipe"), ("Policlínica", "recepcao_equipe"),
    ("Centro médico", "recepcao_equipe"), ("Clínica de estética", "recepcao_equipe"),
    ("Clínica veterinária", "recepcao_equipe"), ("Hospital veterinário", "recepcao_equipe"),
    ("Restaurantes", "recepcao_equipe"), ("Cafeteria", "recepcao_equipe"),
    ("Academia de musculação", "recepcao_equipe"), ("Box de CrossFit", "recepcao_equipe"),
    ("Boxes de Cross Fit", "recepcao_equipe"), ("Salão de beleza médio", "recepcao_equipe"),
    ("Grandes salões de beleza", "recepcao_equipe"),
    ("Corretor autônomo", "contato_direto"), ("Corretora de imóveis independente", "contato_direto"),
    ("AUTÔNOMO - CORRETOR DE IMÓVEIS", "contato_direto"), ("Advogada autônoma", "contato_direto"),
    ("Advogados independentes", "contato_direto"), ("Barbeiro", "contato_direto"),
    ("Barbearia pequena", "contato_direto"), ("Pequena barbearia", "contato_direto"),
    ("Esteticista autônoma", "contato_direto"), ("Profissional autônomo de estética", "contato_direto"),
    ("Personal trainer", "contato_direto"), ("Profissionais independentes", "contato_direto"),
    (None, "indefinido"), ("", "indefinido"), ("Nicho desconhecido", "indefinido"),
    ("Salão pequeno", "indefinido"), ("Salão de beleza", "indefinido"),
    ("Imobiliária com número geral", "indefinido"), ("Advocacia", "indefinido"),
    ("Barbearia", "indefinido"), ("Barbearia grande", "indefinido"),
    ("Clínica de estética / profissional autônomo", "indefinido"),
])
def test_normalized_niche_defaults_and_ambiguity(segment, expected):
    assert classify_contact(segment) == expected


def test_niche_normalization_and_no_company_name_inference(tmp_path):
    assert normalize_niche(" CLÍNICA--Odontológica ") == "clinica odontologica"
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead(dict(empresa="Clínica Autônoma de Nome Inventado", segmento="Desconhecido"))
    assert SalesAgent(repo, Mock()).evidence(lead)["tipo_contato"] == "indefinido"


def test_manual_override_persists_without_changing_lead_or_other_preferences(tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead(dict(empresa="A", segmento="Clínica odontológica", observacoes="Manter"))
    other = repo.create_lead(dict(empresa="B", segmento="Corretor autônomo"))
    before = [dict(row) for row in repo.list_leads()]
    store = ContactPreferenceRepository(repo.path)
    assert store.get(lead) is None
    store.save(lead, "contato_direto")
    store.save(other, "indefinido")
    initialize_database(repo.path)
    reopened = ContactPreferenceRepository(LeadRepository(repo.path).path)
    assert reopened.get(lead) == "contato_direto" and reopened.get(other) == "indefinido"
    assert [dict(row) for row in repo.list_leads()] == before
    with pytest.raises(ValueError):
        store.save(lead, "unknown")
    with pytest.raises(ValueError):
        store.save(999, "recepcao_equipe")
    assert store.get(lead) == "contato_direto"


@pytest.mark.parametrize("segment,kind,message", [
    ("Clínica odontológica", "recepcao_equipe", "Olá, sou Fernando, da Loung Tech. Quem cuida da apresentação digital? Poderiam me encaminhar à pessoa responsável?"),
    ("Corretor autônomo", "contato_direto", "Olá, sou Fernando, da Loung Tech. Posso compartilhar uma ideia para sua apresentação profissional como corretor?"),
    ("Nicho desconhecido", "indefinido", "Olá, sou Fernando, da Loung Tech. Com quem posso conversar sobre apresentação digital?")])
def test_existing_groq_sdk_receives_routing_and_returns_reviewable_draft(tmp_path, segment, kind, message):
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead(dict(empresa="Empresa sintética", segmento=segment))
    captured = []
    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={"id": "test", "object": "chat.completion", "created": 1, "model": "test-model",
            "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant",
                "content": json.dumps(dict(mensagem=message, angulo="apresentação", confianca=.8))}}]})
    provider = GroqSalesProvider(key="synthetic-key", model="test-model", client_factory=lambda **kwargs:
        groq.Groq(**kwargs, http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    agent = SalesAgent(repo, provider)
    draft = agent.generate(lead)
    assert len(captured) == 1
    assert captured[0]["messages"][0]["content"] == SYSTEM_PROMPT
    assert CONTACT_GUIDANCE in SYSTEM_PROMPT
    evidence = json.loads(captured[0]["messages"][1]["content"])
    assert evidence == dict(empresa="Empresa sintética", segmento=segment, tipo_contato=kind, tipo_contato_origem="sugestao_nicho")
    saved = agent.outreach.history(lead)[0]
    assert saved["id"] == draft and saved["mensagem"] == message and saved["status"] == "GERADA"
    assert saved["enviado_em"] is None
    agent.edit(lead, draft, "Edição humana antes de abrir o WhatsApp")
    assert agent.outreach.history(lead)[0]["mensagem"] == "Edição humana antes de abrir o WhatsApp"


def test_new_manual_choice_overrides_frozen_snapshot_on_next_generation(tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead(dict(empresa="Clínica", segmento="Clínica odontológica"))
    provider = Mock(generate=Mock(return_value=dict(mensagem="Quem cuida da apresentação digital? Poderiam encaminhar?", angulo="apresentação", confianca=.8)))
    agent = SalesAgent(repo, provider)
    snapshot = agent.evidence(lead)
    original = deepcopy(snapshot)
    first = agent.generate(lead, evidence=snapshot)
    ContactPreferenceRepository(repo.path).save(lead, "contato_direto")
    provider.generate.return_value = dict(mensagem="Posso compartilhar uma ideia para sua apresentação profissional?", angulo="apresentação", confianca=.8)
    second = agent.generate(lead, evidence=snapshot, regeneration_reason="Ajustar interlocutor")
    evidence = provider.generate.call_args.kwargs["evidence"]
    assert evidence["tipo_contato"] == "contato_direto" and evidence["tipo_contato_origem"] == "ajuste_manual"
    assert snapshot == original
    assert first != second and len(agent.outreach.history(lead)) == 2
    assert agent.outreach.history(lead)[1]["mensagem"].startswith("Quem cuida")


def test_incomplete_data_contains_no_invented_facts(tmp_path):
    repo = LeadRepository(tmp_path / "test.db")
    lead = repo.create_lead(dict(empresa="Empresa sintética", observacoes="Não enviar notas privadas"))
    provider = Mock(generate=Mock(return_value=dict(mensagem="Olá, sou Fernando, da Loung Tech. Quem é responsável pela apresentação digital?", angulo="conversa neutra", confianca=.5)))
    agent = SalesAgent(repo, provider)
    agent.generate(lead)
    assert provider.generate.call_args.kwargs["evidence"] == dict(empresa="Empresa sintética", tipo_contato="indefinido", tipo_contato_origem="sugestao_nicho")
    assert "Não invente" in SYSTEM_PROMPT and "não afirme estrutura ou porte" in SYSTEM_PROMPT
    assert "Site vazio NÃO prova ausência" in SYSTEM_PROMPT


def test_ui_override_saves_without_generating_or_replacing_current_text():
    page = SimpleNamespace(contact_type="recepcao_equipe", contact_preferences=Mock(), lead_id=1,
        snapshot={"old": "snapshot"}, contact_type_label=Mock(), feedback=Mock(), message=Mock(), generate=Mock())
    SalesPanel.change_contact_type(page, "Indefinido")
    page.contact_preferences.save.assert_called_once_with(1, "indefinido")
    assert page.snapshot is None and page.contact_type == "indefinido"
    page.message.delete.assert_not_called()
    page.generate.assert_not_called()


def test_ui_failed_override_keeps_previous_choice():
    page = SimpleNamespace(contact_type="recepcao_equipe", contact_preferences=Mock(save=Mock(side_effect=OSError())),
        lead_id=1, contact_type_selector=Mock(), feedback=Mock(), message=Mock(), snapshot={"keep": True})
    SalesPanel.change_contact_type(page, "Contato direto")
    page.contact_type_selector.set.assert_called_once_with("Recepção/equipe")
    assert page.snapshot == {"keep": True} and page.contact_type == "recepcao_equipe"
