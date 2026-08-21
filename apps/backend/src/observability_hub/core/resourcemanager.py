"""Client do Cloud Resource Manager — descobre quais projetos GCP a
service account de runtime consegue enxergar (`roles/browser` ou
qualquer role que implique `resourcemanager.projects.get`, ver
docs/onboarding-cliente.md), pro seletor de projeto no frontend listar
em vez do usuário digitar o `project_id` de cabeça.

A lib é síncrona, mesmo racional de core/bigquery.py::get_client — quem
chama roda em threadpool (endpoint `def`, não `async def`).
"""

import logging
from functools import lru_cache

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import resourcemanager_v3

logger = logging.getLogger(__name__)


@lru_cache
def get_client() -> resourcemanager_v3.ProjectsClient:
    return resourcemanager_v3.ProjectsClient()


def list_reachable_projects() -> list[dict]:
    """Projetos GCP ativos onde a SA de runtime tem visibilidade via
    Resource Manager. Fail-closed: qualquer erro (role `roles/browser`
    faltando num projeto ainda não onboardado com ela, API indisponível)
    retorna lista vazia em vez de quebrar o seletor — pior caso o
    usuário volta a digitar o `project_id` manualmente, mesmo fallback
    de antes desta função existir."""
    try:
        results = get_client().search_projects(query="state:ACTIVE")
        return [{"project_id": p.project_id, "display_name": p.display_name} for p in results]
    except GoogleAPICallError:
        logger.exception("Falha ao listar projetos via Cloud Resource Manager API")
        return []
