"""Official Groq SDK adapter. No automatic retries, tools or provider fallback."""
import json
import logging
import math
import ssl
import sys

from .errors import SalesConfigurationError, SalesProviderError, GroqProviderError
from .models import SalesGeneration


def _sdk_client(**options):
    """Use Windows' trusted CA store without changing global TLS behavior."""
    import groq
    if sys.platform == 'win32':
        import truststore
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        options['http_client'] = groq.DefaultHttpxClient(verify=context)
    return groq.Groq(**options)


def _tls_verification_failed(error):
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if isinstance(error, ssl.SSLCertVerificationError):
            return True
        error = error.__cause__ or error.__context__
    return False


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
            with (self.client_factory or _sdk_client)(api_key=self._key, timeout=self.timeout,
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
        stage = 'request'
        try:
            import groq
        except ImportError:
            raise SalesProviderError("Instale as dependências do projeto para usar a Groq.") from None
        try:
            # Construct and close inside the worker; never log SDK bodies/headers.
            with (self.client_factory or _sdk_client)(api_key=self._key, timeout=self.timeout,
                    max_retries=0, base_url="https://api.groq.com") as client:
                result = client.chat.completions.create(model=self.model, stream=False,
                    messages=[{"role": "system", "content": system_prompt},
                              {"role": "user", "content": json.dumps(evidence, ensure_ascii=False)}],
                    response_format={"type": "json_object"}, max_completion_tokens=1600)
            stage = 'response'
            if len(result.choices) == 1 and result.choices[0].finish_reason == 'length':
                raise GroqProviderError('GROQ_OUTPUT_TRUNCATED')
            if len(result.choices) != 1 or result.choices[0].finish_reason != "stop":
                raise ValueError
            message = result.choices[0].message
            if message.tool_calls or not isinstance(message.content, str) or len(message.content) > 20_000:
                raise ValueError
            stage = 'json'
            data = json.loads(message.content)
            stage = 'schema'
            SalesGeneration.from_mapping(data)
            self.connection_verified = True
            logging.getLogger(__name__).info("SDR IA: provider=groq resultado=validado")
            return data
        except Exception as error:
            # Never log str(error), SDK response bodies, prompts, headers or key.
            upstream = error.status_code if isinstance(error, groq.APIStatusError) else (200 if stage != 'request' else None)
            body = error.body if isinstance(error, groq.APIStatusError) else None
            if isinstance(body, dict) and isinstance(body.get('error'), dict):
                body = body['error']
            provider_code = body.get('code') if isinstance(body, dict) else None
            allowed_codes = ('invalid_api_key', 'model_not_found', 'model_decommissioned',
                             'model_permission_blocked', 'rate_limit_exceeded',
                             'json_validate_failed', 'service_unavailable')
            provider_code = provider_code if provider_code in allowed_codes else None
            if isinstance(error, GroqProviderError): code = error.code
            elif isinstance(error, groq.AuthenticationError): code = 'GROQ_AUTH_INVALID'
            elif isinstance(error, groq.PermissionDeniedError): code = 'GROQ_PERMISSION_DENIED'
            elif isinstance(error, groq.RateLimitError): code = 'GROQ_RATE_LIMITED'
            elif isinstance(error, groq.APITimeoutError): code = 'GROQ_TIMEOUT'
            elif isinstance(error, groq.APIConnectionError): code = 'GROQ_TLS_FAILED' if _tls_verification_failed(error) else 'GROQ_CONNECTION_FAILED'
            elif provider_code in ('model_not_found', 'model_decommissioned'): code = 'GROQ_MODEL_UNAVAILABLE'
            elif provider_code == 'json_validate_failed' or isinstance(error, json.JSONDecodeError): code = 'GROQ_JSON_INVALID'
            elif upstream is not None and upstream >= 500: code = 'GROQ_UNAVAILABLE'
            elif isinstance(error, groq.APIStatusError): code = 'GROQ_REQUEST_REJECTED'
            else: code = 'GROQ_RESPONSE_INVALID'
            failure = GroqProviderError(code)
            error_types = ('AuthenticationError', 'PermissionDeniedError', 'RateLimitError', 'NotFoundError',
                           'BadRequestError', 'InternalServerError', 'APITimeoutError', 'APIConnectionError',
                           'JSONDecodeError', 'ValueError', 'GroqProviderError')
            kind = type(error).__name__
            logging.getLogger(__name__).warning(json.dumps({'event':'groq.failure', 'stage':stage,
                'endpoint':'/openai/v1/chat/completions', 'http':upstream,
                'error_type':kind if kind in error_types else 'Error',
                'provider_code':provider_code, 'code':code}))
            raise failure from None
