"""Official SDK -> WebAgent -> FastAPI -> temporary SQLite, with no real network."""
import json
from uuid import uuid4
import groq
import httpx
import pytest
from fastapi.testclient import TestClient
from backend.config import Settings
from backend.main import create_app
from backend.tests.test_api import database
from core.sales.groq_provider import GroqSalesProvider
from core.sales.config import groq_settings

ANSWER = {'mensagem':'Olá! Sou Fernando, da Loung Tech. Podemos conversar sobre um site para sua empresa?',
          'angulo':'Apresentação digital', 'confianca':0.8}


def completion(answer=ANSWER, finish='stop'):
    return {'id':'synthetic','object':'chat.completion','created':1,'model':'openai/gpt-oss-20b',
            'choices':[{'index':0,'finish_reason':finish,'message':{'role':'assistant',
                'content':json.dumps(answer,ensure_ascii=False) if isinstance(answer,dict) else answer}}]}


def client_for(database, handler):
    def factory():
        return GroqSalesProvider(key='synthetic-private-key',model='openai/gpt-oss-20b',timeout=30,
            client_factory=lambda **kwargs:groq.Groq(**kwargs,http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    return TestClient(create_app(Settings(database,True),sdr_provider_factory=factory))


@pytest.mark.parametrize('upstream,provider_code,http,code',[
    (401,'invalid_api_key',503,'GROQ_AUTH_INVALID'),
    (403,'model_permission_blocked',503,'GROQ_PERMISSION_DENIED'),
    (404,'model_not_found',503,'GROQ_MODEL_UNAVAILABLE'),
    (400,'model_decommissioned',503,'GROQ_MODEL_UNAVAILABLE'),
    (429,'rate_limit_exceeded',429,'GROQ_RATE_LIMITED'),
    (503,'service_unavailable',503,'GROQ_UNAVAILABLE'),
    (400,'json_validate_failed',502,'GROQ_JSON_INVALID'),
])
def test_provider_failure_remains_diagnosable_and_safe(database,caplog,upstream,provider_code,http,code):
    calls=[]
    def handler(request):
        calls.append(request)
        return httpx.Response(upstream,json={'error':{'code':provider_code,'message':'synthetic-private-key PRIVATE_BODY'}})
    before=database.read_bytes()
    with client_for(database,handler) as client:
        body={'leadId':1,'requestId':str(uuid4())}
        for _ in range(2):
            response=client.post('/v1/sdr/generate',json=body)
            assert response.status_code==http
            assert response.headers['x-loung-sdr-code']==code
            assert 'PRIVATE' not in response.text and 'synthetic-private-key' not in response.text
    assert len(calls)==1
    assert database.read_bytes()==before
    assert code in caplog.text and provider_code in caplog.text
    assert 'PRIVATE' not in caplog.text and 'synthetic-private-key' not in caplog.text


@pytest.mark.parametrize('kind,code,http',[
    ('timeout','GROQ_TIMEOUT',504),('json','GROQ_JSON_INVALID',502),
    ('schema','GROQ_RESPONSE_INVALID',502),('length','GROQ_OUTPUT_TRUNCATED',502),
])
def test_timeout_parsing_and_incomplete_output_are_distinct(database,kind,code,http):
    def handler(request):
        if kind=='timeout':raise httpx.ReadTimeout('PRIVATE_BODY',request=request)
        data=completion('invalid JSON' if kind=='json' else {} if kind=='schema' else ANSWER,
                        finish='length' if kind=='length' else 'stop')
        return httpx.Response(200,json=data)
    with client_for(database,handler) as client:
        response=client.post('/v1/sdr/generate',json={'leadId':1,'requestId':str(uuid4())})
        assert response.status_code==http
        assert response.headers['x-loung-sdr-code']==code
        assert client.get('/v1/sdr/history/1').json()['items']==[]


def test_valid_generation_review_regeneration_and_sqlite_restart_without_supabase(database,monkeypatch):
    for key in ('SUPABASE_URL','SUPABASE_AUTH_AUDIENCE','LOUNG_POSTGRES_DSN','NEXT_PUBLIC_SUPABASE_URL','NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY'):
        monkeypatch.delenv(key,raising=False)
    payloads=[]
    def handler(request):
        assert str(request.url)=='https://api.groq.com/openai/v1/chat/completions'
        payloads.append(json.loads(request.content))
        answer={**ANSWER,'mensagem':ANSWER['mensagem']+(' Outra versão.' if len(payloads)>1 else '')}
        return httpx.Response(200,json=completion(answer))
    with client_for(database,handler) as client:
        request={'leadId':1,'recipient':'reception','service':'automation','instruction':'Mais breve','requestId':str(uuid4())}
        result=client.post('/v1/sdr/generate',json=request)
        assert result.status_code==200
        draft=result.json()
        assert draft['message']==ANSWER['mensagem'] and draft['model']=='openai/gpt-oss-20b'
        evidence=json.loads(payloads[0]['messages'][1]['content'])
        assert evidence['instrucao_adicional']=='Mais breve' and evidence['tipo_contato']=='recepcao_equipe'
        assert 'automa' in evidence['servico'].lower()
        assert payloads[0]['response_format']=={'type':'json_object'}
        assert client.get('/v1/sdr/history/1').json()['items']==[]
        text='Mensagem revisada manualmente: podemos conversar?'
        saved=client.post('/v1/sdr/history',json={'draftId':draft['draftId'],'message':text,'status':'EDITADA'})
        assert saved.status_code==200
        approved=client.post('/v1/sdr/history',json={'draftId':draft['draftId'],'message':text+' Obrigado.','status':'APROVADA'})
        assert approved.status_code==200
        next_draft=client.post('/v1/sdr/generate',json={**request,'requestId':str(uuid4()),'previousDraftId':draft['draftId']})
        assert next_draft.status_code==200 and next_draft.json()['message']!=draft['message']
        assert 'revisao_solicitada' in json.loads(payloads[1]['messages'][1]['content'])
    with client_for(database,handler) as client:
        history=client.get('/v1/sdr/history/1').json()['items']
        assert len(history)==1 and history[0]['message']==text+' Obrigado.'
    import sqlite3
    with sqlite3.connect(database) as c:
        assert c.execute('SELECT mensagem FROM outreach_revisions').fetchone()[0]==text


def test_missing_groq_config_is_explicit_not_a_generic_502(database,monkeypatch):
    from core.sales.config import create_groq_provider
    monkeypatch.setenv('GROQ_API_KEY','')
    monkeypatch.setenv('GROQ_MODEL','openai/gpt-oss-20b')
    with TestClient(create_app(Settings(database,True),sdr_provider_factory=lambda:create_groq_provider(load=False))) as client:
        response=client.post('/v1/sdr/generate',json={'leadId':1,'requestId':str(uuid4())})
        assert response.status_code==503 and response.headers['x-loung-sdr-code']=='GROQ_CONFIG_INVALID'


def test_powershell_environment_takes_precedence_over_env_file(tmp_path,monkeypatch):
    from dotenv import load_dotenv
    path=tmp_path/'synthetic.env'
    path.write_text('GROQ_API_KEY=synthetic-file-key\nGROQ_MODEL=openai/gpt-oss-20b\nGROQ_TIMEOUT=30\n',encoding='utf-8')
    monkeypatch.setenv('GROQ_API_KEY','synthetic-process-key')
    monkeypatch.setenv('GROQ_MODEL','synthetic-process-model')
    monkeypatch.delenv('GROQ_TIMEOUT',raising=False)
    load_dotenv(path,override=False,interpolate=False)
    settings=groq_settings(load=False)
    assert settings=={'key':'synthetic-process-key','model':'synthetic-process-model','timeout':'30'}


def test_sqlite_failure_is_safe_and_does_not_hide_as_groq_failure(database,caplog,monkeypatch):
    from backend.prospecting.storage import StorageError
    with client_for(database,lambda _:httpx.Response(200,json=completion())) as client:
        draft=client.post('/v1/sdr/generate',json={'leadId':1,'requestId':str(uuid4())}).json()
        def fail():raise StorageError('PRIVATE_SQLITE_PATH synthetic-private-key')
        monkeypatch.setattr(client.app.state.sdr.store.writer,'_backup',fail)
        response=client.post('/v1/sdr/history',json={'draftId':draft['draftId'],'message':'Texto revisado','status':'EDITADA'})
        assert response.status_code==503 and response.headers['x-loung-sdr-code']=='SDR_STORAGE_FAILED'
        assert client.get('/v1/sdr/history/1').json()['items']==[]
        assert 'SDR_STORAGE_FAILED' in caplog.text
        assert 'PRIVATE' not in caplog.text and 'synthetic-private-key' not in caplog.text


def test_offline_config_report_never_exposes_key_or_other_secrets(tmp_path,monkeypatch):
    from backend.scripts.check_groq_config import report
    path=tmp_path/'synthetic.env'
    path.write_text('GROQ_API_KEY=PRIVATE_FILE_KEY\nGROQ_MODEL=openai/gpt-oss-20b\nLOUNG_STORAGE_BACKEND=sqlite\n',encoding='utf-8')
    monkeypatch.setenv('GROQ_API_KEY','PRIVATE_PROCESS_KEY')
    monkeypatch.delenv('GROQ_MODEL',raising=False)
    result=report(path)
    assert result['keyPresent'] and not result['networkUsed']
    assert result['model']=='openai/gpt-oss-20b'
    assert result['processDiffersFromFile']['GROQ_API_KEY']
    assert 'PRIVATE' not in json.dumps(result)
