"""Exceções compartilhadas do modelo de acesso cross-project (ADR-006).

Vivem em core/ porque são reusadas por qualquer domínio que consulte um
projeto BigQuery alvo informado pelo usuário (catalog hoje; freshness e
profiling depois), não são específicas do domínio catalog.
"""


class ProjectAccessDeniedError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado ao projeto '{project_id}'.")


class LoggingAccessDeniedError(Exception):
    """A SA de runtime não tem roles/logging.viewer no projeto alvo —
    levantada por domains/lineage (e futuramente domains/access) ao
    consultar audit logs via Cloud Logging."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado aos audit logs do projeto '{project_id}'.")


class LoggingQuotaExceededError(Exception):
    """A cota `ReadRequestsPerMinutePerProject` do Cloud Logging
    (`logging.googleapis.com/read_requests`, default 60/min) foi estourada
    no projeto — 429 TooManyRequests ao paginar audit logs. É transitória
    (por minuto) e do projeto inteiro: dev e prod compartilham o balde
    (topologia single-project). Distinta de LoggingAccessDeniedError (falta
    de IAM, permanente) e do caso "resultado vazio ambíguo" (que vira
    warning, não erro). main.py mapeia pra HTTP 503 + Retry-After.

    Levantada hoje por domains/finops (fallback ao vivo de
    get_scan_events_cached); o retry com backoff que suaviza a maioria dos
    429 antes de chegar aqui entra depois em core/logging_client.py
    (list_entries_with_retry, ver CHANGELOG)."""

    def __init__(self, project_id: str, retry_after: int = 60) -> None:
        self.project_id = project_id
        self.retry_after = retry_after
        super().__init__(
            f"Cota de leitura de audit logs do projeto '{project_id}' atingida "
            "temporariamente — tente novamente em instantes."
        )


class EventCacheNotReadyError(Exception):
    """O cache de audit log do projeto ainda não foi gerado (nenhum blob no
    GCS) e o request path não escaneia mais ao vivo em cache miss (o scan
    completo só roda no job diário ou no gatilho manual de admin — modelo
    incremental, ver docs/specs/lineage.md). Os serviços de lineage/access/
    finops/storage capturam essa exceção e degradam pra resposta vazia com
    um warning; main.py mapeia pra HTTP 503 como rede de segurança."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"O cache de audit log do projeto '{project_id}' ainda não foi gerado.")


