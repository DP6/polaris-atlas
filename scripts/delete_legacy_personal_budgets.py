#!/usr/bin/env python3
"""Migração da v1.13 (`docs/specs/finops-budget.md`, Q-003 respondida) —
apaga os budgets pessoais legados (`users/{email}/budgets/{doc_id}`)
depois que o budget virou compartilhado por projeto
(`hub_projects/{project_id}/budgets/{doc_id}`). Sem migração automática
dos valores: cada projeto começa sem budget compartilhado até um Admin
de projeto/superadmin recadastrar manualmente.

Roda **antes** de trocar o gate de `PUT`/`DELETE /finops/{p}/budgets`
pra `require_project_admin` (ver `docs/specs/finops-budget.md`, "Budget
compartilhado por projeto — pendente", "Mecanismo da migração") — a
ordem não afeta segurança (o código novo já para de ler a coleção
antiga assim que sobe), só evita deixar dado morto por mais tempo que o
necessário.

Usa as credenciais do OPERADOR (`gcloud auth application-default
login`), não a service account de runtime — mesmo racional de
`scripts/seed_admin.py`, roda localmente, fora do Hub.

Uso (a partir de apps/backend, pra usar o venv/uv.lock já resolvido):
    cd apps/backend
    uv run python ../../scripts/delete_legacy_personal_budgets.py \\
        --project dp6-ci-polaris --environment dev

Por padrão só lista o que seria apagado (--dry-run é o comportamento
default) — passe --confirm pra apagar de verdade. Rodar primeiro em dev,
conferir a contagem, só depois em prod (mesmo --project, --environment
prod).
"""

import argparse

from google.cloud import firestore


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Projeto GCP onde o Hub roda — o mesmo projeto serve dev e prod (topologia single-project, ver ADR-010).",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=["dev", "prod"],
        help="Ambiente a migrar — dev e prod são bancos Firestore nomeados distintos no mesmo projeto (ver core/firestore.py), então este parâmetro é obrigatório, não cosmético.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Apaga de verdade. Sem esta flag, só lista quantos docs seriam apagados (dry-run, default).",
    )
    args = parser.parse_args()

    database = f"hub-{args.environment}"
    client = firestore.Client(project=args.project, database=database)

    # collection_group ignora o caminho do documento-pai, só olha o nome
    # da subcoleção — pega "budgets" de QUALQUER users/{email}, uma
    # query só, sem iterar usuário por usuário (mesmo padrão de
    # domains/admin/analytics_repository.py pra favorites/profiling).
    docs = list(client.collection_group("budgets").stream())

    if not docs:
        print(f"Nenhum budget pessoal legado encontrado em {args.project} (database={database}).")
        return

    by_project: dict[str, int] = {}
    for doc in docs:
        data = doc.to_dict() or {}
        project_id = data.get("project_id", "(desconhecido)")
        by_project[project_id] = by_project.get(project_id, 0) + 1

    print(f"{len(docs)} budget(s) pessoal(is) legado(s) em {args.project} (database={database}):")
    for project_id, count in sorted(by_project.items()):
        print(f"  - {project_id}: {count}")

    if not args.confirm:
        print("\nDry-run (default) — nada foi apagado. Rode de novo com --confirm pra apagar.")
        return

    for doc in docs:
        doc.reference.delete()

    print(f"\nOK — {len(docs)} budget(s) pessoal(is) legado(s) apagado(s) de {args.project}.")


if __name__ == "__main__":
    main()
