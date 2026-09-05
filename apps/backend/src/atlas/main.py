from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from atlas.api.v1 import (
    access,
    access_requests,
    admin,
    auth,
    catalog,
    favorites,
    finops,
    freshness,
    history,
    lineage,
    metadata,
    pii,
    profiling,
    project_admins,
    projects,
    quality,
    storage,
)
from atlas.core.config import settings
from atlas.core.exceptions import (
    AccessRequestNotFoundError,
    AdminAccessRequiredError,
    ColumnNotFoundError,
    DatasetNotFoundError,
    EventCacheNotReadyError,
    FolderAccessDeniedError,
    FolderNotFoundError,
    InvalidDateColumnError,
    InvalidSamplePercentError,
    InvalidSessionError,
    LastAdminLockoutError,
    LoggingAccessDeniedError,
    LoggingQuotaExceededError,
    OAuthEmailNotAllowedError,
    OAuthExchangeError,
    OAuthStateMismatchError,
    PiiScanTimeoutError,
    ProfilingTimeoutError,
    ProjectAccessDeniedError,
    ProjectAdminRequiredError,
    ProjectNotAuthorizedError,
    ProjectNotFoundError,
    StorageAccessDeniedError,
    TableNotFoundError,
    TableNotPartitionedError,
)

app = FastAPI()

# Frontend roda em outra origem (Vite dev server local, ou outro serviço
# Cloud Run em prod) — sem isso todo fetch do browser falha no preflight.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(project_admins.router)
app.include_router(catalog.router)
app.include_router(freshness.router)
app.include_router(profiling.router)
app.include_router(favorites.router)
app.include_router(history.router)
app.include_router(quality.router)
app.include_router(quality.router_folders)
app.include_router(lineage.router)
app.include_router(pii.router)
app.include_router(access.router)
app.include_router(finops.router)
app.include_router(admin.router)
app.include_router(access_requests.router)
app.include_router(storage.router)
app.include_router(metadata.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(ProjectAccessDeniedError)
def handle_project_access_denied(request: Request, exc: ProjectAccessDeniedError) -> JSONResponse:
    # A SA de fix é a do próprio ambiente em execução (dev ou prod), injetada
    # pelo Terraform via ATLAS_RUNTIME_SA_EMAIL — nunca
    # reconstruída a partir do project_id, que é o mesmo projeto pros dois
    # ambientes neste repositório (topologia single-project).
    sa_email = settings.runtime_sa_email
    # As três roles cobrem os dois modos de acesso que os domínios usam:
    # metadataViewer + jobUser dão conta de INFORMATION_SCHEMA (catalog,
    # freshness, discover_regions); dataViewer é o que profiling precisa a
    # mais pra rodar query real (mesmo um dry run) contra dados de tabela —
    # nenhuma das duas primeiras cobre isso. A exceção não carrega qual
    # permissão faltou especificamente, então sugerimos as três de uma vez;
    # add-iam-policy-binding é idempotente, rodar as três é seguro mesmo
    # quando só uma estava faltando.
    roles = ["bigquery.metadataViewer", "bigquery.jobUser", "bigquery.dataViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "access_denied",
            "message": "A service account do Hub não tem acesso a este projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
        },
    )


@app.exception_handler(LoggingAccessDeniedError)
def handle_logging_access_denied(request: Request, exc: LoggingAccessDeniedError) -> JSONResponse:
    sa_email = settings.runtime_sa_email
    # logging.viewer sozinho basta pra não estourar Forbidden, mas Data
    # Access audit logs (onde vive o jobCompletedEvent que lineage lê) só
    # ficam visíveis via API com logging.privateLogViewer também — sem essa
    # segunda role a chamada não falha, só retorna sempre vazio (ver aviso
    # estático em domains/lineage/service.py). Sugerimos as duas de uma vez,
    # mesmo padrão de ProjectAccessDeniedError.
    roles = ["logging.viewer", "logging.privateLogViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "logging_access_denied",
            "message": "A service account do Hub não tem acesso aos audit logs deste projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
        },
    )


@app.exception_handler(LoggingQuotaExceededError)
def handle_logging_quota_exceeded(request: Request, exc: LoggingQuotaExceededError) -> JSONResponse:
    # 503 (não 500): é transitório e do lado do servidor — o cliente
    # (TanStack Query) já reintenta 5xx com backoff, então costuma
    # auto-recuperar sem o usuário ver erro. Retry-After orienta o
    # intervalo. Sem `fix:` de gcloud — não é IAM; se recorrer, o caminho
    # é aumentar a cota logging.googleapis.com/read_requests do projeto.
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": str(exc.retry_after)},
        content={
            "error": "logging_quota_exceeded",
            "message": (
                "O limite de leitura de audit logs do projeto foi atingido "
                "temporariamente. Tente novamente em cerca de 1 minuto."
            ),
            "retry_after_seconds": exc.retry_after,
        },
    )


@app.exception_handler(EventCacheNotReadyError)
def handle_event_cache_not_ready(request: Request, exc: EventCacheNotReadyError) -> JSONResponse:
    # Rede de segurança — os serviços de lineage/access/finops/storage já
    # capturam EventCacheNotReadyError e degradam pra resposta vazia com
    # warning (o request path não escaneia mais ao vivo, modelo
    # incremental). Se chegar aqui é caminho não coberto: 503 porque é
    # transitório (o job diário ou o gatilho de admin popula o cache).
    return JSONResponse(
        status_code=503,
        headers={"Retry-After": "60"},
        content={
            "error": "event_cache_not_ready",
            "message": (
                "O cache de audit log deste projeto ainda não foi gerado. "
                "Um administrador pode disparar em Administração → Caches; "
                "o ciclo diário também popula sozinho."
            ),
        },
    )


