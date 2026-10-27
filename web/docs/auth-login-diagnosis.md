# Diagnóstico de login — 20/10/2026

A falha encontrada no workspace acontece antes da chamada ao Supabase: `web/.env.local` estava ausente e o `.env` da raiz continha NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_ANON_KEY. O projeto Next é `web`; seu carregador não busca o `.env` do diretório pai. Além disso, os clientes só liam NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY. O carregador @next/env confirmou as três variáveis públicas ausentes antes da correção.

O formulário possui onSubmit, preventDefault, proteção contra submissão antes da hidratação e chama signInWithPassword. O Button renderiza um button real; foi acrescentado type=submit explícito. O erro vinha de browserAuth antes da chamada HTTP e era escondido pelo catch genérico que atribuía toda falha a credenciais/convite. GET /login?expired=1 retornar 200 é normal: é uma página pública. A chamada Auth é feita pelo navegador diretamente ao Supabase, portanto não aparece como POST no terminal Next.

Correções:

- Criado web/.env.local antes inexistente com somente a URL e a chave pública já configuradas na raiz, sem copiar DSN, senhas ou chaves administrativas. O arquivo é ignorado pelo Git. O `.env` existente não foi alterado.
- Um resolvedor comum valida configuração e aceita PUBLISHABLE_KEY ou ANON_KEY, com preferência pela primeira. Browser, SSR e proxy usam o mesmo resolvedor, mantendo referências estáticas NEXT_PUBLIC necessárias ao bundle Next.
- Mensagens distintas para configuração ausente/inválida, credenciais inválidas, e-mail não confirmado, sessão/link expirado, indisponibilidade de rede e limite de tentativas. Mensagens brutas do SDK não são exibidas nem logadas. Resposta Auth legada sem code também reconhece a mensagem exata conhecida de credenciais inválidas.
- /api/session distingue 401 (sessão), 403 (login realizado, mas sem membership), falha Auth e falha backend. Falta de configuração em rota protegida retorna 503, sem desabilitar proteção. A membership continua sendo verificada no backend, não é inferida do erro de senha.
- Fluxo SDK SSR de getAll/setAll e encaminhamento de Bearer foram preservados. Cookies de refresh continuam propagados pelo proxy, inclusive no redirecionamento de sessão inválida. Cache-Control no-store evita cache de respostas autenticadas.

Validação executada:

- `node web/scripts/auth.test.mjs`: cinco testes aprovados (configuração, mensagens seguras, cliente não construído quando ausente, singleton browser e cookies SSR/BFF).
- Navegador Edge em cópia isolada dos componentes: configuração ausente → zero chamadas Auth e mensagem específica; configuração sintética usando ANON_KEY → um POST Auth interceptado e mensagem de credenciais inválidas, sem criar sessão. Não houve tráfego ao projeto real.
- Lint e TypeScript aprovados. O servidor do usuário na porta 3000 foi preservado; somente a fixture isolada em 3199 foi iniciada/encerrada nesta investigação.
- Nenhum arquivo backend, SQL, RLS, usuário ou dado foi alterado nesta correção. SHA-256 do SQLite permanece 7c36ef1d20e6f4859937111f43baa8964dd62b9bd7adaeaafffeb00b66adbd39.

Para validar localmente:

```powershell
node web/scripts/check-auth-config.mjs
cd web
npm.cmd run dev
```

Primeiro encerre/reinicie o seu processo Next existente no próprio terminal, para carregar a configuração nova. O diagnóstico imprime apenas presença das variáveis e o nome da chave selecionada, nunca seus valores. Se usa npm start, refaça `npm.cmd run build` com a configuração correta antes de iniciar; NEXT_PUBLIC é incorporado no build e mudar o ambiente apenas no start não atualiza o bundle.

No navegador, abra /login e filtre Network por `auth/v1/token`. Submeter credenciais deve produzir POST com grant_type=password ao projeto configurado. Não compartilhe payloads, headers, cookies ou respostas com tokens. Se vier invalid_credentials, o pedido chegou ao Auth: conferir as credenciais e a configuração de acesso. Se o Auth retornar sucesso mas /api/session retornar 403, solicitar ao administrador o provisionamento da membership já previsto na Fase 3.1; não é falha de senha. Se 401, verificar sessão/validação do token; se 503, verificar o serviço apontado pela mensagem.

Não foi tentado login com credenciais reais: validade da senha, confirmação de e-mail e membership do usuário real permanecem a verificar pelo usuário. Não foram executadas migrations ou alterações de contas.

Referências oficiais: [Next.js: variáveis de ambiente](https://nextjs.org/docs/app/guides/environment-variables), [Supabase: signInWithPassword](https://supabase.com/docs/reference/javascript/auth-signinwithpassword), [sessões e cookies](https://supabase.com/docs/guides/auth/sessions).
