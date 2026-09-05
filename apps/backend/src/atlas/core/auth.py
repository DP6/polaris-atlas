"""Dependências FastAPI de autenticação/autorização — aplicadas a nível
de router (via `dependencies=[Depends(...)]`) na maioria dos domínios.
Mora em core/ porque é transversal, mesmo racional de core/bigquery.py.

require_admin e require_project_access dependem de get_current_user
internamente — o FastAPI cacheia a resolução de dependency por request,
então usar as duas juntas (ex: um endpoint que declara
Depends(get_current_user) e o router já usa Depends(require_admin)) não
decodifica o JWT duas vezes.
"""

from fastapi import Cookie, Depends
from google.cloud import firestore

from atlas.core.exceptions import (
    AdminAccessRequiredError,
    ProjectAdminRequiredError,
    ProjectNotAuthorizedError,
)
from atlas.core.firestore import get_firestore_client
from atlas.domains.admin import service as admin_service
from atlas.domains.auth import service
from atlas.domains.auth.schemas import UserInfo


def get_current_user(
    session: str | None = Cookie(default=None, alias=service.SESSION_COOKIE_NAME),
) -> UserInfo:
    return service.decode_session_token(session)


def require_admin(
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    """Sessão válida não basta — precisa também de is_admin=True em
    hub_users/{email} (domains/admin). Leitura sempre fresca do
    Firestore, sem cache (ver domains/admin/service.py)."""
    if not admin_service.is_admin(client, user.email):
        raise AdminAccessRequiredError()
    return user


def require_project_access(
    project_id: str,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    """Aplicada no lugar de get_current_user em todo router que recebe
    project_id como path param — barra ANTES de qualquer chamada real ao
    BigQuery/Cloud Logging do projeto alvo, mesmo que a service account
    de runtime tenha IAM lá (ADR-006 é sobre a SA alcançar o projeto;
    isto aqui é sobre o USUÁRIO estar autorizado no Hub a usar esse
    acesso). Usuário sem doc em hub_users tem allowed_projects vazio,
    nega tudo por padrão (fail closed)."""
    if not admin_service.has_project_access(client, user.email, project_id):
        raise ProjectNotAuthorizedError(project_id)
    return user


def require_project_admin(
    project_id: str,
    dataset_id: str | None = None,
    user: UserInfo = Depends(get_current_user),
    client: firestore.Client = Depends(get_firestore_client),
) -> UserInfo:
    """Papel delegável "Admin de projeto" (ver docs/specs/admin.md) —
    diferente de require_admin (superadmin global) e de
    require_project_access (acesso comum de leitura): aplicada por
    endpoint, não por router inteiro, só nos endpoints de escrita de
    domains/metadata e do budget compartilhado (domains/budget).

    Superadmin sempre passa (mesmo bypass de require_admin). Senão,
    precisa de um doc em hub_projects/{project_id}/project_admins/{email}
    cujo `datasets` seja None (projeto inteiro) ou contenha dataset_id.
    dataset_id=None é usado por endpoints project-scoped (ex: budget de
    projeto inteiro) — só passa quem tem `datasets: null`, nunca um
    admin restrito a datasets específicos."""
    if admin_service.is_admin(client, user.email):
        return user
    if not admin_service.is_project_admin(client, user.email, project_id, dataset_id):
        raise ProjectAdminRequiredError(project_id)
    return user
