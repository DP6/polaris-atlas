from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class CertificationStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"


class MetadataOwner(BaseModel):
    technical_owner: str | None = None
    steward: str | None = None
    team: str | None = None


class MetadataClassification(BaseModel):
    domain: str | None = None
    # Texto livre nesta v1 — times diferentes usam vocabulário diferente
    # pra sensibilidade, sem demanda real de padronização ainda. Ver
    # docs/specs/metadata.md.
    sensitivity: str | None = None


class RelatedLink(BaseModel):
    label: str
    url: str = Field(pattern=r"^https?://")


class ColumnPiiInfo(BaseModel):
    """Sugestão do scanner de PII (domains/pii, lida via
    pii_scan_history, nunca escrita por este domínio) + confirmação
    manual — o valor "oficial" é `flag`, sempre gravado com `source` e
    `confirmed_by`/`confirmed_at` a cada confirmação, mesmo quando ela só
    concorda com `scanner_flagged` (ver docs/specs/metadata.md, ASM-005
    e AC-META-004)."""

    flag: bool = False
    source: Literal["scanner", "manual"] | None = None
    scanner_flagged: bool | None = None
    scanner_confidence: Literal["high", "medium"] | None = None
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None


class MetadataColumn(BaseModel):
    description: str | None = None
    glossary_term: str | None = None
    pii: ColumnPiiInfo | None = None


class MetadataTableResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    description: str | None = None
    owner: MetadataOwner | None = None
    classification: MetadataClassification | None = None
    certification_status: CertificationStatus | None = None
    related_links: list[RelatedLink] = Field(default_factory=list)
    columns: dict[str, MetadataColumn] = Field(default_factory=dict)
    updated_at: datetime | None = None
    updated_by: str | None = None
    # False = tabela nunca documentada — nunca 404 (ver AC-META-001), a
    # UI usa este campo pra distinguir "vazio porque não documentada" de
    # "vazio porque os campos foram apagados de propósito".
    has_metadata: bool = False


class MetadataTableUpsertRequest(BaseModel):
    """Patch parcial — só os campos presentes no JSON do body são
    aplicados (service.py lê via model_dump(exclude_unset=True)), campo
    ausente preserva o valor anterior. `None` explícito no body APAGA o
    campo (distinto de ausente)."""

    description: str | None = None
    owner: MetadataOwner | None = None
    classification: MetadataClassification | None = None
    certification_status: CertificationStatus | None = None
    related_links: list[RelatedLink] | None = None


class MetadataColumnUpsertRequest(BaseModel):
    description: str | None = None
    glossary_term: str | None = None
    pii_flag: bool | None = None


class MetadataHistoryEntry(BaseModel):
    field: str
    old_value: str | None = None
    new_value: str | None = None
    changed_by: str
    changed_at: datetime


class MetadataHistoryResponse(BaseModel):
    entries: list[MetadataHistoryEntry]


class SuggestedPiiColumn(BaseModel):
    column_name: str
    flagged: bool
    confidence: Literal["high", "medium"] | None = None


class SuggestedPiiResponse(BaseModel):
    project_id: str
    dataset_id: str
    table_id: str
    # False = tabela nunca escaneada pelo domínio PII — `columns` vazio
    # não é ambíguo com "escaneada, nenhuma coluna flagada" (ver
    # docs/specs/metadata.md, AC-META-008).
    scanned: bool
    columns: list[SuggestedPiiColumn] = Field(default_factory=list)


class MetadataOverviewEntry(BaseModel):
    dataset_id: str
    table_id: str
    has_metadata: bool
    certification_status: CertificationStatus | None = None
    owner: MetadataOwner | None = None
    classification: MetadataClassification | None = None
    updated_at: datetime | None = None


class MetadataOverviewResponse(BaseModel):
    project_id: str
    tables: list[MetadataOverviewEntry]
    total_tables: int
    documented_count: int
