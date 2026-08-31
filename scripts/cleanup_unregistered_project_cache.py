#!/usr/bin/env python3
"""Limpeza one-off dos metadados de cache de audit log de projetos NÃO
registrados em `hub_projects` (aba Admin → Projetos).

Contexto: antes desta correção, o job diário e a tela Admin → Caches
varriam `hub_projects` ∪ uma coleção "vistos" (`event_cache_seen_projects`)
que era gravada em qualquer cache miss do request path — inclusive para
projetos só *referenciados* na travessia de lineage (ex.:
`bigquery-public-data`). Agora `hub_projects` é a única fonte; nada mais
lê `event_cache_seen_projects`. Este script apaga os resíduos:

- a coleção `event_cache_seen_projects` inteira (ninguém mais lê);
- os docs de `event_cache_metadata` (id = "<kind>:<project_id>") cujo
  `project_id` não está em `hub_projects`.

NÃO toca em `event_cache_runs` (log histórico de execuções) nem nos blobs
do bucket de cache (a lifecycle do GCS os evicta sozinha).

Roda com as credenciais do OPERADOR (`gcloud auth application-default
login`), fora do Hub — não duplica lógica do backend de propósito.

Uso (a partir de apps/backend, pra usar o venv/uv.lock já resolvido):
    cd apps/backend
    uv run python ../../scripts/cleanup_unregistered_project_cache.py \\
        --project dp6-ci-polaris --environment dev
    # revê a saída (dry-run por padrão), depois:
    uv run python ../../scripts/cleanup_unregistered_project_cache.py \\
        --project dp6-ci-polaris --environment dev --apply

Roda primeiro em dev, confere, só depois em prod (mesmo --project,
--environment prod — bancos Firestore nomeados distintos).
"""

import argparse

from google.cloud import firestore

_SEEN_COLLECTION = "event_cache_seen_projects"
_METADATA_COLLECTION = "event_cache_metadata"
_PROJECTS_COLLECTION = "hub_projects"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--project",
        required=True,
        help="Projeto GCP onde o Hub roda (o mesmo serve dev e prod, ver ADR-010).",
    )
    parser.add_argument(
        "--environment",
        required=True,
        choices=["dev", "prod"],
        help="Ambiente — dev e prod são bancos Firestore nomeados distintos no mesmo projeto.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplica as remoções. Sem esta flag, só imprime o que seria apagado (dry-run).",
    )
    args = parser.parse_args()

    database = f"hub-{args.environment}"
    client = firestore.Client(project=args.project, database=database)

    registered = {doc.id for doc in client.collection(_PROJECTS_COLLECTION).stream()}
    print(f"{len(registered)} projeto(s) registrado(s) em hub_projects: {sorted(registered)}")

    seen_docs = list(client.collection(_SEEN_COLLECTION).stream())
    orphan_metadata = [
        doc
        for doc in client.collection(_METADATA_COLLECTION).stream()
        if doc.id.split(":", 1)[-1] not in registered
    ]

    print(f"\n{_SEEN_COLLECTION}: {len(seen_docs)} doc(s) a apagar (coleção inteira)")
    for doc in seen_docs:
        print(f"  - {doc.id}")

    print(f"\n{_METADATA_COLLECTION}: {len(orphan_metadata)} doc(s) órfão(s) a apagar")
    for doc in orphan_metadata:
        print(f"  - {doc.id}")

    if not args.apply:
        print("\n(dry-run — nada foi apagado; rode de novo com --apply)")
        return

    for doc in seen_docs:
        doc.reference.delete()
    for doc in orphan_metadata:
        doc.reference.delete()

    print(
        f"\nOK — apagados {len(seen_docs)} doc(s) de {_SEEN_COLLECTION} "
        f"e {len(orphan_metadata)} doc(s) órfão(s) de {_METADATA_COLLECTION} "
        f"({args.project}, database={database})."
    )


if __name__ == "__main__":
    main()
