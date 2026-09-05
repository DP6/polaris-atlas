# Spec — Domínio: Autenticação (auth)

**Versão:** 1.0
**Status:** Aprovada
**Fase:** 1 — Plataforma
**Última atualização:** 2026-08-24

> Domínio de plataforma (não é um dos 7 domínios de observabilidade da
> tabela do `CLAUDE.md`). Esta spec foi escrita retroativamente,
> documentando o domínio que já estava implementado — gap identificado
> e fechado em 2026-08-24 (ver `CHANGELOG.md`). Comportamento descrito
> aqui é o que já roda em dev/prod, não um plano futuro.

---

## Objetivo

Login via Google OAuth (Workspace), restrito a uma allowlist de domínios/
e-mails, com sessão stateless via JWT em cookie `httpOnly`. Todo outro
domínio do Atlas depende deste para saber quem é o usuário
(`core/auth.py::get_current_user`) e, combinado com `domains/admin`, se
ele é admin (`require_admin`) ou tem acesso a um projeto GCP específico
(`require_project_access`).

---

## Fonte de dados / integrações externas

- **Google OAuth2** (`accounts.google.com/o/oauth2/v2/auth`,
  `oauth2.googleapis.com/token`, `openidconnect.googleapis.com/v1/userinfo`)
  — via `authlib`, fluxo authorization code padrão, escopo
  `openid email profile`. Sem PKCE (client secret confidencial, backend
  server-side).
- **Secret Manager** (`core/secrets.py`) — `GOOGLE_OAUTH_CLIENT_ID_{DEV,PROD}`,
  `GOOGLE_OAUTH_CLIENT_SECRET_{DEV,PROD}`, `JWT_SECRET_{DEV,PROD}` (segredo
  de assinatura HS256, um por ambiente — nunca compartilhado entre dev/prod),
  `OAUTH_ALLOWLIST` (JSON `{"allowed_domains": [...], "allowed_emails": [...]}`,
  único para ambos os ambientes juntos ou por ambiente conforme o secret
  específico usado em cada projeto GCP).
- **Firestore** — não é lido/escrito diretamente por este domínio, mas
  `api/v1/auth.py::callback` chama `domains.admin.analytics_service.record_login`
  (fora do escopo desta spec, ver `docs/specs/admin.md`) e `me` chama
  `admin_service.is_admin` pra popular `UserInfo.is_admin` fresco.

---

## Endpoints da API

### GET /api/v1/auth/login
Gera um `state` aleatório (`secrets.token_urlsafe(32)`), grava em cookie
`oauth_state` (10 min de validade) e redireciona pro authorize endpoint
do Google com `prompt=select_account` (força o seletor de conta mesmo
com sessão Google já ativa no browser).

### GET /api/v1/auth/callback
**Parâmetros (query):** `code`, `state`.
**Cookie esperado:** `oauth_state` (setado por `/login`).

1. Compara `state` (query) com `oauth_state` (cookie) — diferente ou
   cookie ausente → `OAuthStateMismatchError` (400).
2. Troca `code` pelo token e busca `userinfo` no Google — falha de rede/
   OAuth → `OAuthExchangeError` (400).
3. `userinfo` sem `email` → `OAuthExchangeError` (400).
4. E-mail fora da allowlist (nem domínio, nem e-mail específico) →
   `OAuthEmailNotAllowedError` (403).
5. Emite JWT de sessão, grava em cookie `session` (12h), apaga o cookie
   `oauth_state`, registra o login (`analytics_service.record_login`).

**Response 200:**
```json
{ "user": { "email": "ana@dp6.com.br", "name": "Ana", "picture": "https://...", "is_admin": false } }
```

### GET /api/v1/auth/me
Requer sessão válida (`Depends(get_current_user)`). Devolve o `UserInfo`
do JWT com `is_admin` **recalculado fresco** via `admin_service.is_admin`
— o valor de `is_admin` que eventualmente estivesse no JWT nunca é usado
como fonte de verdade.

### POST /api/v1/auth/logout
Apaga o cookie `session` (mesmos atributos `secure`/`httponly`/`samesite`
do cookie original — sem isso o browser não reconhece como o mesmo
cookie e a deleção é ignorada). `204`, sem body.

---

## Regras de sessão e cookies

- Cookies (`oauth_state`, `session`): `httponly=True`, `secure=True`,
  `samesite="none"`, `path="/"`. `SameSite=None` é obrigatório porque
  frontend e backend são dois serviços Cloud Run com origens diferentes
  (cookie precisa trafegar em request cross-site); exige `Secure`, o que
  o Cloud Run garante (HTTPS sempre).
- JWT: algoritmo `HS256`, payload `{sub: email, name, picture, exp}`,
  validade fixa de 12h (`SESSION_COOKIE_MAX_AGE_SECONDS`), **sem refresh
  token nem renovação silenciosa** — expira, o usuário loga de novo.
- Sessão é **stateless**: `logout` só apaga o cookie local. Um JWT
  copiado/roubado continua válido até expirar naturalmente — não há
  revogação server-side (sem blocklist).
- Allowlist: e-mail é permitido se o domínio (`email.split('@')[-1]`,
  case-insensitive) está em `allowed_domains` OU o e-mail completo
  (case-insensitive) está em `allowed_emails`.

