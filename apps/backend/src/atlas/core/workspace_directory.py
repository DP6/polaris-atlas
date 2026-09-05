"""Cliente do Admin SDK Directory API — lê membros de grupos reais do
Google Workspace via domain-wide delegation, sem chave de service
account. A SA de runtime assina o JWT de delegação usando sua própria
identidade (google.auth.iam.Signer, que chama a IAM Credentials API —
signBlob — em vez de precisar de uma chave privada local), depois
impersona settings.workspace_impersonate_email pra ler o grupo. Ver
docs/specs/admin.md, "Grupos (hub_groups, v1.4)".

Pré-requisitos, nenhum gerenciado por este módulo:
- Admin SDK API habilitada no projeto.
- roles/iam.serviceAccountTokenCreator da SA de runtime sobre si mesma
  (self-binding) — permite assinar o JWT de delegação.
- Domain-wide delegation autorizada no Admin Console do Workspace pro
  Client ID da SA de runtime, com os escopos abaixo (só leitura) — isso
  só um Super Admin do Workspace faz, pedido registrado em
  docs/onboarding-cliente.md.

Fail-closed por design: qualquer falha (delegação não configurada,
Workspace indisponível, escopo faltando, settings.workspace_impersonate_
email não setado) retorna lista vazia e loga o erro, nunca propaga
exceção — get_group_members nunca deve derrubar um endpoint só porque o
Workspace está fora do ar ou a integração ainda não foi ligada; o pior
caso é o grupo ficar temporariamente só com manual_members (ver
domains/admin), nunca conceder acesso a mais gente do que devia.
"""

import logging
import threading
import time

import google.auth
from google.auth.iam import Signer
from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2 import service_account

from atlas.core.config import settings

logger = logging.getLogger(__name__)

_TOKEN_URI = "https://oauth2.googleapis.com/token"
_DIRECTORY_MEMBERS_URL_TEMPLATE = (
    "https://admin.googleapis.com/admin/directory/v1/groups/{group_email}/members"
)
_DIRECTORY_GROUPS_URL = "https://admin.googleapis.com/admin/directory/v1/groups"
_DIRECTORY_SCOPES = [
    "https://www.googleapis.com/auth/admin.directory.group.readonly",
    "https://www.googleapis.com/auth/admin.directory.group.member.readonly",
]

_CACHE_TTL_SECONDS = 300
# Mesmo padrão de domains/pii/service.py::_scan_cache — dict em memória
# por processo, protegido por lock, TTL curto. Aqui o motivo é diferente
# (não é custo de query, é latência + cota de uma API externa que roda
# no caminho de has_project_access, chamada em quase todo endpoint).
_members_cache: dict[str, tuple[float, list[str]]] = {}
_members_cache_lock = threading.Lock()
# Cache separado pra list_domain_groups — chave única (o domínio), não
# por group_id como o de membros.
_domain_groups_cache: dict[str, tuple[float, list[dict]]] = {}
_domain_groups_cache_lock = threading.Lock()


def _cache_get(group_email: str) -> list[str] | None:
    now = time.monotonic()
    with _members_cache_lock:
        cached = _members_cache.get(group_email)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]
    return None


def _cache_set(group_email: str, members: list[str]) -> None:
    with _members_cache_lock:
        _members_cache[group_email] = (time.monotonic(), members)


def _build_delegated_credentials() -> service_account.Credentials | None:
    """Credenciais impersonando settings.workspace_impersonate_email,
    assinadas via IAM (sem chave local). None se a integração não
    estiver configurada."""
    if not settings.workspace_impersonate_email:
        return None

    adc_credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/iam"])
    request = Request()
    signer = Signer(request, adc_credentials, settings.runtime_sa_email)

    return service_account.Credentials(
        signer=signer,
        service_account_email=settings.runtime_sa_email,
        token_uri=_TOKEN_URI,
        scopes=_DIRECTORY_SCOPES,
        subject=settings.workspace_impersonate_email,
    )


def get_group_members(group_email: str) -> list[str]:
    """E-mails dos membros do grupo do Workspace, normalizados pra
    lowercase, com cache de 5min. Lista vazia se a integração não
    estiver configurada ou qualquer chamada falhar — nunca propaga
    exceção (ver docstring do módulo)."""
    cached = _cache_get(group_email)
    if cached is not None:
        return cached

    members: list[str] = []
    try:
        credentials = _build_delegated_credentials()
        if credentials is None:
            return []

        session = AuthorizedSession(credentials)
        page_token: str | None = None
        while True:
            params = {"maxResults": 200}
            if page_token:
                params["pageToken"] = page_token
            response = session.get(
                _DIRECTORY_MEMBERS_URL_TEMPLATE.format(group_email=group_email),
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            members.extend(
                m["email"].strip().lower() for m in data.get("members", []) if m.get("email")
            )
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception:
        logger.exception("Falha ao ler membros do grupo %s no Workspace Directory API", group_email)
        return []

    _cache_set(group_email, members)
    return members


def list_domain_groups() -> list[dict]:
    """Grupos do domínio do Workspace (o mesmo domínio de
    settings.workspace_impersonate_email), pra popular o seletor de
    "criar grupo" na UI em vez do admin ter que saber o e-mail exato de
    cor. Cada item: {"email": str, "name": str | None}. Exclui grupos
    com directMembersCount <= 1 (grupos pessoais de 1 funcionário, não
    grupos de time/acesso — comuns em domínios reais). Lista vazia nas
    mesmas condições de get_group_members (integração não configurada,
    Workspace fora do ar, escopo faltando) — nunca propaga exceção."""
    now = time.monotonic()
    with _domain_groups_cache_lock:
        cached = _domain_groups_cache.get("groups")
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    if not settings.workspace_impersonate_email or "@" not in settings.workspace_impersonate_email:
        return []
    domain = settings.workspace_impersonate_email.rsplit("@", 1)[-1]

    groups: list[dict] = []
    try:
        credentials = _build_delegated_credentials()
        if credentials is None:
            return []

        session = AuthorizedSession(credentials)
        page_token: str | None = None
        while True:
            params = {"domain": domain, "maxResults": 200}
            if page_token:
                params["pageToken"] = page_token
            response = session.get(_DIRECTORY_GROUPS_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            groups.extend(
                {"email": g["email"].strip().lower(), "name": g.get("name")}
                for g in data.get("groups", [])
                # directMembersCount <= 1 é quase sempre grupo pessoal
                # auto-criado por funcionário (comum em domínios reais),
                # não um grupo de time/acesso — não faz sentido oferecer
                # no seletor de "criar grupo".
                if g.get("email") and int(g.get("directMembersCount", 0)) > 1
            )
            page_token = data.get("nextPageToken")
            if not page_token:
                break
    except Exception:
        logger.exception("Falha ao listar grupos do domínio %s no Workspace Directory API", domain)
        return []

    with _domain_groups_cache_lock:
        _domain_groups_cache["groups"] = (time.monotonic(), groups)
    return groups
