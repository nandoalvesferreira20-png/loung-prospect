import {test} from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import ts from 'typescript';
import {createRequire} from 'node:module';
const runtimeRequire=createRequire(import.meta.url);
const __dirname=import.meta.dirname;
process.env.LOUNG_AUTH_MODE = 'saas';
function load(file,stubs={}){
  const container={exports:{}};
  const source=fs.readFileSync(path.resolve(__dirname,'../src',file),'utf8');
  const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  new Function('require','module','exports',code)(name=>name in stubs?stubs[name]:name==='server-only'?{}:name.startsWith('@/')?load(name.slice(2)+'.ts'):runtimeRequire(name),container,container.exports);
  return container.exports;
}
const config=load('lib/auth/config.ts');
const errors=load('lib/auth/errors.ts',{'./config':config});
test('Dashboard timings preserve verified bearer and allow only fixed numeric upstream metrics',async()=>{
  const original=globalThis.fetch;
  let calls=0;
  const headers={'Cache-Control':'no-store'};
  const timing=load('lib/api/dashboard-timing.ts',{'server-only':{},'@/lib/auth/server':{backendHeaders:async()=>({Authorization:'Bearer synthetic'})}});
  try {
    globalThis.fetch=async(url,init)=>{
      calls++;assert.equal(init.headers.Authorization,'Bearer synthetic');assert.equal(init.cache,'no-store');
      return new Response('{}',{headers:{'Server-Timing':'jwt;dur=1.2, db_connect;dur=23.4, private;desc="SECRET", handler;dur=invalid'}});
    };
    await timing.dashboardFetch(new URL('http://127.0.0.1:8112/v1/session'),{cache:'no-store'},headers);
    assert.equal(calls,1);assert.match(headers['Server-Timing'],/api_db_connect;dur=23.4/);
    assert.ok(!headers['Server-Timing'].includes('SECRET'));assert.ok(!headers['Server-Timing'].includes('invalid'));
    const denied=load('lib/api/dashboard-timing.ts',{'server-only':{},'@/lib/auth/server':{backendHeaders:async()=>{throw new Error('SESSION_EXPIRED');}}});
    await assert.rejects(()=>denied.dashboardFetch(new URL('http://127.0.0.1:8112'),{},{}),/SESSION_EXPIRED/);
    assert.equal(calls,1);
  } finally {globalThis.fetch=original;}
});

