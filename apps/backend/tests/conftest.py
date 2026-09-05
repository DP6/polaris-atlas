import os

# core.config.Settings exige ATLAS_ENVIRONMENT e
# ATLAS_RUNTIME_SA_EMAIL (sem default, topologia single-project
# — ver core/config.py). `settings = Settings()` roda no import do módulo,
# então isso precisa ser setado antes de qualquer import de
# atlas abaixo, inclusive nos arquivos de teste que importam
# antes deste conftest terminar de carregar.
os.environ.setdefault("ATLAS_ENVIRONMENT", "dev")
os.environ.setdefault(
    "ATLAS_RUNTIME_SA_EMAIL",
    "backend-dev-run@test-project.iam.gserviceaccount.com",
)
os.environ.setdefault("ATLAS_REGION", "us-central1")
os.environ.setdefault("ATLAS_EVENT_CACHE_BUCKET_NAME", "test-project-hub-cache-dev")

import pytest

from atlas.core import bigquery as bigquery_module
from atlas.core import logging_client as logging_client_module
from atlas.core import secrets as secrets_module


@pytest.fixture(autouse=True)
def _fast_logging_retry(monkeypatch):
    """list_entries_with_retry usa backoff exponencial real (deadline de
    30s) — nenhum teste unitário deve exercitar isso de verdade. Zera o
    deadline: o Retry faz 1 tentativa e, se ela falhar com erro
    retentável, levanta RetryError na hora (sem dormir). Os testes de
    tests/unit/core/test_logging_client.py que precisam validar a
    mecânica de retry restauram um deadline próprio + patcham time.sleep."""
    monkeypatch.setattr(logging_client_module, "_RETRY_TIMEOUT_SECONDS", 0.0)


@pytest.fixture(autouse=True)
def _clear_bigquery_table_cache():
    """core.bigquery.get_table_cached/get_tables_metadata cacheiam por
    table_ref (string), não por instância de client — em produção há um
    único client, mas em testes cada teste cria seu próprio MagicMock.
    Sem limpar entre testes, dois testes usando o mesmo table_ref (comum:
    "proj.RAW.ga4_events") vazam o resultado cacheado de um client mockado
    para o outro."""
    bigquery_module._table_cache.clear()
    yield
    bigquery_module._table_cache.clear()


@pytest.fixture(autouse=True)
def _clear_secrets_cache():
    """core.secrets.get_secret/_is_prod são @lru_cache — sem limpar entre
    testes, o valor (ou o mock) da primeira chamada vaza pros testes
    seguintes, mesmo trocando o monkeypatch."""
    secrets_module.get_secret.cache_clear()
    secrets_module._is_prod.cache_clear()
    yield
    secrets_module.get_secret.cache_clear()
    secrets_module._is_prod.cache_clear()
