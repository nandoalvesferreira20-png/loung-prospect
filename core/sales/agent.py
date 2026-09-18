"""Provider-neutral orchestration; no networking or sending implemented here."""
from copy import deepcopy

from core.database.lead_repository import LeadRepository, LeadNotFoundError
from core.database.outreach_repository import OutreachRepository
from .models import SalesGeneration, OutreachStatus
from .prompts import SYSTEM_PROMPT, build_evidence
from .errors import SalesProviderError


class SalesGenerationError(RuntimeError):
    pass


class SalesAgent:
    def __init__(self, repository: LeadRepository, provider):
        self.leads = repository
        self.outreach = OutreachRepository(repository.path)
        self.provider = provider

    def evidence(self, lead_id):
        lead = self.leads.get_lead(lead_id)
        if lead is None:
            raise LeadNotFoundError("Lead não encontrado.")
        return build_evidence(lead)

    def generate(self, lead_id, *, evidence=None):
        current = self.evidence(lead_id)  # also checks deleted leads before API
        context = current if evidence is None else deepcopy(evidence)
        try:
            response = self.provider.generate(system_prompt=SYSTEM_PROMPT, evidence=deepcopy(context))
            result = SalesGeneration.from_mapping(response)
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
