// Read-only probes. Never print URLs, response bodies, cookies or credentials.
import nextEnv from '@next/env';
import {randomUUID} from 'node:crypto';
import path from 'node:path';
nextEnv.loadEnvConfig(path.resolve(import.meta.dirname,'..'),true,{info(){},error(){}});
const correlation_id=randomUUID();
const base=process.env.NEXT_PUBLIC_SUPABASE_URL;
const key=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim() || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY?.trim();
const probes=[
  ['supabase_health',base ? `${base.replace(/\/$/,'')}/auth/v1/health` : null,{apikey:key}],
  ['supabase_jwks',base ? `${base.replace(/\/$/,'')}/auth/v1/.well-known/jwks.json` : null,{}],
  ['fastapi_health',new URL('/health',process.env.LOUNG_API_URL || 'http://127.0.0.1:8000').href,{}],
];
for(const [stage,url,headers] of probes){
  const start=performance.now();
  let http_status=null,error_type=null;
  try{
    if(!url || (stage==='supabase_health' && !key))throw new Error('Configuration');
    const target=new URL(url);
    if(target.username || target.password || (stage==='fastapi_health' && (target.protocol!=='http:' || !['localhost','127.0.0.1','[::1]'].includes(target.hostname))))throw new Error('Configuration');
    const response=await fetch(target,{headers,signal:AbortSignal.timeout(8000),redirect:'error'});
    http_status=response.status;
    await response.body?.cancel();
    if(!response.ok)process.exitCode=1;
  }catch(error){
    const types={SELF_SIGNED_CERT_IN_CHAIN:'TLSCertificateChainError',UNABLE_TO_VERIFY_LEAF_SIGNATURE:'TLSCertificateChainError',CERT_HAS_EXPIRED:'TLSCertificateExpiredError',ENOTFOUND:'DNSResolutionError',ECONNREFUSED:'ConnectionRefusedError'};
    error_type=types[error.cause?.code] || (error.name==='TimeoutError' ? 'TimeoutError' : 'ConnectionOrConfigurationError');
    process.exitCode=1;
  }
  console.log(JSON.stringify({component:'auth_connectivity',stage,http_status,error_type,correlation_id,duration_ms:Math.round(performance.now()-start)}));
}
