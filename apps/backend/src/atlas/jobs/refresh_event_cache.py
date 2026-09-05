"""Entrypoint do Cloud Run Job de refresh do cache de audit log
(lineage + access + finops + storage) — roda 1x/dia (D-1) via Cloud
Scheduler (infra/terraform/modules/cloud-run-job) ou sob demanda via o
gatilho manual de admin (domains/admin::trigger_event_cache_refresh).
Mesma imagem Docker do backend, comando/entrypoint diferente (ver módulo
Terraform cloud-run-job) — `python -m atlas.jobs.refresh_event_cache`.

Não é um domínio — orquestra lineage, access, finops, storage e admin
(fonte da lista de projetos), mesma posição arquitetural de main.py.

**Modelo incremental** (ver docs/specs/lineage.md): cada run lê só o
DELTA do Cloud Logging — o que foi ingerido desde o último run OK, por
`receiveTimestamp` (não uma janela fixa de N dias, pra capturar logs
atrasados) — faz merge com o blob existente (dedup por `job_id`) e
evicta os eventos fora da janela rolante (31d pros domínios de job, 90d
pra storage). O full scan da janela inteira só roda quando: não há base
incremental (primeira execução do projeto, metadado sem anchor, ou blob
sumido pela lifecycle do bucket) OU `settings.cache_force_full` (toggle
"forçar completo" do gatilho de admin).

lineage, access e finops leem a MESMA fonte de audit log
(`jobservice.jobcompleted`) — o Job faz **um único scan** do Cloud
Logging e alimenta os 3 parsers (`parse_job_events`/`parse_access_events`/
`parse_scan_events`), em vez de 3 scans idênticos que triplicavam a
leitura da cota `read_requests` do projeto. O refresh de storage é
best-effort e isolado (filtro `storage.objects.get`, Data Access audit
logs do GCS podem não estar habilitados — docs/specs/storage.md 6.2).
"""

import json
import logging as std_logging
from datetime import UTC, datetime, timedelta
from types import ModuleType

from google.api_core.exceptions import GoogleAPICallError
from google.cloud import firestore, storage
from google.cloud import logging as cloud_logging

from atlas.core import event_cache
from atlas.core.config import settings
from atlas.core.exceptions import LoggingAccessDeniedError, LoggingQuotaExceededError
from atlas.core.firestore import get_firestore_client
from atlas.core.logging_client import (
    LOGGING_PAGE_SIZE,
    bigquery_job_events_filter,
    get_logging_client,
    list_entries_with_retry,
)
from atlas.core.storage_client import get_storage_client
from atlas.domains.access import repository as access_repository
from atlas.domains.admin import repository as admin_repository
from atlas.domains.finops import repository as finops_repository
from atlas.domains.lineage import repository as lineage_repository
from atlas.domains.storage import repository as storage_repository

logger = std_logging.getLogger("atlas.jobs.refresh_event_cache")

# Pausa entre páginas do scan de audit log — rate-limit voluntário pro job
# (que roda fora do request path) não estourar a cota read_requests do
# projeto num scan grande. ~1 fetch a cada 0.4s -> ~150/min, folga sob os
# 200/min. O request path nunca usa pausa.
_SCAN_PAGE_PAUSE_SECONDS = 0.4

# Janela rolante do cache dos domínios de job (evicção por timestamp do
# evento). 31 dias cobre o mês corrente inteiro pro budget de finops
# (docs/specs/finops-budget.md) com folga de 1 dia.
_JOB_WINDOW_DAYS = 31
# Janela rolante do cache de storage (docs/specs/storage.md 6.2).
_STORAGE_WINDOW_DAYS = storage_repository.LOOKBACK_DAYS

# `_CACHE_KIND` do metadado Firestore de cada domínio que lê
# `jobservice.jobcompleted` — casam com domains/{lineage,access,finops}/
# repository.py. Hardcoded aqui (não importado dos repos) pelo mesmo
# racional de isolamento de domínio de domains/admin/service.py.
_STORAGE_CACHE_KIND = "storage_read_keys"

# (cache_kind, chave em `counts`, módulo do domínio, nome do parser, nome
# do leitor de cache, nome do gravador de cache). Os 3 domínios de job
# compartilham a assinatura de read_*/write_* e os eventos têm `.job_id` e
# `.timestamp` — dá pra tratar genericamente. Guardamos os NOMES (resolve
# via getattr no uso) e não as funções, pra o monkeypatch dos testes valer.
_JobKindSpec = tuple[str, str, ModuleType, str, str, str]
_JOB_KIND_SPECS: tuple[_JobKindSpec, ...] = (
    (
        "lineage",
        "job_events",
        lineage_repository,
        "parse_job_events",
        "read_job_events_cache",
        "write_job_events_cache",
    ),
    (
        "access",
        "access_events",
        access_repository,
        "parse_access_events",
        "read_access_events_cache",
        "write_access_events_cache",
    ),
    (
        "finops_scan_events",
        "scan_events",
        finops_repository,
        "parse_scan_events",
        "read_scan_events_cache",
        "write_scan_events_cache",
    ),
)