class StorageAccessDeniedError(Exception):
    """A SA de runtime não tem roles/storage.objectViewer no projeto alvo —
    levantada por domains/storage ao consultar buckets/objetos via Cloud
    Storage. Mesma família de LoggingAccessDeniedError (client REST,
    Forbidden na ausência da role), papel distinto de
    ProjectAccessDeniedError (que cobre só as roles de BigQuery)."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Acesso negado ao Cloud Storage do projeto '{project_id}'.")


class ProjectNotFoundError(Exception):
    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(f"Projeto '{project_id}' não encontrado ou não existe.")


class DatasetNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        super().__init__(f"Dataset '{dataset_id}' não encontrado no projeto '{project_id}'.")


class TableNotFoundError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(f"Tabela '{table_id}' não encontrada em '{project_id}.{dataset_id}'.")


class TableNotPartitionedError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(f"Tabela '{table_id}' em '{project_id}.{dataset_id}' não é particionada.")


class InvalidSamplePercentError(Exception):
    def __init__(self, sample_percent: float) -> None:
        self.sample_percent = sample_percent
        super().__init__(f"sample_percent deve ser >= 1 (recebido: {sample_percent}).")


class InvalidDateColumnError(Exception):
    def __init__(self, date_column: str, available_columns: list[str]) -> None:
        self.date_column = date_column
        self.available_columns = available_columns
        super().__init__(
            f"Coluna de data '{date_column}' não existe ou não é do tipo DATE/DATETIME/"
            f"TIMESTAMP. Colunas de data disponíveis: {available_columns}."
        )


class ProfilingTimeoutError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(
            f"Profiling de '{project_id}.{dataset_id}.{table_id}' excedeu 60s. "
            "Reduza sample_percent e tente novamente."
        )


class PiiScanTimeoutError(Exception):
    def __init__(self, project_id: str, dataset_id: str, table_id: str) -> None:
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.table_id = table_id
        super().__init__(
            f"Scan de PII de '{project_id}.{dataset_id}.{table_id}' excedeu 60s. "
            "Reduza sample_percent e tente novamente."
        )


class OAuthStateMismatchError(Exception):
    """O cookie oauth_state (setado em /auth/login) não bate com o
    parâmetro state devolvido por /auth/callback — sinal de CSRF ou de
    cookie expirado/perdido entre as duas etapas."""

    def __init__(self) -> None:
        super().__init__("Parâmetro state inválido ou ausente — tente fazer login novamente.")


class OAuthExchangeError(Exception):
    """Falha na troca do authorization code pelo token/userinfo do Google
    (rede, code expirado/reutilizado, credenciais OAuth erradas)."""

    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(f"Falha ao autenticar com o Google: {detail}")


class OAuthEmailNotAllowedError(Exception):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"E-mail '{email}' não está na allowlist de acesso.")


class InvalidSessionError(Exception):
    """Cookie de sessão (JWT) ausente, expirado ou com assinatura
    inválida — levantado por core/auth.py::get_current_user, usado em
    todo endpoint que exige usuário autenticado."""

    def __init__(self) -> None:
        super().__init__("Sessão inválida ou expirada — faça login novamente.")


class ProjectNotAuthorizedError(Exception):
    """Distinta de ProjectAccessDeniedError: ali o problema é a service
    account de runtime não ter IAM no GCP (orienta gcloud); aqui o
    problema é o ACL do próprio Hub (domains/admin) — o usuário logado
    não está liberado pra este project_id, independente da SA ter ou não
    acesso real. Levantada por core/auth.py::require_project_access."""

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        super().__init__(
            f"Você não está autorizado a acessar o projeto '{project_id}' no Hub. "
            "Peça a um administrador do Hub para liberar seu acesso."
        )


class AdminAccessRequiredError(Exception):
    """Levantada por core/auth.py::require_admin — usuário autenticado
    mas sem is_admin=True em hub_users."""

    def __init__(self) -> None:
        super().__init__("Esta ação requer permissão de administrador do Hub.")


class AccessRequestNotFoundError(Exception):
    """Levantada por domains/admin/service.py::approve_access_request /
    deny_access_request quando request_id não existe em access_requests."""

    def __init__(self, request_id: str) -> None:
        self.request_id = request_id
        super().__init__(f"Solicitação de acesso '{request_id}' não encontrada.")


class LastAdminLockoutError(Exception):
    """domains/admin/service.py bloqueia remover is_admin (ou deletar) do
    último administrador restante — sem isso, ninguém mais conseguiria
    abrir /admin pra reverter."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(
            f"Não é possível remover o acesso de administrador de '{email}' — "
            "é o último administrador do Hub. Promova outro usuário antes."
        )


class FolderNotFoundError(Exception):
    """Levantada por domains/quality/service.py quando folder_id não
    existe em profiling_folders (ou a entry_id não existe na subcoleção
    entries de um folder que existe)."""

    def __init__(self, folder_id: str) -> None:
        self.folder_id = folder_id
        super().__init__(f"Pasta de profiling '{folder_id}' não encontrada.")


class FolderAccessDeniedError(Exception):
    """Levantada por domains/quality/service.py — usuário autenticado,
    mas sem acesso de visualização (pasta privada de outra pessoa) ou de
    gestão (só dono/admin podem editar/apagar) à pasta."""

    def __init__(self, folder_id: str) -> None:
        self.folder_id = folder_id
        super().__init__(f"Você não tem acesso à pasta de profiling '{folder_id}'.")
