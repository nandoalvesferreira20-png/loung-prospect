"""Provider-neutral orchestration; no networking or sending implemented here."""
from copy import deepcopy

from core.database.lead_repository import LeadRepository, LeadNotFoundError
from core.database.outreach_repository import OutreachRepository
from .models import SalesGeneration, OutreachStatus
from .prompts import SYSTEM_PROMPT, build_evidence
from .errors import SalesProviderError, GroqProviderError
from .contact import blocked
from .contact_routing import contact_context
from core.database.contact_preference_repository import ContactPreferenceRepository


class SalesGenerationError(RuntimeError):
    def __init__(self, message, *, provider_error=None):
        super().__init__(message)
        self.provider_error = provider_error


class SalesAgent:
    def __init__(self, repository: LeadRepository, provider):
        self.leads = repository
        self.outreach = OutreachRepository(repository.path)
        self.provider = provider

    def evidence(self, lead_id):
        lead = self.leads.get_lead(lead_id)
        if lead is None:
            raise LeadNotFoundError("Lead não encontrado.")
        return {**build_evidence(lead), **contact_context(lead["segmento"],
            ContactPreferenceRepository(self.leads.path).get(lead_id))}

    def generate(self, lead_id, *, evidence=None, reuse_existing=False, regeneration_reason=None):
        current = self.evidence(lead_id)  # also checks deleted leads before API
        if blocked(self.leads.get_lead(lead_id)):
            raise SalesGenerationError("Lead marcado como Não contatar. Geração de novas abordagens bloqueada.")
        history = self.outreach.history(lead_id)
        if reuse_existing and regeneration_reason is None:
            saved = next((row for row in history if row["status"] != "CANCELADA"), None)
            if saved is not None:
                return saved["id"]
        context = current if evidence is None else deepcopy(evidence)
        # Routing must use the latest manual choice even with a frozen prior draft snapshot.
        for key in ("tipo_contato", "tipo_contato_origem"):
            context[key] = current[key]
        if "segmento" in current:
            context["segmento"] = current["segmento"]
        else:
            context.pop("segmento", None)
        if regeneration_reason is not None:
            if not isinstance(regeneration_reason, str) or len(regeneration_reason) > 500:
                raise SalesGenerationError("Motivo da regeneração deve ter até 500 caracteres.")
            context["revisao_solicitada"] = {"motivo": regeneration_reason,
                "textos_anteriores": [row["mensagem"] for row in history[:5]]}
        try:
            response = self.provider.generate(system_prompt=SYSTEM_PROMPT, evidence=deepcopy(context))
            result = SalesGeneration.from_mapping(response)
            if regeneration_reason is not None and any(
                    result.mensagem.strip().casefold() == row["mensagem"].strip().casefold() for row in history):
                raise SalesProviderError("A IA repetiu uma versão anterior. Nenhuma nova versão foi salva; tente outro motivo.")
        except GroqProviderError as error:
            raise SalesGenerationError(str(error), provider_error=error) from None
        except SalesProviderError as error:
            raise SalesGenerationError(str(error)) from None
        except Exception:
            # Provider payloads/errors can contain credentials; never surface them.
            raise SalesGenerationError("Não foi possível gerar uma resposta válida. Confira a configuração e tente novamente.") from None
        provider = getattr(self.provider, "provider_name", None)
        model = getattr(self.provider, "model", None)
        return self.outreach.create(lead_id, result,
            provider=provider if isinstance(provider, str) else None,
            model=model if isinstance(model, str) else None)

    def edit(self, lead_id, draft_id, message):
        self.outreach.update(lead_id, draft_id, status=OutreachStatus.EDITED, message=message)

    def approve(self, lead_id, draft_id, message):
        self.outreach.update(lead_id, draft_id, status=OutreachStatus.APPROVED, message=message)

    def cancel(self, lead_id, draft_id):
        self.outreach.update(lead_id, draft_id, status=OutreachStatus.CANCELLED)
