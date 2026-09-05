"""Client compartilhado do Cloud Logging + leitura de audit log com retry.

`_use_grpc=False` é obrigatório: o audit log de job do BigQuery vem com
`protoPayload` duplamente aninhado em `Any` (AuditLog -> serviceData ->
AuditData, formato legado `google.cloud.bigquery.logging.v1.AuditData`).
O transporte gRPC padrão do client Python só decodifica `Any` pra dict
via `MessageToDict` usando o descriptor pool local do processo — e não
existe pacote Python publicado com o `.proto`/pb2 desse tipo específico
da BigQueryAuditData, então a decodificação sempre falha e
`entry.payload` volta como `google.protobuf.any_pb2.Any` cru (bytes),
nunca como dict, silenciosamente descartado pelos parsers de domínio. O
transporte REST não tem esse problema — o payload já chega pronto como
JSON/dict do servidor (mesmo formato que `gcloud logging read
--format=json` mostra), confirmado ao vivo contra observability-hub-dev
em 2026-08-14.

`list_entries_with_retry` centraliza o que os 4 domínios que leem audit
log (lineage, access, finops, storage) faziam copiado: materializar a
paginação numa lista e mapear `Forbidden` -> `LoggingAccessDeniedError`.
Adiciona retry exponencial em 429/503 e mapeia o 429 persistente pra
`LoggingQuotaExceededError` (HTTP 503 + Retry-After) em vez de deixar
`google.api_core.exceptions.TooManyRequests` subir como 500 ("Failed to
fetch" no browser).
"""

import json
import logging
import time
from datetime import UTC, datetime, timedelta
from functools import lru_cache

from google.api_core import exceptions as gapi_exceptions
from google.api_core import retry as retries
from google.cloud import logging as cloud_logging

from atlas.core.exceptions import LoggingAccessDeniedError, LoggingQuotaExceededError

logger = logging.getLogger(__name__)


