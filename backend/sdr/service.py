"""Reuse SalesAgent.generate with read-only leads and an ephemeral draft sink.

The desktop constructor migrates and its sink persists automatically. Neither is
appropriate for web generation, so only those I/O adapters are replaced here.
"""
from copy import deepcopy
from threading import Lock, RLock
from time import monotonic
from uuid import uuid4
from fastapi import HTTPException
from core.sales.agent import SalesAgent
from core.sales.config import create_groq_provider
from core.sales.contact import normalize_phone, blocked
from core.sales.prompts import build_evidence
from .policy import routing, SERVICES, WEB_POLICY
from .storage import SdrStore


def configured_provider():
    provider = create_groq_provider()
    provider.timeout = min(provider.timeout, 30)
    return provider


class PolicyProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.provider_name = getattr(delegate, "provider_name", "groq")
        self.model = getattr(delegate, "model", None)

    def generate(self, *, system_prompt, evidence):
        return self.delegate.generate(system_prompt=system_prompt + WEB_POLICY, evidence=evidence)


class DraftSink:
    def __init__(self, history):
        self.rows = [{"mensagem": r["message"], "status": r["status"]} for r in history]
        self.result = None

    def history(self, _lead_id):
        return self.rows

    def create(self, _lead_id, result, **_metadata):
        self.result = result
        return 1


class WebAgent(SalesAgent):
    def __init__(self, store, provider, request, history):
        self.store, self.request = store, request
        self.leads = self  # get_lead is read-only; never call desktop constructor
        self.provider = PolicyProvider(provider)
        self.outreach = DraftSink(history)

    def get_lead(self, lead_id):
        return self.store.lead(lead_id)[0]

    def evidence(self, lead_id):
        lead, saved = self.store.lead(lead_id)
        role, source = routing(lead.get("segmento"), self.request.recipient, saved)
        # Bound legacy data too; notes/phone/email never enter the model prompt.
        evidence = {key: value[:1500] if isinstance(value, str) else value
                    for key, value in build_evidence(lead).items()}
        self.last_evidence = {**evidence, "tipo_contato": role, "tipo_contato_origem": source,
                              "servico": SERVICES[self.request.service],
                              "instrucao_adicional": self.request.instruction.strip()}
        return self.last_evidence


class SdrService:
    def __init__(self, selection_store, provider_factory=configured_provider):
        self.store = SdrStore(selection_store)
        self.provider_factory = provider_factory
        self.generation_lock = Lock()
        self.cache_lock = RLock()
        self.requests, self.drafts = {}, {}
        self.ttl = 900

    def reap(self):
        with self.cache_lock:
            now = monotonic()
            for cache in (self.requests, self.drafts):
                for key in list(cache):
                    if now - cache[key]["time"] >= self.ttl:
                        del cache[key]

    def context(self, lead_id):
        row, saved = self.store.lead(lead_id)
        role, source = routing(row.get("segmento"), saved=saved)
        phone, reason = None, None
        if blocked(row):
            reason = "Contato bloqueado: lead marcado como Não contatar ou com recusa/revogação registrada."
        else:
            try:
                phone = normalize_phone((row.get("whatsapp") or "").strip() or row.get("telefone"))
            except ValueError as error:
                reason = str(error)
        return {"leadId": lead_id, "company": row["empresa"], "niche": row.get("segmento"),
                "phone": row.get("whatsapp") or row.get("telefone"), "website": row.get("site"),
                "stage": row.get("status"), "contactType": role, "contactSource": source,
                "normalizedPhone": phone, "whatsappReason": reason, "blocked": blocked(row)}

    def generate(self, request):
        self.reap()
        key = str(request.requestId)
        fingerprint = request.model_dump_json()
        if not self.generation_lock.acquire(blocking=False):
            raise HTTPException(429, "Já existe uma geração em andamento. Aguarde antes de tentar novamente.")
        try:
            with self.cache_lock:
                previous = self.requests.get(key)
                if previous:
                    if previous["fingerprint"] != fingerprint:
                        raise HTTPException(409, "Identificador já utilizado para outra solicitação.")
                    if "response" in previous:
                        return deepcopy(previous["response"])
                    raise HTTPException(previous["status"], previous["detail"])
                # Never evict active drafts early: capacity applies backpressure.
                if len(self.requests) >= 100:
                    raise HTTPException(429, "Limite local de gerações atingido. Aguarde alguns minutos.")
                self.requests[key] = {"time": monotonic(), "fingerprint": fingerprint,
                                      "status": 502, "detail": "A geração falhou. Inicie uma nova tentativa."}
            try:
                context = self.context(request.leadId)
                if context["blocked"]:
                    raise HTTPException(409, context["whatsappReason"])
                history = self.store.history(request.leadId)["items"]
                if request.previousDraftId:
                    previous_draft = self.draft(str(request.previousDraftId))
                    if previous_draft["leadId"] != request.leadId:
                        raise HTTPException(409, "O rascunho anterior pertence a outro lead.")
                    history = [{"message": previous_draft["message"], "status": "GERADA"}, *history]
                provider = self.provider_factory()
                agent = WebAgent(self.store, provider, request, history)
                agent.generate(request.leadId, regeneration_reason="Crie uma abertura diferente, mantendo os fatos e a solução selecionada." if request.previousDraftId else None)
                result = agent.outreach.result
                if self.context(request.leadId)["blocked"]:
                    raise HTTPException(409, "Lead bloqueado durante a geração. O rascunho foi descartado.")
                evidence = agent.last_evidence
                response = {"draftId": str(uuid4()), "leadId": request.leadId, "message": result.mensagem,
                            "angle": result.angulo, "contactType": evidence["tipo_contato"],
                            "contactSource": evidence["tipo_contato_origem"], "state": "generated",
                            "provider": agent.provider.provider_name, "model": agent.provider.model}
                with self.cache_lock:
                    self.drafts[response["draftId"]] = {**response, "confidence": result.confianca, "time": monotonic()}
                    self.requests[key]["response"] = response
                return deepcopy(response)
            except HTTPException as error:
                with self.cache_lock:
                    self.requests[key].update(status=error.status_code, detail=error.detail)
                raise
            except Exception:
                # SDK errors may contain request/credentials. Never echo or log them.
                detail = "Não foi possível gerar uma abordagem válida. Confira a configuração Groq existente, conexão e limites; tente novamente."
                with self.cache_lock:
                    self.requests[key].update(status=502, detail=detail)
                raise HTTPException(502, detail) from None
        finally:
            self.generation_lock.release()

    def draft(self, key):
        self.reap()
        with self.cache_lock:
            draft = self.drafts.get(key)
            if draft is None:
                raise HTTPException(410, "Rascunho expirado ou API reiniciada. Copie o texto e gere uma nova versão para salvar.")
            return draft

    def save(self, request):
        # Serialize saves with expiry to keep savedId and retry idempotency intact.
        with self.cache_lock:
            draft = self.draft(str(request.draftId))
            saved_id = self.store.save(draft, request.message, request.status)
            return {"id": saved_id, "leadId": draft["leadId"], "status": request.status}
