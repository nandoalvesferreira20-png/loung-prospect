"""JWKS transport still rejects untrusted TLS; no external services or database."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import ssl
import pytest
import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from backend.authorization import TokenVerifier
from fastapi import HTTPException
import json
from types import SimpleNamespace


def test_jwks_rejects_unknown_self_signed_certificate(tmp_path, monkeypatch):
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'localhost')])
    now = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]), critical=False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / 'synthetic.pem', tmp_path / 'synthetic.key'
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                         serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"keys": []}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        verifier = TokenVerifier(f'https://localhost:{server.server_port}')
        with pytest.raises(jwt.PyJWKClientConnectionError):
            verifier.keys.fetch_data()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_jwks_failure_logs_only_safe_fields(caplog):
    def fail(_):
        raise jwt.PyJWKClientConnectionError('PRIVATE_TOKEN_COOKIE_URL')

    verifier = TokenVerifier('https://synthetic.invalid')
    verifier.keys = SimpleNamespace(get_signing_key_from_jwt=fail)
    token = jwt.encode({}, ec.generate_private_key(ec.SECP256R1()), algorithm='ES256')
    with pytest.raises(HTTPException) as failure:
        verifier.verify('Bearer ' + token)
    assert failure.value.status_code == 503
    assert 'PRIVATE' not in caplog.text and token not in caplog.text
    entry = json.loads(caplog.records[-1].message)
    assert set(entry) == {'component', 'stage', 'http_status', 'error_type', 'correlation_id', 'duration_ms'}
    assert entry['stage'] == 'jwks_fetch' and entry['duration_ms'] >= 0
