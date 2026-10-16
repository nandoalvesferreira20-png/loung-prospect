"""Official Groq SDK adapter. No automatic retries, tools or provider fallback."""
import json
import logging
import math

from .errors import SalesConfigurationError, SalesProviderError
from .models import SalesGeneration


class GroqSalesProvider:
    provider_name = "groq"

    def __init__(self, *, key, model, timeout=60, client_factory=None):
        if not key.strip() or not model.strip():
            raise SalesConfigurationError("Configure GROQ_API_KEY e GROQ_MODEL no .env.")
        try:
            self.timeout = float(timeout)
            if not math.isfinite(self.timeout) or not 0 < self.timeout <= 300:
                raise ValueError
        except (TypeError, ValueError):
            raise SalesConfigurationError("GROQ_TIMEOUT deve estar entre 1 e 300 segundos.") from None
        self._key, self.model = key.strip(), model.strip()
        self.client_factory = client_factory
        self.connection_verified = False

    def test_connection(self):
        """Explicit authenticated model lookup: no generation, no lead data."""
        try:
            import groq
        except ImportError:
            raise SalesProviderError("Instale as dependências do projeto para usar a Groq.") from None
        try:
            with (self.client_factory or groq.Groq)(api_key=self._key, timeout=self.timeout,
                    max_retries=0, base_url="https://api.groq.com") as client:
                model = client.models.retrieve(self.model)
                if model.id != self.model:
                    raise ValueError
            self.connection_verified = True
        except Exception:
            self.connection_verified = False
            raise SalesProviderError("Erro de conexão: confira a credencial, o modelo e os limites da Groq.") from None

    def generate(self, *, system_prompt, evidence):
        self.connection_verified = False
        try:
            import groq
        except ImportError:
            raise SalesProviderError("Instale as dependências do projeto para usar a Groq.") from None
        try:
            # Construct and close inside the worker; never log SDK bodies/headers.
            with (self.client_factory or groq.Groq)(api_key=self._key, timeout=self.timeout,
                    max_retries=0, base_url="https://api.groq.com") as client:
                result = client.chat.completions.create(model=self.model, stream=False,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
                    response_format={"type": "json_object"}, max_completion_tokens=1600)
            if len(result.choices) != 1 or result.choices[0].finish_reason != "stop":
                raise ValueError
            message = result.choices[0].message
            if message.tool_calls or not isinstance(message.content, str) or len(message.content) > 20_000:
                raise ValueError
            data = json.loads(message.content)
            SalesGeneration.from_mapping(data)
            self.connection_verified = True
            logging.getLogger(__name__).info("SDR IA: provider=groq resultado=validado")
            return data
        except groq.AuthenticationError:
            raise SalesProviderError("A Groq recusou a credencial. Confira GROQ_API_KEY.") from None
        except groq.PermissionDeniedError:
            raise SalesProviderError("A Groq negou acesso (403). Confira as permissões da chave e do modelo.") from None
        except groq.RateLimitError:
            raise SalesProviderError("Limite de requisições da Groq atingido (429). Aguarde antes de tentar novamente.") from None
        except groq.APITimeoutError:
            raise SalesProviderError("A Groq excedeu o tempo de espera. Tente novamente mais tarde.") from None
        except groq.APIConnectionError:
            raise SalesProviderError("Não foi possível conectar à Groq. Confira sua conexão.") from None
        except groq.APIStatusError:
            raise SalesProviderError("A Groq rejeitou a solicitação. Confira GROQ_MODEL e a disponibilidade na conta.") from None
        except Exception:
            raise SalesProviderError("A Groq não retornou um rascunho válido e completo. Nenhuma mensagem foi salva.") from None