---

## Critérios de aceite

| ID | Comportamento | Testado em |
|---|---|---|
| AC-001 | `state` do callback divergente do cookie (ou cookie ausente) rejeita com `OAuthStateMismatchError` | `test_handle_callback_raises_on_state_mismatch`, `test_handle_callback_raises_on_missing_state_cookie` |
| AC-002 | E-mail fora da allowlist (nem domínio, nem e-mail específico) é rejeitado | `test_handle_callback_raises_when_email_not_allowed` |
| AC-003 | E-mail permitido por domínio OU por lista específica autentica com sucesso | `test_handle_callback_happy_path_allowed_by_domain`, `test_handle_callback_happy_path_allowed_by_email` |
| AC-004 | Falha na troca do code por token/userinfo (erro OAuth ou de rede) vira `OAuthExchangeError` | `test_handle_callback_wraps_exchange_failures` |
| AC-005 | Resposta do Google sem `email` é rejeitada | `test_handle_callback_raises_when_userinfo_missing_email` |
| AC-006 | JWT emitido decodifica de volta pro mesmo `UserInfo` (roundtrip) | `test_issue_and_decode_session_token_roundtrip` |
| AC-007 | Sessão ausente, malformada ou assinada com outro segredo é rejeitada com `InvalidSessionError` | `test_decode_session_token_raises_when_missing`, `test_decode_session_token_raises_when_garbage`, `test_decode_session_token_raises_when_signed_with_different_secret` |
| AC-008 | `build_redirect_uri` usa a primeira origem `https://` de `cors_origins_list`, com fallback pra primeira entrada se nenhuma for https | `test_build_redirect_uri_picks_first_https_origin`, `test_build_redirect_uri_falls_back_to_first_entry_without_https` |
| AC-009 | `/login` sempre força `select_account` no prompt do Google | `test_build_authorize_url_delegates_to_repository_and_forces_account_selector` |

---

## Estrutura de arquivos

```
apps/backend/src/atlas/
├── api/v1/
│   └── auth.py             # /login, /callback, /me, /logout
├── core/
│   ├── auth.py              # get_current_user, require_admin, require_project_access
│   └── secrets.py           # client id/secret, JWT secret, allowlist (Secret Manager)
├── domains/auth/
│   ├── __init__.py
│   ├── service.py            # orquestra o fluxo OAuth + JWT
│   ├── repository.py         # única camada que fala com as APIs do Google
│   └── schemas.py
└── tests/unit/auth/
    ├── test_service.py
    ├── test_repository.py
    └── test_schemas.py
```

---

## Casos de borda

| Cenário | Comportamento |
|---|---|
| `state` do callback não bate com o cookie `oauth_state` | `OAuthStateMismatchError` (400) — sinal de CSRF ou cookie expirado/perdido |
| Cookie `oauth_state` ausente no callback | Mesma resposta acima — tratado como o mesmo caso |
| `code` do Google já usado/expirado | `OAuthExchangeError` (400) |
| Google não devolve `email` no userinfo | `OAuthExchangeError` (400) |
| E-mail fora da allowlist | `OAuthEmailNotAllowedError` (403) |
| `userinfo.name` ausente | Usa o próprio e-mail como `name` (`userinfo.get('name') or email`) |
| Cookie `session` ausente/expirado em endpoint autenticado | `InvalidSessionError` → 401 (handler em `main.py`) |
| Sessão assinada com segredo de outro ambiente (dev vs prod) | `InvalidSessionError` — segredos nunca são compartilhados entre ambientes |

---

## Suposições

| ID | Suposição | Status |
|---|---|---|
| ASM-001 | Sessão dura 12h fixas, sem refresh/renovação silenciosa — usuário loga de novo ao expirar, mesmo no meio de uma tarefa longa | confirmada (`SESSION_COOKIE_MAX_AGE_SECONDS`, comportamento atual) |
| ASM-002 | Allowlist é lida do Secret Manager, não do Firestore — trocar quem pode logar exige atualizar o secret (`gcloud secrets versions add`), não uma tela de admin | confirmada |
| ASM-003 | `UserInfo.is_admin` no schema é só um placeholder de shape — a única fonte de verdade é `admin_service.is_admin` lido fresco do Firestore em cada request que precisa checar | confirmada, ver `core/auth.py::require_admin` |

## Perguntas em aberto

| ID | Pergunta | Status | Resposta |
|---|---|---|---|
| Q-001 | Vale um refresh silencioso (renovar o cookie a cada request bem-sucedido) pra evitar logout no meio de uma sessão de trabalho longa? | aberta | — |

---

## Fora do escopo desta spec

- MFA / segundo fator — delegado inteiramente ao Google (conta do
  Workspace do usuário já pode exigir 2FA lá).
- Login com provedores além do Google.
- Rate limiting de tentativas de login/callback.
- Revogação de sessão do lado servidor (blocklist de JWT) — sessão é
  stateless por design; se necessário no futuro, exigiria trocar pra
  sessão com estado (Firestore/Redis) ou reduzir bastante o TTL do JWT.
- Gestão de quem está na allowlist (isso é `docs/onboarding-cliente.md`
  + Secret Manager, não uma tela do Atlas).
