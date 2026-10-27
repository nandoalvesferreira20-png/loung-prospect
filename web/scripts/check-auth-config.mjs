// Safe diagnostics: print only variable presence and the selected public key NAME.
import nextEnv from '@next/env';
import {existsSync} from 'node:fs';
import path from 'node:path';
const project=path.resolve(import.meta.dirname,'..');
const {loadEnvConfig}=nextEnv;
loadEnvConfig(project,process.env.NODE_ENV!=='production',{info(){},error(){}});
const present=name=>!!process.env[name]?.trim();
console.log('web/.env.local: '+(existsSync(path.join(project,'.env.local'))?'present':'absent'));
for(const key of ['NEXT_PUBLIC_SUPABASE_URL','NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY','NEXT_PUBLIC_SUPABASE_ANON_KEY'])console.log(key+': '+(present(key)?'present':'absent'));
console.log('Selected public key variable: '+(present('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')?'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY':present('NEXT_PUBLIC_SUPABASE_ANON_KEY')?'NEXT_PUBLIC_SUPABASE_ANON_KEY':'none'));
if(!present('NEXT_PUBLIC_SUPABASE_URL')||(!present('NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY')&&!present('NEXT_PUBLIC_SUPABASE_ANON_KEY')))process.exitCode=1;
