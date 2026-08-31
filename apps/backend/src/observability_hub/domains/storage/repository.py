"""Consulta buckets/objetos do Cloud Storage via client REST
(google-cloud-storage). Mesma classe de erro que domains/lineage já
aprendeu da forma difícil (core/logging_client.py): o client de Storage
também é REST, não gRPC — um 403 aqui levanta
google.api_core.exceptions.Forbidden, não PermissionDenied.

`scan_read_object_events` (final do arquivo) é diferente das demais
funções — fala com Cloud Logging, não com o client de Storage, pra
checagem 6.2 do waste scanner (objeto sem leitura recente). Só o Job de
refresh a chama (modelo de cache incremental — o request path não
escaneia mais ao vivo, lê só de `get_read_object_keys_cached`). Payload é
o proto padrão `google.cloud.audit.AuditLog` (`resource.type="gcs_bucket"`),
**não** o formato legado `AuditData`/`jobCompletedEvent` que
domains/lineage e domains/access usam pra job do BigQuery — confirmado ao
vivo em dev (2026-08-18, leitura real de objeto + `gcloud logging read`),
payload diferente o bastante que não dá pra reaproveitar o parser deles.
"""

import json
import logging as std_logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

from google.api_core.exceptions import Forbidden
from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from observability_hub.core import event_cache
from observability_hub.core.config import settings
from observability_hub.core.exceptions import EventCacheNotReadyError, StorageAccessDeniedError
from observability_hub.core.logging_client import LOGGING_PAGE_SIZE, list_entries_with_retry
from observability_hub.core.storage_client import list_bucket_objects_cached

# Cache incremental: chave = (bucket, objeto), valor = ISO da leitura mais
# recente vista pra essa chave. Antes era um `set` (sem timestamp), o que
# impedia o merge incremental (não dá pra evictar chave "antiga" sem saber
# a data). Ver docs/specs/storage.md.
ReadObjectKeys = dict[tuple[str, str], str]

_OBJECT_READ_METHOD = "storage.objects.get"
# Janela do scanner 6.2 (objeto sem leitura recente) — ver
# docs/specs/storage.md seção 6.2. Único valor de referência: service.py
# e jobs/refresh_event_cache.py importam daqui em vez de duplicar.
LOOKBACK_DAYS = 90
_CACHE_KIND = "storage_read_keys"

logger = std_logging.getLogger(__name__)


def list_buckets(client: storage.Client, project_id: str) -> list[storage.Bucket]:
    """Lista os buckets do projeto. Levanta StorageAccessDeniedError se a SA
    não tiver roles/storage.bucketViewer (storage.objectViewer sozinha não
    cobre storage.buckets.list — ver docs/specs/storage.md seção 8)."""
    try:
        return list(client.list_buckets(project=project_id))
    except Forbidden as exc:
        raise StorageAccessDeniedError(project_id) from exc


def _list_objects_or_raise(
    client: storage.Client, project_id: str, bucket_name: str
) -> list[storage.Blob]:
    """list_bucket_objects_cached() com o mesmo tratamento de Forbidden de
    list_buckets() acima — sem isso, um projeto com storage.bucketViewer
    mas sem storage.objectViewer (as duas são necessárias juntas, ver
    docs/specs/storage.md seção 8) estouraria 500 cru aqui em vez do 403
    limpo que o domínio já sabe gerar."""
    try:
        return list_bucket_objects_cached(client, bucket_name)
    except Forbidden as exc:
        raise StorageAccessDeniedError(project_id) from exc


def get_bucket_size_and_count(
    client: storage.Client, project_id: str, bucket_name: str
) -> tuple[int, int]:
    """Soma size_bytes e conta objetos de um bucket (listagem cacheada 5min
    — ver core/storage_client.py). Não há campo agregado nativo no bucket,
    a única forma de saber o tamanho total é listar os objetos."""
    blobs = _list_objects_or_raise(client, project_id, bucket_name)
    total_size = sum(blob.size or 0 for blob in blobs)
    return total_size, len(blobs)


