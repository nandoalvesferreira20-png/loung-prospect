"""Manual lead creation and editing; reuses tenant transactions and revision checks."""
from contextlib import closing
from datetime import datetime,timezone
from fastapi import APIRouter,Request,HTTPException,Path
from pydantic import BaseModel,ConfigDict,Field,StringConstraints
from typing import Annotated
from backend.crm.models import Mutation
from backend.crm.service import revision

router=APIRouter(tags=['leads'])
Text=Annotated[str,StringConstraints(strip_whitespace=True,max_length=500)]

class LeadFields(BaseModel):
    model_config=ConfigDict(extra='forbid')
    empresa:Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=200)]
    cidade:Text=''
    segmento:Text=''
    telefone:Text=''
    whatsapp:Text=''
    email:Text=''
    site:Text=''
    endereco:Text=''

class LeadEdit(LeadFields,Mutation):
    observacoes:str=Field(default='',max_length=4000)

@router.get('/v1/leads/{lead_id}/edit')
def editable(request:Request,lead_id:int=Path(gt=0,le=9223372036854775807)):
    service=request.app.state.crm
    with closing(service.writer.connect()) as c:
        row=service.require_lead(c,lead_id)
        return {'fields':{k:row.get(k) or '' for k in LeadFields.model_fields},'observacoes':row.get('observacoes') or '', 'revision':revision(row)}

@router.post('/v1/leads',status_code=201)
def create(body:LeadFields,request:Request):
    writer=request.app.state.crm.writer
    return writer.save([body.model_dump()])

@router.patch('/v1/leads/{lead_id}')
def edit(body:LeadEdit,request:Request,lead_id:int=Path(gt=0,le=9223372036854775807)):
    service=request.app.state.crm
    with closing(service.writer.connect('rw')) as c,c:
        row=service.require_lead(c,lead_id)
        if revision(row)!=body.revision:
            raise HTTPException(409,'Lead alterado em outra tela. Atualize antes de salvar.')
        values=body.model_dump(exclude={'revision'})
        values['updated_at']=datetime.now(timezone.utc).isoformat()
        # Field names come exclusively from the server-owned validated model.
        c.execute('UPDATE leads SET '+','.join(k+'=?' for k in values)+' WHERE id=?',(*values.values(),lead_id))
        current=service.require_lead(c,lead_id)
    return {'leadId':lead_id,'revision':revision(current),'changed':True}