test('SessionGate cancels cleanup requests and ignores late expiration',async()=>{
  const original=globalThis.fetch;
  const effects=[],redirects=[];
  let complete,signal;
  const react=runtimeRequire('react');
  const gate=load('components/session-provider.tsx',{
    react:{...react,useState:value=>[value,()=>{}],useEffect:effect=>effects.push(effect)},
    'next/navigation':{usePathname:()=>'/leads',useRouter:()=>({replace:path=>redirects.push(path)})},
    '@/lib/auth/browser':{},
  });
  try {
    globalThis.fetch=async(_,init)=>{signal=init.signal;return new Promise(resolve=>{complete=resolve;});};
    gate.SessionGate({children:null});
    const cleanup=effects[0]();
    cleanup();assert.equal(signal.aborted,true);
    complete(new Response('{}',{status:401}));
    await new Promise(resolve=>setImmediate(resolve));
    assert.deepEqual(redirects,[]);
  } finally {globalThis.fetch=original;}
});
test('public key aliases and malformed config fail before client creation',()=>{
  assert.deepEqual(config.resolveAuthConfig('https://example.invalid','public-test','old-test'),{url:'https://example.invalid',key:'public-test'});
  assert.equal(config.resolveAuthConfig('https://example.invalid','', 'old-test').key,'old-test');
  for(const values of [[undefined,undefined],['not-a-url','x'],['http://example.invalid','x'],['https://example.invalid','sb_secret_test'],['https://example.invalid/?token=x','x']])assert.throws(()=>config.resolveAuthConfig(...values),config.AuthConfigurationError);
});
test('safe distinct error messages never echo untrusted SDK text',()=>{
  assert.match(errors.authErrorMessage(new config.AuthConfigurationError(),'login'),/web\/\.env.local/);
  assert.match(errors.authErrorMessage({code:'invalid_credentials'},'login'),/E-mail ou senha/);
  assert.match(errors.authErrorMessage({code:'email_not_confirmed'},'login'),/Confirme/);
  assert.match(errors.authErrorMessage({code:'refresh_token_not_found'},'login'),/expirado/);
  assert.match(errors.authErrorMessage(new TypeError(),'login'),/conectar/);
  assert.ok(!errors.authErrorMessage({message:'PRIVATE_PAYLOAD'},'login').includes('PRIVATE_PAYLOAD'));
});
test('browser client is not constructed on missing configuration',()=>{
  let calls=0;
  const browser=load('lib/auth/browser.ts',{'./config':{authConfig(){throw new config.AuthConfigurationError();}},'@supabase/ssr':{createBrowserClient(){calls++;}}});
  assert.throws(()=>browser.browserAuth(),config.AuthConfigurationError);assert.equal(calls,0);
});
test('browser client reuses SDK cookie session singleton',()=>{
  let calls=0;const client={auth:{}};
  const browser=load('lib/auth/browser.ts',{'./config':{authConfig:()=>({url:'http://127.0.0.1:59199',key:'synthetic'})},'@supabase/ssr':{createBrowserClient(){calls++;return client;}}});
  assert.equal(browser.browserAuth(),client);assert.equal(browser.browserAuth(),client);assert.equal(calls,1);
});
test('SSR cookie adapter reads and writes SDK cookies, BFF forwards authenticated token only',async()=>{
  const saved=[];let options;
  const sdk={auth:{getUser:async()=>({data:{user:{id:'synthetic-user'}}}),getSession:async()=>({data:{session:{access_token:'synthetic-access'}}})}};
  const server=load('lib/auth/server.ts',{'server-only':{},'./config':{authConfig:()=>({url:'http://127.0.0.1:59199',key:'synthetic'})},'next/headers':{cookies:async()=>({getAll:()=>[{name:'session',value:'synthetic'}],set:(...v)=>saved.push(v)})},'@supabase/ssr':{createServerClient:(url,key,o)=>{options=o;return sdk;}}});
  await server.serverAuth();assert.equal(options.cookies.getAll()[0].name,'session');options.cookies.setAll([{name:'session',value:'rotated',options:{path:'/'}}]);assert.equal(saved[0][1],'rotated');
  const headers=await server.backendHeaders();assert.equal(headers.Authorization,'Bearer synthetic-access');
  sdk.auth.getUser=async()=>({data:{user:null},error:{}});await assert.rejects(server.backendHeaders(),/SESSION_EXPIRED/);
});
test('session BFF preserves safe failure codes, authorization and recovery',async()=>{
  const previousFetch=globalThis.fetch;const previousUrl=process.env.LOUNG_API_URL;
  process.env.LOUNG_API_URL='http://127.0.0.1:8000';
  const safe=load('lib/auth/access-errors.ts');
  const timing=load('lib/api/dashboard-timing.ts',{'server-only':{},'@/lib/auth/server':{backendHeaders:async()=>({Authorization:'Bearer synthetic-token'})}});
  const route=load('app/api/session/route.ts',{'@/lib/api/dashboard-timing':timing,'@/lib/auth/config':config,'@/lib/auth/access-errors':safe});
  let received;
  try{
    globalThis.fetch=async(url,init)=>{received=init.headers;return Response.json({code:'DB_DNS_FAILED',detail:'PRIVATE_DATABASE_DETAILS'},{status:503});};
    let response=await route.GET(new Request("http://127.0.0.1/api/session"));let body=await response.json();
    assert.equal(response.status,503);assert.equal(body.code,'DB_DNS_FAILED');assert.ok(!JSON.stringify(body).includes('PRIVATE_DATABASE_DETAILS'));assert.equal(received.Authorization,'Bearer synthetic-token');
    globalThis.fetch=async()=>Response.json({detail:'PRIVATE'},{status:403});
    response=await route.GET(new Request("http://127.0.0.1/api/session"));assert.match((await response.json()).detail,/membership/);
    globalThis.fetch=async()=>Response.json({detail:'PRIVATE'},{status:401});
    response=await route.GET(new Request("http://127.0.0.1/api/session"));assert.equal(response.status,401);assert.match((await response.json()).detail,/Sessão/);
    globalThis.fetch=async()=>{throw new TypeError('PRIVATE_NETWORK_DETAILS');};
    response=await route.GET(new Request("http://127.0.0.1/api/session"));assert.equal(response.status,503);assert.ok(!JSON.stringify(await response.json()).includes('PRIVATE_NETWORK_DETAILS'));
    globalThis.fetch=async()=>Response.json({displayName:'Synthetic',organization:'Synthetic'});
    response=await route.GET(new Request("http://127.0.0.1/api/session"));assert.equal(response.status,200);assert.equal((await response.json()).organization,'Synthetic');
    process.env.LOUNG_API_URL='https://other.invalid';
    globalThis.fetch=async()=>assert.fail('Must not forward credentials to other hosts');
    response=await route.GET(new Request("http://127.0.0.1/api/session"));assert.equal((await response.json()).code,'BFF_CONFIG_INVALID');
  }finally{globalThis.fetch=previousFetch;if(previousUrl===undefined)delete process.env.LOUNG_API_URL;else process.env.LOUNG_API_URL=previousUrl;}
});