def get_eligible_waste_objects(
    client: storage.Client,
    project_id: str,
    bucket_name: str,
    min_days_unused: int,
    now: datetime,
) -> list[storage.Blob]:
    """Objetos STANDARD do bucket mais antigos que min_days_unused dias
    (customTime como campo primário, updated como fallback — mesmo
    raciocínio já usado no item de freshness, aqui só interno ao scanner).
    Reaproveita a listagem cacheada do catálogo (item 1), sem chamada
    nova. Objeto sem nenhum dos dois timestamps (não deveria acontecer na
    prática — updated é sempre setado pelo GCS) é ignorado, não conta como
    elegível nem quebra o cálculo dos demais."""
    blobs = _list_objects_or_raise(client, project_id, bucket_name)
    eligible = []
    for blob in blobs:
        if blob.storage_class != "STANDARD":
            continue
        reference_time = blob.custom_time or blob.updated
        if reference_time is None:
            continue
        age_days = (now - reference_time).days
        if age_days >= min_days_unused:
            eligible.append(blob)
    return eligible


def get_buckets_sizes_and_counts(
    client: storage.Client, project_id: str, bucket_names: list[str], max_workers: int = 8
) -> dict[str, tuple[int, int]]:
    """Mesma técnica de core/bigquery.py::get_tables_metadata — um bucket
    por thread, cada listagem já usa o cache TTL individual."""
    if not bucket_names:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(get_bucket_size_and_count, client, project_id, name): name
            for name in bucket_names
        }
        return {futures[future]: future.result() for future in as_completed(futures)}


def browse_bucket_objects(
    client: storage.Client,
    project_id: str,
    bucket_name: str,
    prefix: str | None,
    page_token: str | None,
    page_size: int = 100,
) -> tuple[list[storage.Blob], list[str], str | None]:
    """Uma página de objetos do bucket, com navegação por "pasta"
    simulada via delimiter="/" — GCS não tem pastas reais, mas prefixos
    terminados em "/" simulam (mesma convenção de qualquer console/CLI
    de GCS). Diferente de list_bucket_objects_cached (lista TUDO de uma
    vez, usado só pra agregação/scanner) — um bucket pode ter milhões de
    objetos, carregar tudo pra navegar a UI não escala. Retorna (blobs
    desta página, prefixos/"pastas" filhas, próximo page_token ou None
    se for a última página)."""
    try:
        iterator = client.list_blobs(
            bucket_name,
            prefix=prefix,
            delimiter="/",
            page_token=page_token,
            max_results=page_size,
        )
        page = next(iterator.pages, None)
        blobs = list(page) if page is not None else []
        prefixes = sorted(iterator.prefixes)
        return blobs, prefixes, iterator.next_page_token
    except Forbidden as exc:
        raise StorageAccessDeniedError(project_id) from exc


def _parse_resource_name(resource_name: str | None) -> tuple[str, str] | None:
    """Extrai (bucket, object) de um resourceName no formato
    "projects/_/buckets/{bucket}/objects/{object}" — split no primeiro
    "/objects/", nome de objeto pode ter mais barras (pseudo-diretórios),
    mantidas como parte do nome."""
    if not resource_name:
        return None
    marker = "/objects/"
    if marker not in resource_name:
        return None
    bucket_part, _, object_name = resource_name.partition(marker)
    bucket_name = bucket_part.removeprefix("projects/_/buckets/")
    if not bucket_name or not object_name:
        return None
    return bucket_name, object_name


