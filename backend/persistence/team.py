"""Organization administration through narrow SQL functions and existing RLS."""
from contextlib import closing
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel, ConfigDict
import psycopg
from backend.authorization import identity
from backend.persistence.errors import DatabaseAccessError

router=APIRouter(tags=['team'])

class MemberChange(BaseModel):
    model_config=ConfigDict(extra='forbid')
    role: Literal['owner','admin','member']

def owner():
    if identity.get().role!='owner':
        raise HTTPException(403,'Somente o owner pode gerenciar acessos.')

@router.get('/v1/team')
def team(request: Request):
    with closing(request.app.state.database.connection()) as c,c:
        rows=c.execute('SELECT * FROM public.team_roster()').fetchall()
    return {'items':rows,'canManage':identity.get().role=='owner','writesEnabled':request.app.state.writes_enabled}

def change(request,target,role,remove=False):
    owner()
    if str(target)==identity.get().user_id:
        raise HTTPException(403,'Não é permitido alterar o próprio acesso.')
    # Use raw connection so controlled SQLSTATEs become safe domain errors.
    c=request.app.state.database.open(identity.get(),'rw')
    try:
        c.execute('SELECT public.manage_member(%s,%s,%s)',(target,role,remove))
        c.commit()
    except psycopg.Error as error:
        if error.sqlstate=='23514': raise HTTPException(409,'A organização precisa manter ao menos um owner.') from None
        if error.sqlstate=='42501': raise HTTPException(403,'Gerenciamento de acesso não autorizado.') from None
        if error.sqlstate=='P0002': raise HTTPException(404,'Integrante não encontrado.') from None
        raise DatabaseAccessError('team_change',error) from None
    finally:c.close()
    return {'ok':True}

@router.patch('/v1/team/{user_id}')
def update(user_id:UUID,body:MemberChange,request:Request):
    return change(request,user_id,body.role)

@router.delete('/v1/team/{user_id}')
def remove(user_id:UUID,request:Request):
    return change(request,user_id,'member',True)

@router.get('/v1/organization/activities')
def activities(request:Request,before:int=Query(default=9223372036854775807,gt=0),limit:int=Query(default=30,ge=1,le=100)):
    if identity.get().role not in ('owner','admin'):
        raise HTTPException(403,'Histórico da organização disponível para owner e admin.')
    # Deliberately omit old_value/new_value (may contain contact or message data).
    with closing(request.app.state.database.connection()) as c,c:
        rows=c.execute("""SELECT a.id,a.at,a.action,a.lead_id,a.actor_id,p.display_name AS actor_name,a.origin,
          CASE WHEN split_part(a.action,'.',1)='organization_members' THEN a.new_value->>'user_id' END AS subject_id,
          CASE WHEN split_part(a.action,'.',1)='organization_members' THEN a.old_value->>'role' END AS before_role,
          CASE WHEN split_part(a.action,'.',1)='organization_members' THEN a.new_value->>'role' END AS after_role
          FROM public.audit_events a LEFT JOIN public.profiles p ON p.id=a.actor_id
          WHERE a.id<? ORDER BY a.id DESC LIMIT ?""", (before,limit)).fetchall()
    return {'items':rows,'nextCursor':rows[-1]['id'] if len(rows)==limit else None}
