import pytest


@pytest.fixture(autouse=True)
def _default_no_project_budget(monkeypatch):
    """get_budget() sempre consulta budget_repository.get_project_budget_amount
    desde a v1.13 (budget compartilhado por projeto, não mais condicionado
    a um user_email) — sem este default, todo teste de get_budget que não
    se importa com budget_target_usd bateria num firestore_client mockado
    de verdade (MagicMock) e quebraria tentando fazer float() de um
    MagicMock. Testes que querem testar o valor injetado sobrescrevem via
    monkeypatch no próprio corpo do teste (roda depois desta fixture)."""
    monkeypatch.setattr(
        "atlas.domains.finops.service.budget_repository.get_project_budget_amount",
        lambda client, project_id: None,
    )
