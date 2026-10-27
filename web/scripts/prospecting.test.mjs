import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import {createRequire} from 'node:module';
const runtimeRequire=createRequire(import.meta.url);
function load(file,stubs={}) {
  const container={exports:{}};
  const source=fs.readFileSync(path.resolve(import.meta.dirname,'../src',file),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('require','module','exports',code)(name=>name in stubs?stubs[name]:runtimeRequire(name),container,container.exports);
  return container.exports;
}
const contracts=load('lib/api/prospecting-contracts.ts');
const local=load('lib/api/local-request.ts',{'server-only':{}});
const headers=async()=>({Authorization:'Bearer synthetic-only'});
function proxy(auth=headers) {return load('lib/api/prospecting-proxy.ts',{'server-only':{},'@/lib/auth/server':{backendHeaders:auth},'./prospecting-contracts':contracts,'./local-request':local}).proxyProspecting;}
const id='a'.repeat(32);
const request=(suffix='',init={})=>new Request('http://127.0.0.1:3198/api/prospecting/search'+suffix,init);

test('search acceptance and paginated results preserve contracts and authenticated BFF path',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async(url,init)=>{
      assert.equal(init.headers.Authorization,'Bearer synthetic-only');assert.equal(init.redirect,'error');
      assert.equal(init.cache,'no-store');assert.ok(!('cookie' in init.headers));
      if(init.method==='POST') {
        assert.equal(url.pathname,'/v1/prospecting/search');
        return Response.json({id,status:'pending',found:0},{status:202});
      }
      assert.equal(url.pathname,`/v1/prospecting/search/${id}/results`);
      assert.equal(url.searchParams.get('page'),'2');
      return Response.json({items:[{id:21,alreadySaved:true}],total:25,page:2,pageSize:20});
    };
    const started=await proxy()(request('',{method:'POST',body:JSON.stringify({niche:'Synthetic',location:'Synthetic city',quantity:25})}),'start');
    assert.equal(started.status,202);assert.equal((await started.json()).status,'pending');
    const result=await proxy()(request(`/${id}/results?page=2&pageSize=20`),'results',id);
    assert.equal((await result.json()).items[0].alreadySaved,true);
  } finally {globalThis.fetch=original;}
});

test('results timeout is distinguishable from an empty completed search and never echoes secrets',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>{throw new DOMException('PRIVATE_TOKEN','TimeoutError');};
    const result=await proxy()(request(`/${id}/results`),'results',id);
    assert.equal(result.status,503);
    const body=await result.text();assert.match(body,/tempo limite/);assert.ok(!body.includes('PRIVATE_TOKEN'));
    globalThis.fetch=async()=>Response.json({items:[],total:0,page:1,pageSize:20});
    const empty=await proxy()(request(`/${id}/results`),'results',id);
    assert.equal(empty.status,200);assert.equal((await empty.json()).total,0);
  } finally {globalThis.fetch=original;}
});

test('invalid pagination, cross-origin import and body organization escalation fail before fetch',async()=>{
  const original=globalThis.fetch;
  try {
    globalThis.fetch=async()=>assert.fail('Untrusted requests must not reach backend');
    assert.equal((await proxy()(request(`/${id}/results?page=0`),'results',id)).status,422);
    assert.equal((await proxy()(request('',{method:'POST',headers:{Origin:'https://external.invalid'},body:'{}'}),'import')).status,403);
    assert.equal((await proxy()(request('',{method:'POST',body:JSON.stringify({searchId:id,resultIds:[1],organizationId:'other'})}),'import')).status,422);
    const expired=proxy(async()=>{throw new Error('SESSION_EXPIRED');});
    assert.equal((await expired(request(`/${id}`),'status',id)).status,401);
  } finally {globalThis.fetch=original;}
});
