"""Loopback-only Auth/API fixture. No database, env files or real accounts."""
from datetime import datetime, timedelta, timezone
import json
from secrets import token_urlsafe
from uuid import uuid4
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from backend.authorization import TokenVerifier


def create_app():
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=['http://127.0.0.1:3198'],
                       allow_methods=['*'], allow_headers=['*'])
    key = ec.generate_private_key(ec.SECP256R1())
    uid, password = str(uuid4()), token_urlsafe(24)
    issuer = 'http://127.0.0.1:8112/auth/v1'
    verifier = TokenVerifier('http://127.0.0.1:8112')
    refreshes, revoked = {}, set()
    state = {'auth': True, 'backend': True, 'verified': 0}
    user = {'id': uid, 'aud': 'authenticated', 'role': 'authenticated',
            'email': 'test@example.invalid', 'app_metadata': {}, 'user_metadata': {}}

    def session():
        now = datetime.now(timezone.utc)
        refresh = token_urlsafe(32)
        refreshes[refresh] = True
        token = jwt.encode({'sub': uid, 'role': 'authenticated', 'iss': issuer,
                            'aud': 'authenticated', 'iat': now,
                            'exp': now + timedelta(hours=1)}, key, algorithm='ES256',
                           headers={'kid': 'synthetic-key'})
        return {'access_token': token, 'refresh_token': refresh, 'expires_in': 3600,
                'token_type': 'bearer', 'user': user}

    @app.get('/__test/config')
    def config():
        return {'signature': 'auth-session-no-database', 'password': password, **state}

    @app.post('/__test/state')
    async def control(request: Request):
        values = await request.json()
        for name in ('auth', 'backend'):
            if name in values:
                state[name] = bool(values[name])
        return {'ok': True}

    @app.get('/auth/v1/.well-known/jwks.json')
    def jwks():
        return {'keys': [{**json.loads(jwt.algorithms.ECAlgorithm.to_jwk(key.public_key())),
                          'kid': 'synthetic-key', 'alg': 'ES256', 'use': 'sig'}]}

    @app.post('/auth/v1/token')
    async def login(request: Request):
        body = await request.json()
        if request.query_params.get('grant_type') == 'refresh_token':
            if refreshes.pop(body.get('refresh_token'), None):
                return session()
        elif body.get('email') == user['email'] and body.get('password') == password:
            return session()
        return JSONResponse({'code': 'invalid_credentials', 'msg': 'Invalid login credentials'}, 400)

    @app.get('/auth/v1/user')
    def get_user(request: Request):
        if not state['auth']:
            return JSONResponse({'code': 'unexpected_failure'}, 503)
        raw = request.headers.get('authorization', '')
        try:
            if raw in revoked:
                raise ValueError()
            jwt.decode(raw[7:], key.public_key(), algorithms=['ES256'],
                       audience='authenticated', issuer=issuer)
            return user
        except (jwt.PyJWTError, ValueError):
            return JSONResponse({'code': 'bad_jwt'}, 401)

    @app.post('/auth/v1/logout')
    def logout(request: Request):
        revoked.add(request.headers.get('authorization', ''))
        return {}

    @app.get('/v1/{path:path}')
    def api(path: str, request: Request):
        try:
            verifier.verify(request.headers.get('authorization'))
        except HTTPException as error:
            return JSONResponse({'code': 'AUTH_INVALID'}, error.status_code)
        state['verified'] += 1
        if not state['backend']:
            return JSONResponse({'code': 'DB_UNAVAILABLE'}, 503)
        if path == 'session':
            return {'userId': uid, 'displayName': 'Synthetic Operator',
                    'organization': 'Synthetic Workspace', 'role': 'member', 'writesEnabled': False}
        if path == 'overview':
            return {'total': 2, 'today': 0, 'overdue': 0, 'meetings': 0,
                    'referenceDate': '2026-10-22', 'invalidDates': 0,
                    'stageCounts': [{'stage': 'Novo', 'count': 2}], 'actions': []}
        if path == 'dashboard/commercial':
            return {name: 0 for name in ('total', 'contacted', 'responded', 'negotiations',
                                         'converted', 'pending', 'overdue', 'invalidDates')}
        return {'available': True, 'items': [], 'total': 0, 'invalidDates': 0,
                'writesEnabled': False, 'stages': [], 'page': 1, 'pageSize': 20}

    return app
