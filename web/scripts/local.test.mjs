import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
function load(file, stubs={}) {
  const container={exports:{}};
  const source=fs.readFileSync(path.resolve(import.meta.dirname,'../src',file),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('require','module','exports',code)(name => name in stubs ? stubs[name] : name==='server-only' ? {} : name.startsWith('@/') ? load(name.slice(2)+'.ts',stubs) : require(name),container,container.exports);
  return container.exports;
}
const mode=load('lib/runtime-mode.ts');

test('SDR niche and status reach the local backend without losing pagination or search',async()=>{
  const original=globalThis.fetch;
  const {proxyRead}=load('lib/api/proxy.ts',{
    './dashboard-timing':{dashboardFetch:(...args)=>globalThis.fetch(...args)},
    './local-request':load('lib/api/local-request.ts'),
  });
  const {prospectApi}=load('lib/api/client.ts');
  const niche="Clínica & Saúde '";
  try {
    globalThis.fetch=async url=>{
      const parsed=new URL(url,'http://127.0.0.1');
      assert.equal(parsed.searchParams.get('niche'),niche);
      assert.equal(parsed.searchParams.get('stage'),'Novo');
      assert.equal(parsed.searchParams.get('q'),'Árvore');
      assert.equal(parsed.searchParams.get('page'),'2');
      assert.equal(parsed.searchParams.get('pageSize'),'8');
      return Response.json({items:[],total:0});
    };
    assert.equal((await prospectApi.listLeads({niche,stage:'Novo',q:'Árvore',page:2,pageSize:8})).status,'ready');
    const params=new URLSearchParams({niche,stage:'Novo',q:'Árvore',page:'2',pageSize:'8'});
    assert.equal((await proxyRead(new Request(`http://127.0.0.1/api/leads?${params}`),'/v1/leads')).status,200);
    globalThis.fetch=async url=>{
      assert.equal(new URL(url).pathname,'/v1/lead-niches');
      return Response.json([niche]);
    };
    const response=await proxyRead(new Request('http://127.0.0.1/api/lead-niches'),'/v1/lead-niches');
    assert.deepEqual(await response.json(),[niche]);
  } finally {globalThis.fetch=original;}
});

test('local is the default; invalid, mixed and cloud modes fail closed',()=>{
  delete process.env.LOUNG_AUTH_MODE;
  assert.equal(mode.isLocalMode(),true);
  process.env.LOUNG_AUTH_MODE='saas';assert.equal(mode.isLocalMode(),false);
  process.env.LOUNG_AUTH_MODE='typo';assert.throws(mode.isLocalMode);
  process.env.LOUNG_AUTH_MODE='local';process.env.VERCEL='1';assert.throws(mode.isLocalMode);
  delete process.env.VERCEL;delete process.env.LOUNG_AUTH_MODE;
});

test('local proxy serves Dashboard without Supabase and denies remote origins',async()=>{
  delete process.env.LOUNG_AUTH_MODE;
  const {NextRequest}=require('next/server');
  const {proxy}=load('proxy.ts',{'@supabase/ssr':{createServerClient(){assert.fail('Supabase must not be called');}}});
  assert.equal((await proxy(new NextRequest('http://127.0.0.1/'))).status,200);
  assert.equal((await proxy(new NextRequest('http://127.0.0.1/',{headers:{'x-forwarded-for':'127.0.0.1'}}))).status,200);
  for(const headers of [{host:'public.example'},{origin:'https://evil.example'},{'sec-fetch-site':'cross-site'},{'x-forwarded-for':'192.168.1.2'}]) {
    assert.equal((await proxy(new NextRequest('http://127.0.0.1/',{headers}))).status,403);
  }
  for(const route of ['/login','/recuperar-senha','/configuracoes/equipe']) {
    const response=await proxy(new NextRequest('http://127.0.0.1'+route));
    assert.equal(new URL(response.headers.get('location')).pathname,'/');
  }
  assert.equal((await proxy(new NextRequest('http://127.0.0.1/api/team'))).status,404);
});

test('local BFF does not read cookies or create a Supabase client',async()=>{
  delete process.env.LOUNG_AUTH_MODE;
  const server=load('lib/auth/server.ts',{
    './config':{authConfig(){assert.fail('No Supabase config required');}},
    'next/headers':{cookies(){assert.fail('No cookies required');}},
    '@supabase/ssr':{createServerClient(){assert.fail('No Supabase client');}},
  });
  assert.deepEqual(await server.backendHeaders(),{});
  assert.deepEqual(await server.backendHeaders(true),{'Content-Type':'application/json'});
});

test('start scripts bind both frontend modes to loopback',()=>{
  const pkg=JSON.parse(fs.readFileSync(path.resolve(import.meta.dirname,'../package.json'),'utf8'));
  assert.match(pkg.scripts.dev,/--hostname 127\.0\.0\.1/);
  assert.match(pkg.scripts.start,/--hostname 127\.0\.0\.1/);
});

test('SDR BFF preserves safe Groq codes and timeout status without auth in local mode',async()=>{
  const original=globalThis.fetch;
  const proxy=load('lib/api/sdr-proxy.ts',{
    '@/lib/auth/server':{backendHeaders:async()=>({})},
    './local-request':load('lib/api/local-request.ts'),
    './sdr-contracts':load('lib/api/sdr-contracts.ts'),
  });
  const body={leadId:1,recipient:'auto',service:'auto',instruction:'',requestId:crypto.randomUUID()};
  try {
    for(const [status,code] of [[504,'GROQ_TIMEOUT'],[429,'GROQ_RATE_LIMITED'],[503,'GROQ_MODEL_UNAVAILABLE'],[503,'GROQ_TLS_FAILED']]) {
      globalThis.fetch=async(url,init)=>{
        assert.equal(new URL(url).pathname,'/v1/sdr/generate');
        assert.equal(init.headers.Authorization,undefined);
        return Response.json({detail:'Safe diagnostic'},{status,headers:{'x-loung-sdr-code':code}});
      };
      const response=await proxy.proxySdr(new Request('http://127.0.0.1/api/sdr/generate',{method:'POST',body:JSON.stringify(body)}),'generate');
      assert.equal(response.status,status);
      assert.deepEqual(await response.json(),{detail:'Safe diagnostic',code});
    }
    globalThis.fetch=async()=>Response.json({detail:'Safe diagnostic'},{status:502,headers:{'x-loung-sdr-code':'PRIVATE_KEY'}});
    const response=await proxy.proxySdr(new Request('http://127.0.0.1/api/sdr/generate',{method:'POST',body:JSON.stringify(body)}),'generate');
    assert.equal((await response.json()).code,undefined);
  } finally {globalThis.fetch=original;}
});

test('WhatsApp uses exactly the reviewed text, only as a manual URL',()=>{
  const {whatsappLink}=load('lib/sdr-whatsapp.ts');
  const text='Texto revisado\nPodemos conversar sobre gestão & contatos?';
  const url=new URL(whatsappLink('5511999991234',text));
  assert.equal(url.origin,'https://wa.me');
  assert.equal(url.pathname,'/5511999991234');
  assert.equal(url.searchParams.get('text'),text);
  assert.equal(whatsappLink(null,text),null);
  assert.equal(whatsappLink('5511999991234',''),null);
});
