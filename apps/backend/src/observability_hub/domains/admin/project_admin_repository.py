"""Acesso a hub_projects/{project_id}/project_admins/{email} — subcoleção
do papel delegável "Admin de projeto" (ver docs/specs/admin.md, "Admin de
projeto"). Arquivo separado de repository.py (não misturado nele) porque
a chave de leitura mais comum é "todos os admins deste projeto" — uma
subcoleção por projeto, não um campo dentro do documento do usuário como
os outros três eixos de acesso (hub_users.allowed_projects).
"""

from datetime import UTC, datetime

from google.cloud import firestore


def _project_admins_collection(client: firestore.Client, project_id: str):
    return client.collection("hub_projects").document(project_id).collection("project_admins")


def get_project_admin(client: firestore.Client, project_id: str, email: str) -> dict | None:
    doc = _project_admins_collection(client, project_id).document(email).get()
    return doc.to_dict() if doc.exists else None


def list_project_admins(client: firestore.Client, project_id: str) -> list[dict]:
    docs = _project_admins_collection(client, project_id).order_by("email").stream()
    return [doc.to_dict() for doc in docs]


def upsert_project_admin(
    client: firestore.Client,
    project_id: str,
    email: str,
    datasets: list[str] | None,
    granted_by: str,
) -> dict:
    """created_at/granted_by só são definidos na primeira gravação —
    reconceder o papel a alguém que já era Admin de projeto não reatribui
    autoria original, mesmo padrão de upsert_user/upsert_project."""
    now = datetime.now(UTC)
    existing = get_project_admin(client, project_id, email)
    data = {
        "email": email,
        "datasets": datasets,
        "granted_by": existing["granted_by"] if existing else granted_by,
        "granted_at": existing["granted_at"] if existing else now,
        "updated_at": now,
    }
    _project_admins_collection(client, project_id).document(email).set(data)
    return data


def delete_project_admin(client: firestore.Client, project_id: str, email: str) -> None:
    _project_admins_collection(client, project_id).document(email).delete()
