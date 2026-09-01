from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class BudgetScope(str, Enum):
    PROJECT = "project"
    DATASET = "dataset"
    TABLE = "table"


class BudgetEntry(BaseModel):
    project_id: str
    scope: BudgetScope
    # dataset_id preenchido em scope=dataset|table; table_id só em scope=table.
    dataset_id: str | None = None
    table_id: str | None = None
    amount_usd: float
    # Só "month" nesta fase (cadastro simples — ASM-005 do brief).
    period: str = "month"
    created_by: str
    created_at: datetime
    updated_at: datetime


class BudgetUpsertRequest(BaseModel):
    scope: BudgetScope
    dataset_id: str | None = None
    table_id: str | None = None
    amount_usd: float = Field(gt=0)

    @model_validator(mode="after")
    def _check_scope_fields(self) -> "BudgetUpsertRequest":
        if self.scope == BudgetScope.PROJECT and (self.dataset_id or self.table_id):
            raise ValueError("scope=project não aceita dataset_id/table_id")
        if self.scope == BudgetScope.DATASET and (not self.dataset_id or self.table_id):
            raise ValueError("scope=dataset exige dataset_id e não aceita table_id")
        if self.scope == BudgetScope.TABLE and (not self.dataset_id or not self.table_id):
            raise ValueError("scope=table exige dataset_id e table_id")
        return self


class BudgetListResponse(BaseModel):
    project_id: str
    budgets: list[BudgetEntry]
