"""Cálculo de custo de storage do BigQuery — função pura, sem estado de
domínio. Vive em core/ (não em domains/finops/) porque é compartilhada
por mais de um domínio (finops e lineage, este último pro custo
estimado de tabelas órfãs) — diferente do parsing de audit log, que o
projeto duplica de propósito entre domínios, isto aqui é só aritmética
de preço sobre valores já resolvidos (settings + tamanho/data da
tabela), sem nada específico de um domínio."""

from datetime import datetime

from observability_hub.core.config import settings

_LONG_TERM_STORAGE_THRESHOLD_DAYS = 90


def estimate_bigquery_storage_cost_usd(
    size_bytes: int, modified: datetime | None, now: datetime
) -> float:
    is_long_term = (
        modified is not None and (now - modified).days >= _LONG_TERM_STORAGE_THRESHOLD_DAYS
    )
    price_per_gb = (
        settings.bigquery_storage_price_usd_per_gb_month_long_term
        if is_long_term
        else settings.bigquery_storage_price_usd_per_gb_month_active
    )
    gb = size_bytes / (1024**3)
    return round(gb * price_per_gb, 4)
