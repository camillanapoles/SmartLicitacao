# STORY-SEO-027 discovery: `/contratos/orgao`

Data: 2026-05-06

## Escopo

Investigar os 44 hits reportados na story como URL raiz `/contratos/orgao` e decidir mitigacao proporcional sem alterar a rota dinamica `/contratos/orgao/[cnpj]`.

## GSC local export (`gsc-404-urls.txt`)

Comando executado:

```bash
node - <<'NODE'
const fs=require('fs');
const urls=JSON.parse(fs.readFileSync('gsc-404-urls.txt','utf8'));
const exact=urls.filter((u)=>new URL(u).pathname==='/contratos/orgao');
console.log(`total=${urls.length}`);
console.log(`exact_root=${exact.length}`);
NODE
```

Resultado:

- Total no export local: 1000 URLs.
- Path exato `/contratos/orgao`: 0 URLs.
- URLs contendo `/contratos/orgao`: 44 URLs.
- As 44 URLs tinham CNPJ no path e caracteres Unicode Private Use Area anexados pelo scrape do GSC. Apos remover os caracteres de icone do GSC, a lista unica e:

- https://smartlic.tech/contratos/orgao/00269444000127
- https://smartlic.tech/contratos/orgao/00394452000103
- https://smartlic.tech/contratos/orgao/01613428000172
- https://smartlic.tech/contratos/orgao/01613989000171
- https://smartlic.tech/contratos/orgao/01616420000160
- https://smartlic.tech/contratos/orgao/03507498000171
- https://smartlic.tech/contratos/orgao/04034583000122
- https://smartlic.tech/contratos/orgao/04104816000116
- https://smartlic.tech/contratos/orgao/04696490000163
- https://smartlic.tech/contratos/orgao/05191333000169
- https://smartlic.tech/contratos/orgao/05193123000100
- https://smartlic.tech/contratos/orgao/06553952000119
- https://smartlic.tech/contratos/orgao/08158669000118
- https://smartlic.tech/contratos/orgao/08160467000100
- https://smartlic.tech/contratos/orgao/08761124000525
- https://smartlic.tech/contratos/orgao/08924011000170
- https://smartlic.tech/contratos/orgao/09283185000163
- https://smartlic.tech/contratos/orgao/10662072000158
- https://smartlic.tech/contratos/orgao/13797188000192
- https://smartlic.tech/contratos/orgao/13915632000127
- https://smartlic.tech/contratos/orgao/13922596000129
- https://smartlic.tech/contratos/orgao/13927801000300
- https://smartlic.tech/contratos/orgao/13937149000143
- https://smartlic.tech/contratos/orgao/15180714000104
- https://smartlic.tech/contratos/orgao/18125146000129
- https://smartlic.tech/contratos/orgao/27165562000141
- https://smartlic.tech/contratos/orgao/28305936000140
- https://smartlic.tech/contratos/orgao/37382116000142
- https://smartlic.tech/contratos/orgao/39217831000155
- https://smartlic.tech/contratos/orgao/45138070000149
- https://smartlic.tech/contratos/orgao/45735552000186
- https://smartlic.tech/contratos/orgao/45774064000188
- https://smartlic.tech/contratos/orgao/57604530000166
- https://smartlic.tech/contratos/orgao/76331941000170
- https://smartlic.tech/contratos/orgao/76416965000121
- https://smartlic.tech/contratos/orgao/76966845000106
- https://smartlic.tech/contratos/orgao/78493343000122
- https://smartlic.tech/contratos/orgao/81478059000191
- https://smartlic.tech/contratos/orgao/81648859000103
- https://smartlic.tech/contratos/orgao/89363642000169
- https://smartlic.tech/contratos/orgao/89814693000160
- https://smartlic.tech/contratos/orgao/94704061000183
- https://smartlic.tech/contratos/orgao/96291141000180
- https://smartlic.tech/contratos/orgao/98671597000109

## Git history

Comandos executados:

```bash
git grep -n "contratos/orgao" -- frontend ':!frontend/app/api-types.generated.ts'
git log --all -S'/contratos/orgao' --format='%h %ad %s' --date=short -- frontend
git log --all -G'contratos/orgao' --format='%h %ad %s' --date=short -- frontend
git log --all -p --since='2026-02-01' -- frontend/app frontend/components | rg -n -B5 -A8 "/contratos/orgao"
```

Achados:

- O codigo atual contem links internos somente para `/contratos/orgao/{cnpj}`: templates usam CNPJ literal ou interpolado.
- `frontend/app/sitemap.ts` emite somente `${baseUrl}/contratos/orgao/${cnpj}` no shard 4.
- A rota foi introduzida em `64aa69746` (2026-04-08) como `/contratos/orgao/[cnpj]` e sitemap com `${cnpj}`.
- Nao foi encontrado template removido emitindo o literal exato `/contratos/orgao`.

## Sentry e GSC dashboards

- Sentry dashboard/API: bloqueado nesta worktree por ausencia de token/credencial acessivel na sessao.
- GSC Performance dashboard: bloqueado nesta sessao por ausencia de acesso interativo/autenticado ao Search Console.

## Conclusao

Origem do path exato `/contratos/orgao`: indeterminada. O export local nao confirma 44 URLs raiz; confirma 44 URLs dinamicas com CNPJ e artefatos de scrape ja documentados no brief GSC de 2026-04-27.

Mesmo assim, a mitigacao proporcional para a raiz orfa e defensiva e segura: retornar `410 Gone` apenas quando `pathname === "/contratos/orgao"`. A rota dinamica `/contratos/orgao/[cnpj]` permanece fora desse match exato.

## Decisao tecnica

Next.js 16 `notFound()` retorna 404, nao 410. Para preservar um status HTTP 410 sem criar conteudo nem redirecionar, a implementacao usa `frontend/middleware.ts` com match exato e `new NextResponse("Gone", { status: 410 })`.

Fallback documentado: se o ambiente ignorar middleware em algum deploy especifico, o comportamento volta ao 404 existente, que ainda e aceitavel para a story como fallback tecnico; a validacao local deve confirmar 410.
