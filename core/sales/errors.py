"""Only these provider errors contain messages safe to show to the operator."""


class SalesConfigurationError(ValueError):
    pass


class SalesProviderError(RuntimeError):
    pass


class GroqProviderError(SalesProviderError):
    """Only server-owned codes/messages cross the SDK boundary."""
    MESSAGES = {
        'GROQ_AUTH_INVALID': (503, 'A Groq recusou a credencial. Confira GROQ_API_KEY no ambiente do backend.'),
        'GROQ_PERMISSION_DENIED': (503, 'A Groq negou acesso (403). Confira as permissões da chave e do modelo.'),
        'GROQ_MODEL_UNAVAILABLE': (503, 'Modelo Groq indisponível para esta conta. Confira GROQ_MODEL e as permissões no GroqCloud.'),
        'GROQ_RATE_LIMITED': (429, 'Limite de requisições da Groq atingido (429). Aguarde antes de tentar novamente.'),
        'GROQ_TIMEOUT': (504, 'A Groq excedeu o tempo de espera. Tente novamente mais tarde.'),
        'GROQ_CONNECTION_FAILED': (503, 'Não foi possível conectar à Groq. Confira sua conexão e os certificados TLS.'),
        'GROQ_TLS_FAILED': (503, 'Não foi possível validar o certificado TLS da Groq. Confira os certificados confiáveis do Windows e atualize as dependências do backend.'),
        'GROQ_UNAVAILABLE': (503, 'A Groq rejeitou a solicitação por indisponibilidade temporária. Tente novamente mais tarde.'),
        'GROQ_REQUEST_REJECTED': (502, 'A Groq rejeitou a solicitação. Confira GROQ_MODEL e a disponibilidade na conta.'),
        'GROQ_JSON_INVALID': (502, 'A Groq não retornou JSON válido. Nenhuma mensagem foi salva; tente gerar outra versão.'),
        'GROQ_OUTPUT_TRUNCATED': (502, 'A Groq atingiu o limite de saída antes de concluir o JSON. Nenhuma mensagem foi salva.'),
        'GROQ_RESPONSE_INVALID': (502, 'A Groq não retornou um rascunho válido e completo. Nenhuma mensagem foi salva.'),
    }

    def __init__(self, code):
        self.code = code
        self.http_status, message = self.MESSAGES[code]
        super().__init__(message)