def _known_projects(firestore_client: firestore.Client) -> list[str]:
    """Projetos registrados no ADM (`hub_projects`) — a única fonte. Um
    projeto acessível só por wildcard `allowed_projects=["*"]` precisa ser
    cadastrado explicitamente pra entrar no ciclo do cache (ver
    docs/specs/lineage.md, ASM-003 invalidada)."""
    return sorted(p["project_id"] for p in admin_repository.list_projects(firestore_client))


def _job_scan_anchor(firestore_client: firestore.Client, project_id: str) -> datetime | None:
    """Menor `last_scan_receive_ts` entre os 3 kinds de job — o delta
    incremental parte daí pra não perder evento de nenhum kind. None se
    QUALQUER kind não tiver anchor (força full scan)."""
    anchors: list[datetime] = []
    for kind, *_rest in _JOB_KIND_SPECS:
        meta = event_cache.get_cache_metadata(firestore_client, kind, project_id)
        anchor = meta.get("last_scan_receive_ts") if meta else None
        if anchor is None:
            return None
        anchors.append(anchor)
    return min(anchors)


def _refresh_job_caches(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    *,
    force_full: bool,
) -> dict[str, object]:
    """Um scan de `jobservice.jobcompleted` -> merge/evict/grava os 3
    caches de job. Retorna as contagens pro registro de execução."""
    existing_by_kind: dict[str, list] = {}
    anchor: datetime | None = None
    if not force_full:
        anchor = _job_scan_anchor(firestore_client, project_id)
        if anchor is not None:
            for kind, _count_key, module, _parse_name, read_name, _write_name in _JOB_KIND_SPECS:
                cached = getattr(module, read_name)(storage_client, firestore_client, project_id)
                if cached is None:
                    # Blob sumido (lifecycle do bucket) apesar do metadado —
                    # sem base pra merge, cai em full.
                    anchor = None
                    existing_by_kind.clear()
                    break
                existing_by_kind[kind] = cached[0]

    mode = "incremental" if anchor is not None else "full"

    # Marcado ANTES do scan pra virar o próximo anchor sem perder eventos
    # ingeridos durante o scan (serão relidos no próximo delta — dedup
    # por job_id absorve a sobreposição).
    now_receive = datetime.now(UTC)
    cutoff = now_receive - timedelta(days=_JOB_WINDOW_DAYS)

    if mode == "incremental":
        filter_ = bigquery_job_events_filter(since_receive_ts=anchor)
    else:
        filter_ = bigquery_job_events_filter(_JOB_WINDOW_DAYS)

    raw_entries = list_entries_with_retry(
        logging_client,
        resource_names=[f"projects/{project_id}"],
        filter_=filter_,
        page_size=LOGGING_PAGE_SIZE,
        project_id=project_id,
        page_pause=_SCAN_PAGE_PAUSE_SECONDS,
    )

    counts: dict[str, object] = {"mode": mode, "raw_entries": len(raw_entries)}
    evicted_total = 0
    for kind, count_key, module, parse_name, _read_name, write_name in _JOB_KIND_SPECS:
        parsed = getattr(module, parse_name)(raw_entries)
        if mode == "incremental":
            merged = event_cache.merge_dedup(
                existing_by_kind.get(kind, []), parsed, key=lambda e: e.job_id
            )
        else:
            merged = parsed
        kept = [e for e in merged if e.timestamp is not None and e.timestamp >= cutoff]
        evicted_total += len(merged) - len(kept)
        getattr(module, write_name)(
            storage_client,
            firestore_client,
            project_id,
            kept,
            window_start=cutoff,
            last_scan_receive_ts=now_receive,
            last_full_scan_at=now_receive if mode == "full" else None,
            mode=mode,
        )
        counts[count_key] = len(kept)
    counts["evicted"] = evicted_total
    return counts