@app.exception_handler(StorageAccessDeniedError)
def handle_storage_access_denied(request: Request, exc: StorageAccessDeniedError) -> JSONResponse:
    sa_email = settings.runtime_sa_email
    # roles/storage.objectViewer sozinha NÃO cobre storage.buckets.list/get
    # (só storage.objects.*) — confirmado em dev 2026-08-17 (403 mesmo com
    # a role concedida). list_buckets() precisa de storage.bucketViewer
    # também; a exceção não distingue qual das duas faltou, então sugerimos
    # as duas de uma vez, mesmo padrão de ProjectAccessDeniedError/
    # LoggingAccessDeniedError. Ver docs/specs/storage.md seção 8.
    roles = ["storage.bucketViewer", "storage.objectViewer"]
    return JSONResponse(
        status_code=403,
        content={
            "error": "storage_access_denied",
            "message": "A service account do Hub não tem acesso ao Cloud Storage deste projeto.",
            "fix": [
                f"gcloud projects add-iam-policy-binding {exc.project_id} "
                f"--member='serviceAccount:{sa_email}' "
                f"--role='roles/{role}'"
                for role in roles
            ],
        },
    )


@app.exception_handler(ProjectNotFoundError)
def handle_project_not_found(request: Request, exc: ProjectNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "project_not_found",
            "message": f"Projeto '{exc.project_id}' não encontrado ou não existe.",
        },
    )


@app.exception_handler(DatasetNotFoundError)
def handle_dataset_not_found(request: Request, exc: DatasetNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "dataset_not_found", "message": str(exc)},
    )


@app.exception_handler(TableNotFoundError)
def handle_table_not_found(request: Request, exc: TableNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "table_not_found", "message": str(exc)},
    )


@app.exception_handler(ColumnNotFoundError)
def handle_column_not_found(request: Request, exc: ColumnNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "column_not_found", "message": str(exc)},
    )


@app.exception_handler(TableNotPartitionedError)
def handle_table_not_partitioned(request: Request, exc: TableNotPartitionedError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "table_not_partitioned", "message": str(exc)},
    )


@app.exception_handler(InvalidSamplePercentError)
def handle_invalid_sample_percent(request: Request, exc: InvalidSamplePercentError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "invalid_sample_percent", "message": str(exc)},
    )


@app.exception_handler(InvalidDateColumnError)
def handle_invalid_date_column(request: Request, exc: InvalidDateColumnError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_date_column",
            "message": str(exc),
            "available_date_columns": exc.available_columns,
        },
    )


@app.exception_handler(ProfilingTimeoutError)
def handle_profiling_timeout(request: Request, exc: ProfilingTimeoutError) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"error": "profiling_timeout", "message": str(exc)},
    )


@app.exception_handler(PiiScanTimeoutError)
def handle_pii_scan_timeout(request: Request, exc: PiiScanTimeoutError) -> JSONResponse:
    return JSONResponse(
        status_code=504,
        content={"error": "pii_scan_timeout", "message": str(exc)},
    )


@app.exception_handler(OAuthStateMismatchError)
def handle_oauth_state_mismatch(request: Request, exc: OAuthStateMismatchError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "oauth_state_mismatch", "message": str(exc)},
    )


@app.exception_handler(OAuthExchangeError)
def handle_oauth_exchange_error(request: Request, exc: OAuthExchangeError) -> JSONResponse:
    return JSONResponse(
        status_code=502,
        content={"error": "oauth_exchange_failed", "message": str(exc)},
    )


@app.exception_handler(OAuthEmailNotAllowedError)
def handle_oauth_email_not_allowed(
    request: Request, exc: OAuthEmailNotAllowedError
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "email_not_allowed", "message": str(exc)},
    )


@app.exception_handler(InvalidSessionError)
def handle_invalid_session(request: Request, exc: InvalidSessionError) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "invalid_session", "message": str(exc)},
    )


@app.exception_handler(ProjectNotAuthorizedError)
def handle_project_not_authorized(request: Request, exc: ProjectNotAuthorizedError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "project_not_authorized", "message": str(exc)},
    )


@app.exception_handler(AdminAccessRequiredError)
def handle_admin_access_required(request: Request, exc: AdminAccessRequiredError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "admin_access_required", "message": str(exc)},
    )


@app.exception_handler(ProjectAdminRequiredError)
def handle_project_admin_required(request: Request, exc: ProjectAdminRequiredError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "project_admin_required", "message": str(exc)},
    )


@app.exception_handler(LastAdminLockoutError)
def handle_last_admin_lockout(request: Request, exc: LastAdminLockoutError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"error": "last_admin_lockout", "message": str(exc)},
    )


@app.exception_handler(AccessRequestNotFoundError)
def handle_access_request_not_found(
    request: Request, exc: AccessRequestNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "access_request_not_found", "message": str(exc)},
    )


@app.exception_handler(FolderNotFoundError)
def handle_folder_not_found(request: Request, exc: FolderNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": "folder_not_found", "message": str(exc)},
    )


@app.exception_handler(FolderAccessDeniedError)
def handle_folder_access_denied(request: Request, exc: FolderAccessDeniedError) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={"error": "folder_access_denied", "message": str(exc)},
    )
