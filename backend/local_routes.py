"""Local lead editing uses the same revision, backup and transaction rules as CRM."""
from contextlib import closing
from datetime import datetime, timezone
import json
import sqlite3
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from backend.persistence.leads import LeadFields, LeadEdit
from backend.crm.service import revision
from backend.prospecting.storage import StorageError
from core.database.lead_repository import LeadRepository

router = APIRouter()


@router.get('/v1/session')
def session(request: Request):
    return {'displayName': 'Uso local', 'organization': 'SQLite local', 'role': 'local',
            'writesEnabled': request.app.state.crm.writer.enabled}


@router.get('/v1/leads/{lead_id}/edit')
def editable(lead_id: int, request: Request):
    service = request.app.state.crm
    with closing(service.writer.connect()) as c:
        row = service.require_lead(c, lead_id)
        return {'fields': {key: row.get(key) or '' for key in LeadFields.model_fields},
                'observacoes': row.get('observacoes') or '', 'revision': revision(row)}


@router.post('/v1/leads', status_code=201)
def create(body: LeadFields, request: Request):
    writer = request.app.state.crm.writer
    if not writer.enabled:
        raise HTTPException(403, 'Escrita local desabilitada.')
    return writer.save([body.model_dump()])


@router.patch('/v1/leads/{lead_id}')
def edit(lead_id: int, body: LeadEdit, request: Request):
    service = request.app.state.crm
    writer = service.writer
    if not writer.enabled:
        raise HTTPException(403, 'Escrita local desabilitada.')
    try:
        with writer.lock:
            with closing(writer.connect('rw')) as c, c:
                c.execute('BEGIN IMMEDIATE')
                row = service.require_lead(c, lead_id)
                if revision(row) != body.revision:
                    raise HTTPException(409, 'Lead alterado em outra tela. Atualize antes de salvar.')
                values = body.model_dump(exclude={'revision'})
                other = LeadRepository.find_existing(c, values)
                if other is not None and other != lead_id:
                    raise HTTPException(409, 'Outro lead ja utiliza esta identidade.')
                if not writer.backed_up:
                    writer._backup()
                values['updated_at'] = datetime.now(timezone.utc).isoformat()
                c.execute('UPDATE leads SET ' + ','.join(key + '=?' for key in values) + ' WHERE id=?', (*values.values(), lead_id))
                c.execute('INSERT INTO lead_interactions (lead_id,tipo,descricao,created_at) VALUES (?,?,?,?)',
                          (lead_id, 'CRM · Cadastro editado', 'Dados cadastrais revisados manualmente.', values['updated_at']))
                current = service.require_lead(c, lead_id)
            writer.backed_up = True
        return {'leadId': lead_id, 'revision': revision(current), 'changed': True}
    except sqlite3.Error:
        raise StorageError('Banco ocupado ou indisponivel. Nenhuma alteracao foi salva.') from None


class Preferences(BaseModel):
    values: dict[str, str] = Field(default_factory=dict, max_length=30)


@router.get('/v1/local/preferences')
def preferences(request: Request):
    with closing(request.app.state.crm.writer.connect()) as c:
        return {'values': {r['key']: json.loads(r['value']) for r in c.execute('SELECT key,value FROM local_settings')}}


@router.put('/v1/local/preferences')
def save_preferences(body: Preferences, request: Request):
    writer = request.app.state.crm.writer
    if not writer.enabled:
        raise HTTPException(403, 'Escrita local desabilitada.')
    if any(len(key) > 100 or len(value) > 4000 for key, value in body.values.items()):
        raise HTTPException(422, 'Preferencia extensa demais.')
    with writer.lock, closing(writer.connect('rw')) as c, c:
        c.execute('BEGIN IMMEDIATE')
        for key, value in body.values.items():
            c.execute('INSERT INTO local_settings VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at',
                      (key, json.dumps(value), datetime.now(timezone.utc).isoformat()))
    return body
