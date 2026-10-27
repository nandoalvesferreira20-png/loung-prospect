"""Native Windows trust remains verified; all TLS requests target loopback only."""
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import json
import ssl
import sys
import groq
import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID
from core.sales.groq_provider import GroqSalesProvider, _sdk_client
from core.sales.errors import GroqProviderError


@pytest.fixture
def https_server(tmp_path):
    key=ec.generate_private_key(ec.SECP256R1())
    name=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'localhost')])
    now=datetime.now(timezone.utc)
    cert=(x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=1))
          .not_valid_after(now+timedelta(days=1))
          .add_extension(x509.SubjectAlternativeName([x509.DNSName('localhost')]),critical=False)
          .add_extension(x509.BasicConstraints(ca=True,path_length=None),critical=True)
          .sign(key,hashes.SHA256()))
    cert_file,key_file=tmp_path/'synthetic.pem',tmp_path/'synthetic.key'
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(data)
            answer={'mensagem':'Olá! Sou Fernando, da Loung Tech. Podemos conversar sobre um site?', 'angulo':'Site profissional','confianca':0.8}
            response={'id':'synthetic','object':'chat.completion','created':1,'model':'test-model',
                      'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(answer)}}]}
            body=json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self,*_):pass
    class Server(ThreadingHTTPServer):
        def handle_error(self,*args):
            # Clients intentionally abort untrusted TLS handshakes in these tests.
            if not isinstance(sys.exc_info()[1],(ssl.SSLError,ConnectionError)):
                super().handle_error(*args)
    server=Server(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file,key_file)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    thread=Thread(target=server.serve_forever,daemon=True)
    thread.start()
    try:yield server.server_port,cert_file,calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.skipif(sys.platform!='win32',reason='Windows native CA store')
def test_default_groq_client_uses_native_ca_and_still_rejects_untrusted_cert(https_server,monkeypatch):
    import truststore
    port,_,calls=https_server
    monkeypatch.setenv('NO_PROXY','127.0.0.1,localhost')
    with _sdk_client(api_key='synthetic-key',timeout=2,max_retries=0,base_url=f'https://localhost:{port}') as client:
        context=client._client._transport._pool._ssl_context
        assert isinstance(context,truststore.SSLContext)
        assert context.verify_mode==ssl.CERT_REQUIRED and context.check_hostname
        with pytest.raises(groq.APIConnectionError):
            client.chat.completions.create(model='test-model',messages=[{'role':'user','content':'JSON'}])
    assert calls==[]


@pytest.mark.skipif(sys.platform!='win32',reason='Windows native CA store')
def test_native_tls_generation_accepts_trusted_local_chain_and_rejects_wrong_hostname(https_server,monkeypatch):
    import truststore
    port,cert_file,calls=https_server
    monkeypatch.setenv('NO_PROXY','127.0.0.1,localhost')
    original=truststore.SSLContext
    def trusted_context(*args,**kwargs):
        context=original(*args,**kwargs)
        # Trust only in this test client; no OS/global trust changes.
        context.load_verify_locations(cafile=str(cert_file))
        return context
    monkeypatch.setattr(truststore,'SSLContext',trusted_context)
    with _sdk_client(api_key='synthetic-key',timeout=2,max_retries=0,base_url=f'https://localhost:{port}') as client:
        result=client.chat.completions.create(model='test-model',messages=[{'role':'user','content':'JSON'}])
        assert result.choices[0].finish_reason=='stop'
    assert len(calls)==1
    with _sdk_client(api_key='synthetic-key',timeout=2,max_retries=0,base_url=f'https://127.0.0.1:{port}') as client:
        with pytest.raises(groq.APIConnectionError):
            client.chat.completions.create(model='test-model',messages=[{'role':'user','content':'JSON'}])
    assert len(calls)==1


def test_certificate_failure_gets_specific_safe_code_without_retry(caplog):
    calls=[]
    def handler(request):
        calls.append(request)
        try:raise ssl.SSLCertVerificationError('PRIVATE_CERTIFICATE_DATA')
        except ssl.SSLCertVerificationError as error:
            raise httpx.ConnectError('PRIVATE_KEY',request=request) from error
    provider=GroqSalesProvider(key='synthetic-key',model='test-model',
        client_factory=lambda **kwargs:groq.Groq(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    with pytest.raises(GroqProviderError) as failure:
        provider.generate(system_prompt='JSON',evidence={})
    assert failure.value.code=='GROQ_TLS_FAILED' and len(calls)==1
    assert 'GROQ_TLS_FAILED' in caplog.text and 'PRIVATE' not in caplog.text
