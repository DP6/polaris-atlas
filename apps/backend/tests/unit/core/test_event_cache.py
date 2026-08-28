from unittest.mock import MagicMock

from google.api_core.exceptions import NotFound

from observability_hub.core import event_cache


def _storage_client_with(existing_blobs: dict[str, bytes] | None = None) -> MagicMock:
    """Fake mínimo de storage.Client: bucket()/blob() sempre retornam o
    mesmo MagicMock por (bucket, path), com download_as_bytes levantando
    NotFound se o path não estiver em existing_blobs."""
    existing_blobs = existing_blobs or {}
    client = MagicMock()
    blobs: dict[str, MagicMock] = {}

    def fake_bucket(bucket_name):
        bucket = MagicMock()

        def fake_blob(blob_path):
            key = f"{bucket_name}/{blob_path}"
            if key not in blobs:
                blob = MagicMock()
                if key in existing_blobs:
                    blob.download_as_bytes.return_value = existing_blobs[key]
                else:
                    blob.download_as_bytes.side_effect = NotFound("missing")
                blobs[key] = blob
            return blobs[key]

        bucket.blob.side_effect = fake_blob
        return bucket

    client.bucket.side_effect = fake_bucket
    client._blobs = blobs  # inspeção nos testes de write
    return client


def test_read_cache_bytes_returns_none_on_miss():
    client = _storage_client_with()
    assert event_cache.read_cache_bytes(client, "bucket", "lineage/proj.json") is None


def test_write_then_read_cache_bytes_round_trips():
    client = _storage_client_with()

    event_cache.write_cache_bytes(client, "bucket", "lineage/proj.json", b'{"a": 1}')

    blob = client._blobs["bucket/lineage/proj.json"]
    blob.upload_from_string.assert_called_once_with(b'{"a": 1}', content_type="application/json")


def test_get_cache_metadata_returns_none_when_missing():
    firestore_client = MagicMock()
    doc = MagicMock()
    doc.exists = False
    firestore_client.collection.return_value.document.return_value.get.return_value = doc

    assert event_cache.get_cache_metadata(firestore_client, "lineage", "proj") is None


def test_set_cache_metadata_writes_expected_shape():
    firestore_client = MagicMock()
    doc_ref = firestore_client.collection.return_value.document.return_value

    data = event_cache.set_cache_metadata(firestore_client, "lineage", "proj", event_count=42)

    firestore_client.collection.return_value.document.assert_called_with("lineage:proj")
    doc_ref.set.assert_called_once_with(data)
    assert data["cache_kind"] == "lineage"
    assert data["project_id"] == "proj"
    assert data["event_count"] == 42
    assert data["cached_at"] is not None


def test_record_project_seen_writes_project_id():
    firestore_client = MagicMock()

    event_cache.record_project_seen(firestore_client, "proj")

    firestore_client.collection.return_value.document.assert_called_with("proj")
    doc_ref = firestore_client.collection.return_value.document.return_value
    written = doc_ref.set.call_args.args[0]
    assert written["project_id"] == "proj"
    assert written["last_seen_at"] is not None


def test_list_seen_projects_returns_document_ids():
    firestore_client = MagicMock()
    doc_a = MagicMock(id="proj-a")
    doc_b = MagicMock(id="proj-b")
    firestore_client.collection.return_value.stream.return_value = [doc_a, doc_b]

    assert event_cache.list_seen_projects(firestore_client) == ["proj-a", "proj-b"]


def test_start_cache_run_creates_running_doc_and_returns_id():
    firestore_client = MagicMock()
    # _prune_cache_runs itera o stream — vazio, nada a apagar.
    firestore_client.collection.return_value.order_by.return_value.stream.return_value = []

    run_id = event_cache.start_cache_run(firestore_client, ["a", "b", "c"])

    assert run_id
    doc_ref = firestore_client.collection.return_value.document.return_value
    written = doc_ref.set.call_args.args[0]
    assert written["run_id"] == run_id
    assert written["status"] == "running"
    assert written["project_count"] == 3
    assert written["projects"] == {}
    assert written["finished_at"] is None


def test_record_cache_run_project_updates_dotted_path():
    firestore_client = MagicMock()

    event_cache.record_cache_run_project(
        firestore_client, "run-1", "proj-x", "ok", {"job_events": 5, "access_events": 2}
    )

    doc_ref = firestore_client.collection.return_value.document.return_value
    firestore_client.collection.return_value.document.assert_called_with("run-1")
    update_arg = doc_ref.update.call_args.args[0]
    assert "projects.proj-x" in update_arg
    entry = update_arg["projects.proj-x"]
    assert entry["status"] == "ok"
    assert entry["job_events"] == 5
    assert entry["finished_at"] is not None


def test_finish_cache_run_marks_done():
    firestore_client = MagicMock()

    event_cache.finish_cache_run(firestore_client, "run-1")

    doc_ref = firestore_client.collection.return_value.document.return_value
    update_arg = doc_ref.update.call_args.args[0]
    assert update_arg["status"] == "done"
    assert update_arg["finished_at"] is not None


def test_list_cache_runs_orders_by_run_id_desc():
    firestore_client = MagicMock()
    query = firestore_client.collection.return_value.order_by.return_value.limit.return_value
    query.stream.return_value = [MagicMock(to_dict=lambda: {"run_id": "r2"})]

    runs = event_cache.list_cache_runs(firestore_client, limit=3)

    assert runs == [{"run_id": "r2"}]
    firestore_client.collection.return_value.order_by.assert_called_once()
    _, kwargs = firestore_client.collection.return_value.order_by.call_args
    assert kwargs.get("direction") is not None