def bigquery_job_events_filter(
    lookback_days: int | None = None, *, since_receive_ts: datetime | None = None
) -> str:
    """Filtro do Cloud Logging pros eventos de job completado do BigQuery
    (`jobservice.jobcompleted`, formato legado AuditData) — a MESMA fonte
    lida por domains/lineage, domains/access e domains/finops. Centralizado
    aqui pra jobs/refresh_event_cache.py poder fazer UM scan e alimentar os
    3 parsers (parse_job_events/parse_access_events/parse_scan_events).

    - `since_receive_ts` setado → delta incremental: `receiveTimestamp>"..."`
      (tudo que foi INGERIDO desde o último run OK, cobre logs atrasados).
    - senão → full scan: `timestamp>="hoje−lookback_days"` (default 30d)."""
    base = 'resource.type="bigquery_resource" protoPayload.methodName="jobservice.jobcompleted" '
    if since_receive_ts is not None:
        return base + f'receiveTimestamp>"{since_receive_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}"'
    cutoff = (datetime.now(UTC) - timedelta(days=lookback_days or 30)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return base + f'timestamp>="{cutoff}"'


# Cota `logging.googleapis.com/read_requests` (60/min por projeto, default)
# — um scan paginado de 30 dias de audit log estoura fácil sob
# concorrência, e dev+prod dividem o balde (topologia single-project). O
# Retry absorve o pico transitório (a cota é por minuto); o que sobreviver
# a _RETRY_TIMEOUT_SECONDS vira LoggingQuotaExceededError -> 503.
#
# O transporte REST (`_use_grpc=False`, obrigatório) não aceita `retry=`
# nativo e o 429 estoura no meio da paginação (`_get_next_page_response`),
# então o retry envolve o scan INTEIRO: um 429 na página 8 re-executa da
# página 1. Aceitável — é raro, tem backoff, e fora do request path (o job
# de cache diário) o custo não importa.
_RETRY_TIMEOUT_SECONDS = 30.0
_RETRY_INITIAL_BACKOFF = 1.0
_RETRY_MAX_BACKOFF = 10.0
_RETRY_MULTIPLIER = 2.0

# `entries.list` corta a página pelo tamanho da resposta (~10 MiB), não
# pela contagem pedida — audit log de job ≈ 2-4 KB, então na prática cada
# página traz ~2.5-4 mil entradas independente do valor aqui. 5000 pede o
# máximo útil; derruba um scan de 30 dias de ~50 mil eventos de ~50 páginas
# pra ~15.
LOGGING_PAGE_SIZE = 5000

# ResourceExhausted é subclasse de TooManyRequests no google-api-core
# instalado, então um predicado só cobre as duas formas do 429.
# ServiceUnavailable (503 do próprio Logging) também é transitório.
_RETRYABLE = retries.if_exception_type(
    gapi_exceptions.TooManyRequests,
    gapi_exceptions.ServiceUnavailable,
)


@lru_cache
def get_logging_client() -> cloud_logging.Client:
    return cloud_logging.Client(_use_grpc=False)


def _log_retry(exc: Exception) -> None:
    logger.warning(
        json.dumps(
            {
                "event": "cloud_logging_list_entries_retry",
                "error_type": type(exc).__name__,
                "error": str(exc)[:200],
            }
        )
    )


def list_entries_with_retry(
    client: cloud_logging.Client,
    *,
    resource_names: list[str],
    filter_: str,
    page_size: int,
    project_id: str,
    page_pause: float = 0.0,
) -> list[cloud_logging.LogEntry]:
    """`client.list_entries(...)` materializado numa lista, com retry
    exponencial em 429 (`TooManyRequests`/`ResourceExhausted`) e 503
    (`ServiceUnavailable`).

    `page_pause > 0` insere um `time.sleep(page_pause)` a cada `page_size`
    entradas consumidas (≈ fronteira de página) — rate-limit voluntário
    pro job de cache diário não estourar a cota `read_requests` num scan
    grande. O request path sempre passa `0.0` (latência importa lá).

    Mapeia:
    - `Forbidden` -> `LoggingAccessDeniedError` (sem retry — falta de IAM,
      permanente; quem chama sugere as roles).
    - 429 persistente (após `_RETRY_TIMEOUT_SECONDS`) ->
      `LoggingQuotaExceededError` (main.py: HTTP 503 + `Retry-After`).
    - Outro transitório persistente (`ServiceUnavailable`) propaga como
      está — outage sustentado do Logging é raro e honesto como 5xx cru.
    """
    retry_policy = retries.Retry(
        predicate=_RETRYABLE,
        initial=_RETRY_INITIAL_BACKOFF,
        maximum=_RETRY_MAX_BACKOFF,
        multiplier=_RETRY_MULTIPLIER,
        timeout=_RETRY_TIMEOUT_SECONDS,
        on_error=_log_retry,
    )

    def _scan() -> list[cloud_logging.LogEntry]:
        gen = client.list_entries(
            resource_names=resource_names, filter_=filter_, page_size=page_size
        )
        if page_pause <= 0:
            return list(gen)
        out: list[cloud_logging.LogEntry] = []
        for i, entry in enumerate(gen):
            if i and page_size and i % page_size == 0:
                time.sleep(page_pause)
            out.append(entry)
        return out

    try:
        return retry_policy(_scan)()
    except gapi_exceptions.Forbidden as exc:
        raise LoggingAccessDeniedError(project_id) from exc
    except gapi_exceptions.RetryError as exc:
        if isinstance(exc.cause, gapi_exceptions.TooManyRequests):
            raise LoggingQuotaExceededError(project_id) from exc
        raise
    except gapi_exceptions.TooManyRequests as exc:
        # Defensivo: um timeout curtíssimo (testes) pode levantar o 429
        # direto em vez de embrulhar num RetryError.
        raise LoggingQuotaExceededError(project_id) from exc
