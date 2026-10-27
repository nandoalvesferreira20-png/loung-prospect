"""Cryptographic Supabase verification. No decoded-only token acceptance."""
from contextvars import ContextVar
from dataclasses import dataclass
from uuid import UUID, uuid4
import json
import logging
from time import monotonic
import ssl
import sys
import jwt
from fastapi import HTTPException

@dataclass(frozen=True)
class Identity:
    user_id: str
    organization_id: str = ''
    role: str = ''

identity = ContextVar('loung_identity', default=None)

class TokenVerifier:
    def __init__(self, url, audience='authenticated'):
        self.issuer = url.rstrip('/') + '/auth/v1'
        self.audience = audience
        # Use Windows' native chain validation and trusted enterprise CAs for
        # JWKS, just as the browser does. Do not patch global SSL behavior.
        if sys.platform == 'win32':
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        else:
            context = ssl.create_default_context()
        self.keys = jwt.PyJWKClient(self.issuer + '/.well-known/jwks.json',
                                    timeout=5, ssl_context=context)

    def verify(self, authorization):
        started = monotonic()
        if not authorization or not authorization.startswith('Bearer '):
            raise HTTPException(401, 'Sessão ausente ou expirada.')
        token = authorization[7:]
        try:
            header = jwt.get_unverified_header(token)
            if header.get('alg') not in ('ES256', 'RS256'):
                raise jwt.InvalidTokenError()
            key = self.keys.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, key.key, algorithms=['ES256','RS256'],
                issuer=self.issuer, audience=self.audience,
                options={'require':['exp','iat','sub','iss','aud']})
            if claims.get('role') != 'authenticated':
                raise jwt.InvalidTokenError()
            return str(UUID(claims['sub']))
        except jwt.PyJWKClientConnectionError:
            logging.getLogger('loung.auth').warning(json.dumps({
                'component': 'fastapi_jwt', 'stage': 'jwks_fetch', 'http_status': 503,
                'error_type': 'PyJWKClientConnectionError', 'correlation_id': str(uuid4()),
                'duration_ms': round((monotonic() - started) * 1000),
            }))
            raise HTTPException(503, 'Verificação de sessão indisponível.') from None
        except (jwt.PyJWTError, ValueError, TypeError, KeyError):
            raise HTTPException(401, 'Sessão inválida ou expirada. Entre novamente.') from None
