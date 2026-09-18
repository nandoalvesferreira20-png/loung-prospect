"""OpenAI Responses adapter using stdlib; injectable transport for offline tests."""
import http.client
import json
import os
import logging

from core.providers.environment import load_environment
from .errors import SalesConfigurationError

SCHEMA = {"type": "object", "properties": {
    "mensagem": {"type": "string"}, "angulo": {"type": "string"}, "confianca": {"type": "number"}},
    "required": ["mensagem", "angulo", "confianca"], "additionalProperties": False}


def _post(payload, key):
    connection = http.client.HTTPSConnection("api.openai.com", timeout=45)
    try:
        connection.request("POST", "/v1/responses", body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                           headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read(1_000_001)
    finally:
        connection.close()


class OpenAISalesProvider:
    provider_name = "openai"

    def __init__(self, *, key, model, transport=None):
        if not key.strip() or not model.strip():
            raise SalesConfigurationError("Configure AI_API_KEY e AI_MODEL no ambiente ou .env.")
        self._key, self.model = key.strip(), model.strip()
        self.transport = transport or _post

    def generate(self, *, system_prompt, evidence):
        payload = {"model": self.model, "store": False, "instructions": system_prompt,
            "input": [{"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
            "max_output_tokens": 1600,
            "text": {"format": {"type": "json_schema", "name": "sales_draft", "strict": True, "schema": SCHEMA}}}
        try:
            status, raw = self.transport(payload, self._key)
            if status != 200 or len(raw) > 1_000_000:
                raise ValueError
            data = json.loads(raw)
            if data.get("status") != "completed":
                raise ValueError
            texts = []
            for item in data.get("output", []):
                if item.get("type") != "message":
                    continue
                for content in item.get("content", []):
                    if content.get("type") == "refusal":
                        raise ValueError
                    if content.get("type") == "output_text":
                        texts.append(content["text"])
            return json.loads("".join(texts))
        except Exception:
            raise RuntimeError("A OpenAI não retornou uma resposta completa válida. Confira modelo, credencial e quota.") from None


def create_sales_provider():
    load_environment()
    name = os.environ.get("AI_PROVIDER", "openai").strip().lower()
    model = os.environ.get("AI_MODEL", "")
    if name == "openai":
        provider = OpenAISalesProvider(key=os.environ.get("AI_API_KEY", ""), model=model)
    elif name == "ollama":
        from .ollama import OllamaSalesProvider
        provider = OllamaSalesProvider(model=model,
            base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            timeout=os.environ.get("OLLAMA_TIMEOUT", "120"))
    else:
        raise SalesConfigurationError("AI_PROVIDER não suportado; utilize openai ou ollama.")
    # Never log credentials, the endpoint, prompts or evidence.
    logging.getLogger(__name__).info("SDR IA: provider=%s model=%s", name,
        provider.model if name == "ollama" else "configurado")
    return provider