test('proxy distinguishes Auth outage from expiration and preserves public login',async()=>{
  const {NextRequest,NextResponse}=runtimeRequire('next/server');
  for(const error of [{name:'AuthRetryableFetchError',status:0},{status:503},{status:429}]){
    const {proxy}=load('proxy.ts',{'@/lib/auth/config':{...config,authConfig:()=>({url:'http://127.0.0.1:59199',key:'synthetic'})},'@supabase/ssr':{createServerClient:()=>({auth:{getUser:async()=>({data:{user:null},error})}})}});
    const response=await proxy(new NextRequest('http://localhost/private'));
    assert.equal(response.status,503);
    assert.equal(response.headers.get('location'),null);
    assert.equal(response.headers.get('cache-control'),'no-store');
    assert.equal((await proxy(new NextRequest('http://localhost/login?expired=1'))).status,200);
  }
  assert.ok(NextResponse);
});

test('proxy failure diagnostics contain only safe fields and correlate with response',async()=>{
  const {NextRequest}=runtimeRequire('next/server');
  const previousWarn=console.warn;const logs=[];
  const {proxy}=load('proxy.ts',{'@/lib/auth/config':{...config,authConfig:()=>({url:'http://127.0.0.1:59199',key:'synthetic'})},'@supabase/ssr':{createServerClient:()=>({auth:{getUser:async()=>{throw {name:'PRIVATE_NAME',message:'PRIVATE_TOKEN',cookie:'PRIVATE_COOKIE'};}}})}});
  try{
    console.warn=value=>logs.push(value);
    const response=await proxy(new NextRequest('http://localhost/private'));
    const entry=JSON.parse(logs[0]);
    assert.deepEqual(Object.keys(entry).sort(),['component','stage','http_status','error_type','correlation_id','duration_ms'].sort());
    assert.equal(entry.error_type,'Error');assert.equal(entry.stage,'supabase_get_user');
    assert.equal(entry.correlation_id,response.headers.get('x-request-id'));
    assert.ok(entry.duration_ms>=0);assert.ok(!logs[0].includes('PRIVATE'));
    assert.ok(!JSON.stringify(await response.json()).includes('PRIVATE'));
  }finally{console.warn=previousWarn;}
});