def _refresh_storage_read_keys(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    *,
    force_full: bool,
) -> int:
    """Best-effort, isolado do try/except principal de _refresh_project:
    Data Access audit logs (DATA_READ) do GCS podem não estar habilitados
    no projeto (ver docs/specs/storage.md seção 6.2), o que não deveria
    impedir o refresh de lineage/access do mesmo projeto. Retorna 0 nesses
    casos (mesmo efeito de cache vazio já tratado com grace pelo
    domains/storage/service.py). Incremental pela mesma regra dos domínios
    de job — full se `force_full`, sem blob, ou sem anchor no metadado."""
    now_receive = datetime.now(UTC)
    window_start = now_receive - timedelta(days=_STORAGE_WINDOW_DAYS)
    cutoff_iso = window_start.isoformat()
    try:
        existing = (
            None
            if force_full
            else storage_repository.read_read_object_keys_cache(storage_client, project_id)
        )
        meta = event_cache.get_cache_metadata(firestore_client, _STORAGE_CACHE_KIND, project_id)
        anchor = meta.get("last_scan_receive_ts") if meta else None
        incremental = existing is not None and anchor is not None

        if incremental:
            delta = storage_repository.scan_read_object_events(
                logging_client,
                project_id,
                since_receive_ts=anchor,
                page_pause=_SCAN_PAGE_PAUSE_SECONDS,
            )
            merged = dict(existing)
            for key, ts in delta.items():
                if ts > merged.get(key, ""):
                    merged[key] = ts
        else:
            merged = storage_repository.scan_read_object_events(
                logging_client, project_id, page_pause=_SCAN_PAGE_PAUSE_SECONDS
            )
    except (LoggingAccessDeniedError, LoggingQuotaExceededError):
        return 0
    except GoogleAPICallError as exc:
        logger.warning(
            json.dumps({"project_id": project_id, "status": "storage_api_error", "error": str(exc)})
        )
        return 0

    kept = {key: ts for key, ts in merged.items() if ts and ts >= cutoff_iso}
    storage_repository.write_read_object_keys_cache(
        storage_client,
        firestore_client,
        project_id,
        kept,
        window_start=window_start,
        last_scan_receive_ts=now_receive,
        last_full_scan_at=now_receive if not incremental else None,
        mode="incremental" if incremental else "full",
    )
    return len(kept)


def _refresh_project(
    logging_client: cloud_logging.Client,
    storage_client: storage.Client,
    firestore_client: firestore.Client,
    project_id: str,
    *,
    force_full: bool,
) -> tuple[str, dict[str, object]]:
    """Retorna (status, counts) pra o registro de execução no Firestore
    (event_cache_runs, lido pela tela de acompanhamento em Administração →
    Caches). status: "ok" | "access_denied" | "quota_exceeded" |
    "api_error" | "unexpected_error"."""
    try:
        counts = _refresh_job_caches(
            logging_client, storage_client, firestore_client, project_id, force_full=force_full
        )
        counts["storage_read_object_keys"] = _refresh_storage_read_keys(
            logging_client, storage_client, firestore_client, project_id, force_full=force_full
        )
    except LoggingAccessDeniedError:
        logger.warning(json.dumps({"project_id": project_id, "status": "access_denied"}))
        return "access_denied", {}
    except LoggingQuotaExceededError:
        # Cota read_requests/min do projeto estourada mesmo após o retry —
        # transitória. O ciclo do dia seguinte (ou um novo disparo manual)
        # preenche; não pode derrubar o refresh dos demais projetos.
        logger.warning(json.dumps({"project_id": project_id, "status": "quota_exceeded"}))
        return "quota_exceeded", {}
    except GoogleAPICallError as exc:
        # Cobre, entre outros, projeto inexistente/renomeado/deletado
        # (Cloud Logging devolve 404 NotFound em vez de 403 Forbidden
        # quando a SA do Hub não tem NENHUM binding de IAM no projeto —
        # `hub_projects`/"vistos" pode conter entradas obsoletas). Um
        # projeto com problema não pode derrubar o refresh dos demais.
        logger.warning(
            json.dumps({"project_id": project_id, "status": "api_error", "error": str(exc)})
        )
        return "api_error", {}
    except Exception as exc:  # noqa: BLE001 — rede de segurança final do job em lote
        logger.error(
            json.dumps({"project_id": project_id, "status": "unexpected_error", "error": str(exc)})
        )
        return "unexpected_error", {}

    logger.info(json.dumps({"project_id": project_id, "status": "ok", **counts}))
    return "ok", counts


def main() -> None:
    logging_client = get_logging_client()
    storage_client = get_storage_client()
    firestore_client = get_firestore_client()

    force_full = settings.cache_force_full
    only_projects = settings.cache_only_projects_list
    # only_projects (escolha explícita do gatilho de admin) SUBSTITUI a
    # união hub_projects ∪ "vistos" — roda exatamente os projetos pedidos,
    # nada mais. Vazio = todos (ciclo diário do Scheduler).
    projects = sorted(only_projects) if only_projects else _known_projects(firestore_client)
    logger.info(
        json.dumps(
            {
                "status": "start",
                "project_count": len(projects),
                "force_full": force_full,
                "only_projects": only_projects or None,
            }
        )
    )

    # Registro de execução no Firestore (event_cache_runs) — lido pela tela
    # de acompanhamento em Administração → Caches. try/finally garante que
    # a execução seja marcada como concluída mesmo se main() estourar no
    # meio (o que _refresh_project já não deixa acontecer por projeto, mas
    # _known_projects / get_*_client podem).
    run_id = event_cache.start_cache_run(firestore_client, projects)
    try:
        for project_id in projects:
            status, counts = _refresh_project(
                logging_client,
                storage_client,
                firestore_client,
                project_id,
                force_full=force_full,
            )
            event_cache.record_cache_run_project(
                firestore_client, run_id, project_id, status, counts
            )
    finally:
        event_cache.finish_cache_run(firestore_client, run_id)
    logger.info(json.dumps({"status": "done", "run_id": run_id}))


if __name__ == "__main__":
    main()
