"""Safe database failure classification; never expose driver exception text."""
from backend.repository import DatabaseUnavailable
import re

def permission_details(error):
    """Allowlisted identifiers only; driver messages/context can contain secrets."""
    if getattr(error,'sqlstate',None)!='42501':return {}
    primary=getattr(getattr(error,'diag',None),'message_primary','') or ''
    if re.fullmatch(r'permission denied for schema (auth|public)',primary):
        return {'object_type':'schema','object':primary.rsplit(' ',1)[1],'privilege':'USAGE'}
    if primary=='permission denied for function uid':
        return {'object_type':'function','object':'auth.uid()','privilege':'EXECUTE'}
    functions={'is_member':'public.is_member(uuid)','shared_profile':'public.shared_profile(uuid)','active_org':'public.active_org()'}
    for name,signature in functions.items():
        if primary=='permission denied for function '+name:
            return {'object_type':'function','object':signature,'privilege':'EXECUTE'}
    if re.fullmatch(r'permission denied for table (organization_members|organizations|profiles)',primary):
        return {'object_type':'table','object':'public.'+primary.rsplit(' ',1)[1],'privilege':'SELECT'}
    if primary=='permission denied to set role "loung_api"':
        return {'object_type':'role','object':'loung_api','privilege':'SET'}
    return {}


def database_error_code(error):
    code=getattr(error,'sqlstate',None)
    if code=='42501':return 'DB_PERMISSION_DENIED'
    if code in ('28P01','28000'):return 'DB_LOGIN_REJECTED'
    if code in ('42P01','42883'):return 'DB_SCHEMA_MISSING'
    text=str(error).lower()
    if 'tenant or user not found' in text:return 'DB_POOLER_USER_FORMAT'
    if 'password authentication failed' in text:return 'DB_LOGIN_REJECTED'
    if 'could not translate host name' in text or 'failed to resolve host' in text:return 'DB_DNS_FAILED'
    if 'permission denied' in text:return 'DB_PERMISSION_DENIED'
    if 'network is unreachable' in text or 'unreachable network' in text:return 'DB_NETWORK_UNREACHABLE'
    return 'DB_CONNECTION_FAILED'


class DatabaseAccessError(DatabaseUnavailable):
    def __init__(self,stage,error,statement_id=None):
        super().__init__('Persistência PostgreSQL indisponível.')
        self.stage=stage
        self.code=database_error_code(error)
        self.error_type=type(error).__name__
        state=getattr(error,'sqlstate',None)
        self.sqlstate=state if isinstance(state,str) and re.fullmatch('[A-Z0-9]{5}',state) else None
        self.statement_id=statement_id
        self.permission=permission_details(error)
