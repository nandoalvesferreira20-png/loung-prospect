"""Local Ollama chat adapter; one request, no retry or provider fallback."""
import http.client
import json
import math
import re
from urllib.parse import urlsplit

from .errors import SalesConfigurationError, SalesProviderError
from .models import SalesGeneration
from .provider import SCHEMA


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Chave JSON duplicada.")
        result[key] = value
    return result


def parse_ollama_output(content):
    """Accept one JSON object, optionally fenced or surrounded by prose.

    Taking the whole brace span rejects multiple objects and malformed outer
    objects instead of guessing which answer the model intended.
    """
    if not isinstance(content, str) or len(content) > 1_000_000:
        raise ValueError("Resposta JSON inválida.")
    text = content.strip()
    try:
        data = json.loads(text, object_pairs_hook=_unique_keys)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end < start or "[" in text[:start] or "]" in text[end + 1:]:
            raise ValueError("Resposta JSON inválida.") from None
        data = json.loads(text[start:end + 1], object_pairs_hook=_unique_keys)
    SalesGeneration.from_mapping(data)
    return data


def _post(base_url, payload, timeout):
    url = urlsplit(base_url)
    connection_type = http.client.HTTPSConnection if url.scheme == "https" else http.client.HTTPConnection
    connection = connection_type(url.hostname, port=url.port, timeout=timeout)
    try:
        connection.request("POST", "/api/chat",
            body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        return response.status, response.read(1_000_001)
    finally:
        connection.close()


class OllamaSalesProvider:
    provider_name = "ollama"

    def __init__(self, *, model, base_url="http://localhost:11434", timeout=120, transport=None):
        # Also keeps the model safe for log output and the suggested pull command.
        if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,199}", model.strip()):
            raise SalesConfigurationError("Configure AI_MODEL com o nome do modelo Ollama, por exemplo gemma3:4b.")
        try:
            url = urlsplit(base_url.strip())
            if (url.scheme not in ("http", "https") or not url.hostname or url.username is not None
                    or url.password is not None or url.query or url.fragment or url.path not in ("", "/")
                    or any(char.isspace() for char in base_url) or url.port == 0):
                raise ValueError
            timeout = float(timeout)
            if not math.isfinite(timeout) or not 0 < timeout <= 600:
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise SalesConfigurationError("Confira OLLAMA_BASE_URL (http://localhost:11434) e OLLAMA_TIMEOUT (1–600 segundos).") from None
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport or _post

    def generate(self, *, system_prompt, evidence):
        payload = {"model": self.model, "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
            "stream": False, "format": SCHEMA}
        try:
            status, raw = self.transport(self.base_url, payload, self.timeout)
            if len(raw) > 1_000_000:
                raise ValueError
            if status != 200:
                # Inspect the error only for classification; never surface body text.
                if status == 404:
                    error = json.loads(raw).get("error", "")
                    if isinstance(error, str) and "model" in error.lower() and "not found" in error.lower():
                        raise SalesProviderError(f'O modelo "{self.model}" não está disponível no Ollama. Execute: ollama pull {self.model}')
                raise SalesProviderError("O Ollama rejeitou a solicitação. Confira o serviço, o modelo e OLLAMA_BASE_URL.")
            data = json.loads(raw)
            if data.get("done") is not True or data.get("error") or data.get("done_reason") == "length":
                raise ValueError
            message = data["message"]
            if message.get("tool_calls"):
                raise ValueError
            return parse_ollama_output(message["content"])
        except SalesProviderError:
            raise
        except TimeoutError:
            raise SalesProviderError("O Ollama excedeu o tempo de espera. Confira o modelo e OLLAMA_TIMEOUT e tente novamente.") from None
        except (ConnectionError, OSError, http.client.HTTPException):
            raise SalesProviderError("Não foi possível conectar ao Ollama. Verifique se está em execução e se OLLAMA_BASE_URL está correto.") from None
        except Exception:
            raise SalesProviderError("O Ollama não retornou uma resposta completa válida. Tente novamente ou confira o modelo configurado.") from None