test('real SDK password login cookies are readable by proxy and BFF; refresh rotates both cookie jars',async()=>{
  const {createBrowserClient,createServerClient}=runtimeRequire('@supabase/ssr');
  const {NextRequest}=runtimeRequire('next/server');
  const jar=new Map();const calls=[];
  const user={id:'synthetic-user',aud:'authenticated',role:'authenticated',email:'test@example.invalid'};
  let expired=false;let rejectRefresh=false;
  const session=()=>({access_token:expired?'synthetic-new-access':'synthetic-access',refresh_token:expired?'synthetic-new-refresh':'synthetic-refresh',token_type:'bearer',expires_in:expired?3600:-1,user});
  const fakeFetch=async(url)=>{
    const target=new URL(url);calls.push(target.pathname+target.search);
    if(rejectRefresh && target.searchParams.get('grant_type')==='refresh_token')return Response.json({code:'refresh_token_not_found',message:'Invalid Refresh Token'},{status:400});
    if(target.pathname.endsWith('/token'))return Response.json(session());
    if(target.pathname.endsWith('/user'))return Response.json(user);
    assert.fail('Unexpected Auth endpoint');
  };
  const authConfig=()=>({url:'http://127.0.0.1:59199',key:'synthetic'});
  const sdk={createServerClient:(url,key,options)=>createServerClient(url,key,{...options,global:{fetch:fakeFetch}})};
  const browser=createBrowserClient(authConfig().url,'synthetic',{isSingleton:false,global:{fetch:fakeFetch},auth:{autoRefreshToken:false,detectSessionInUrl:false},cookies:{getAll:()=>Array.from(jar,([name,value])=>({name,value})),setAll:values=>{for(const {name,value} of values)jar.set(name,value);}}});
  const login=await browser.auth.signInWithPassword({email:user.email,password:'synthetic-password'});
  assert.equal(login.error,null);assert.ok(jar.size);
  expired=true;
  const {proxy}=load('proxy.ts',{'@/lib/auth/config':{authConfig},'@supabase/ssr':sdk});
  const request=new NextRequest('http://localhost/',{headers:{cookie:Array.from(jar,([k,v])=>`${k}=${v}`).join('; ')}});
  const before=request.cookies.getAll();
  const response=await proxy(request);
  assert.equal(response.status,200);assert.equal(response.headers.get('location'),null);
  assert.ok(calls.includes('/auth/v1/token?grant_type=password'));
  assert.ok(calls.includes('/auth/v1/token?grant_type=refresh_token'));
  assert.notDeepEqual(request.cookies.getAll(),before);
  assert.ok(response.cookies.getAll().length);
  for(const cookie of response.cookies.getAll())assert.equal(request.cookies.get(cookie.name)?.value,cookie.value);
  const server=load('lib/auth/server.ts',{'server-only':{},'./config':{authConfig},'@supabase/ssr':sdk,'next/headers':{cookies:async()=>request.cookies}});
  assert.equal((await server.backendHeaders()).Authorization,'Bearer synthetic-new-access');
  const refreshCount=calls.filter(call=>call.includes('grant_type=refresh_token')).length;
  assert.equal((await proxy(request)).status,200);
  assert.equal(calls.filter(call=>call.includes('grant_type=refresh_token')).length,refreshCount);
  rejectRefresh=true;
  const staleRequest=new NextRequest('http://localhost/private',{headers:{cookie:before.map(({name,value})=>`${name}=${value}`).join('; ')}});
  const staleResponse=await proxy(staleRequest);
  assert.equal(staleResponse.status,307);
  assert.equal(staleResponse.headers.get('location'),'http://localhost/login?expired=1');
  assert.ok(staleResponse.cookies.getAll().some(cookie=>cookie.value===''));
  const noSession=await proxy(new NextRequest('http://localhost/private'));
  assert.equal(noSession.status,307);assert.equal(noSession.headers.get('location'),'http://localhost/login?expired=1');
  assert.equal((await proxy(new NextRequest(noSession.headers.get('location')))).status,200);
  assert.equal((await proxy(new NextRequest('http://localhost/api/session'))).status,401);
});