def scan_read_object_events(
    logging_client: cloud_logging.Client,
    project_id: str,
    *,
    lookback_days: int = LOOKBACK_DAYS,
    since_receive_ts: datetime | None = None,
    page_pause: float = 0.0,
) -> ReadObjectKeys:
    """`{(bucket, objeto): ISO da leitura mais recente vista}` a partir dos
    audit logs de `storage.objects.get`.

    - `since_receive_ts` setado → delta incremental (`receiveTimestamp>"..."`).
    - senão → full scan (`timestamp>="hoje−lookback_days"`).

    Levanta LoggingAccessDeniedError (sem roles/logging.viewer) ou
    LoggingQuotaExceededError (429 persistente após o retry). Dict vazio
    (sem erro) é ambíguo — "nenhuma leitura na janela" ou "Data Access
    audit log DATA_READ do GCS desabilitado" (ver docs/onboarding-cliente.md);
    quem chama decide como comunicar (domains/storage/service.py)."""
    base = f'resource.type="gcs_bucket" protoPayload.methodName="{_OBJECT_READ_METHOD}" '
    if since_receive_ts is not None:
        filter_ = base + f'receiveTimestamp>"{since_receive_ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}"'
    else:
        cutoff = (datetime.now(UTC) - timedelta(days=lookback_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
        filter_ = base + f'timestamp>="{cutoff}"'

    entries = list_entries_with_retry(
        logging_client,
        resource_names=[f"projects/{project_id}"],
        filter_=filter_,
        page_size=LOGGING_PAGE_SIZE,
        project_id=project_id,
        page_pause=page_pause,
    )
    keys: ReadObjectKeys = {}
    for entry in entries:
        payload = entry.payload if isinstance(entry.payload, dict) else None
        if payload is None:
            continue
        key = _parse_resource_name(payload.get("resourceName"))
        if key is None:
            continue
        ts = entry.timestamp.isoformat() if entry.timestamp else ""
        if ts > keys.get(key, ""):
            keys[key] = ts
    return keys


# --- Cache de audit log (job periódico incremental) -----------------------------


def _serialize_read_object_keys(keys: ReadObjectKeys) -> bytes:
    return json.dumps([[b, o, ts] for (b, o), ts in sorted(keys.items())]).encode("utf-8")


def _deserialize_read_object_keys(data: bytes) -> ReadObjectKeys | None:
    """None => formato antigo (`[[b, o], ...]`, sem timestamp) ou corrompido
    — o job trata como "sem base incremental" e faz full scan."""
    raw = json.loads(data.decode("utf-8"))
    if not isinstance(raw, list):
        return None
    result: ReadObjectKeys = {}
    for row in raw:
        if not isinstance(row, list) or len(row) != 3:
            return None
        result[(row[0], row[1])] = row[2]
    return result


def _cache_blob_path(project_id: str) -> str:
    return f"{_CACHE_KIND}/{project_id}.json"


def read_read_object_keys_cache(
    storage_client: storage.Client, project_id: str
) -> ReadObjectKeys | None:
    """None em cache miss OU formato antigo (ver _deserialize_read_object_keys)."""
    data = event_cache.read_cache_bytes(
        storage_client, settings.event_cache_bucket_name, _cache_blob_path(project_id)
    )
    if data is None:
        return None
    return _deserialize_read_object_keys(data)


def write_read_object_keys_cache(
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    keys: ReadObjectKeys,
    *,
    window_start: datetime | None = None,
    last_scan_receive_ts: datetime | None = None,
    last_full_scan_at: datetime | None = None,
    mode: str | None = None,
) -> None:
    event_cache.write_cache_bytes(
        storage_client,
        settings.event_cache_bucket_name,
        _cache_blob_path(project_id),
        _serialize_read_object_keys(keys),
    )
    event_cache.set_cache_metadata(
        firestore_client,
        _CACHE_KIND,
        project_id,
        len(keys),
        window_start=window_start,
        last_scan_receive_ts=last_scan_receive_ts,
        last_full_scan_at=last_full_scan_at,
        mode=mode,
    )


def get_read_object_keys_cached(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
) -> set[tuple[str, str]]:
    """Só lê o cache pré-computado — o request path NÃO escaneia mais ao
    vivo (modelo incremental: o scan roda só no job diário ou no gatilho
    manual). Cache hit → conjunto de chaves. Cache miss → levanta
    EventCacheNotReadyError, que domains/storage/service.py degrada pra
    warning best-effort. O job diário só cobre `hub_projects`."""
    try:
        cached = read_read_object_keys_cache(storage_client, project_id)
    except Exception:
        logger.exception("Falha ao ler cache de storage read-keys para %s", project_id)
        cached = None

    if cached is not None:
        return set(cached.keys())

    raise EventCacheNotReadyError(project_id)
