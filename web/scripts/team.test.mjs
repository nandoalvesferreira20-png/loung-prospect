import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import ts from 'typescript';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const container={exports:{}};
const code=ts.transpileModule(fs.readFileSync(new URL('../src/lib/api/team-proxy.ts',import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
new Function('require','module','exports',code)(name=>name==='server-only'?{}:name==='@/lib/auth/server'?{backendHeaders:async()=>({Authorization:'Bearer synthetic-only'})}:name==='./local-request'?{isLocalRequest:r=>r.headers.get('origin')!=='https://outsider.invalid'}:require(name),container,container.exports);
const {proxyTeam}=container.exports;
const id='10000000-0000-4000-8000-000000000001';
test('BFF rejects cross-origin writes and body organization/role escalation fields',async()=>{
  assert.equal((await proxyTeam(new Request('http://localhost/api/team/'+id,{method:'DELETE',headers:{origin:'https://outsider.invalid'}}),'team',id)).status,403);
  assert.equal((await proxyTeam(new Request('http://localhost/api/team/'+id,{method:'PATCH',body:JSON.stringify({role:'owner',organization_id:id})}),'team',id)).status,422);
  assert.equal((await proxyTeam(new Request('http://localhost/api/team/not-a-uuid'),'team','not-a-uuid')).status,422);
});
test('BFF uses fixed paths, verified bearer and never browser organization/cookies',async()=>{
  const original=globalThis.fetch;
  const previous=process.env.LOUNG_API_URL;process.env.LOUNG_API_URL='http://127.0.0.1:8100';
  try{
    globalThis.fetch=async(url,options)=>{
      assert.equal(url.pathname,'/v1/team/'+id);
      assert.equal(url.search,'');
      assert.deepEqual(options.headers,{Authorization:'Bearer synthetic-only'});
      assert.equal(options.redirect,'error');
      assert.equal(options.cache,'no-store');
      assert.equal(options.body,JSON.stringify({role:'admin'}));
      return Response.json({ok:true});
    };
    const result=await proxyTeam(new Request('http://localhost/api/team/'+id+'?organization_id=untrusted',{method:'PATCH',headers:{cookie:'untrusted','x-organization-id':'untrusted'},body:JSON.stringify({role:'admin'})}),'team',id);
    assert.equal(result.status,200);
    assert.equal(result.headers.get('Cache-Control'),'no-store');
    globalThis.fetch=async()=>new Response('PRIVATE_DB_DETAIL',{status:500});
    const failed=await proxyTeam(new Request('http://localhost/api/team'),'team');
    assert.equal(failed.status,502);assert.ok(!(await failed.text()).includes('PRIVATE_DB_DETAIL'));
  }finally{globalThis.fetch=original;if(previous===undefined)delete process.env.LOUNG_API_URL;else process.env.LOUNG_API_URL=previous;}
});
