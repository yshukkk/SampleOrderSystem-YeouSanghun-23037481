from sampleordersystem.persistence import JsonRepository


def test_create_assigns_auto_incrementing_id(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    first = repo.create({"name": "sample-1"})
    second = repo.create({"name": "sample-2"})

    assert first["id"] == 1
    assert second["id"] == 2


def test_list_all_reflects_insertion_order(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    repo.create({"name": "a"})
    repo.create({"name": "b"})
    repo.create({"name": "c"})

    names = [record["name"] for record in repo.list_all()]
    assert names == ["a", "b", "c"]


def test_find_success(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    created = repo.create({"name": "sample-1"})

    found = repo.find(created["id"])

    assert found == created


def test_find_failure_for_nonexistent_id(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    repo.create({"name": "sample-1"})

    assert repo.find(999) is None


def test_update_changes_only_specified_fields(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    created = repo.create({"name": "sample-1", "status": "pending"})

    result = repo.update(created["id"], status="done")

    assert result is True
    updated = repo.find(created["id"])
    assert updated["status"] == "done"
    assert updated["name"] == "sample-1"


def test_update_nonexistent_id_returns_false(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    assert repo.update(999, status="done") is False


def test_delete_then_find_fails(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    created = repo.create({"name": "sample-1"})

    result = repo.delete(created["id"])

    assert result is True
    assert repo.find(created["id"]) is None


def test_delete_nonexistent_id_returns_falsy(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    assert not repo.delete(999)


def test_separate_repositories_do_not_interfere(tmp_path):
    samples_repo = JsonRepository(tmp_path / "samples.json")
    orders_repo = JsonRepository(tmp_path / "orders.json")

    samples_repo.create({"name": "sample-1"})
    samples_repo.create({"name": "sample-2"})
    orders_repo.create({"name": "order-1"})

    assert len(samples_repo.list_all()) == 2
    assert len(orders_repo.list_all()) == 1
    assert orders_repo.list_all()[0]["id"] == 1


def test_records_survive_repository_restart(tmp_path):
    path = tmp_path / "samples.json"

    first_repo = JsonRepository(path)
    first_repo.create({"name": "sample-1"})
    first_repo.create({"name": "sample-2"})
    del first_repo  # simulate process restart: discard in-memory instance

    second_repo = JsonRepository(path)
    records = second_repo.list_all()

    assert [r["name"] for r in records] == ["sample-1", "sample-2"]
    assert [r["id"] for r in records] == [1, 2]


def test_next_id_continues_after_restart(tmp_path):
    path = tmp_path / "samples.json"

    first_repo = JsonRepository(path)
    first_repo.create({"name": "sample-1"})
    del first_repo

    second_repo = JsonRepository(path)
    new_record = second_repo.create({"name": "sample-2"})

    assert new_record["id"] == 2


def test_create_with_id_inserts_record_under_given_id(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    created = repo.create_with_id({"name": "sample-1"}, 42)

    assert created["id"] == 42
    assert created["name"] == "sample-1"
    assert repo.find(42) == created


def test_create_with_id_duplicate_is_rejected_and_does_not_overwrite(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    original = repo.create_with_id({"name": "sample-1"}, 7)

    result = repo.create_with_id({"name": "sample-2"}, 7)

    assert result is None
    assert repo.find(7) == original


def test_create_with_id_advances_next_id_past_manual_id(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")

    repo.create_with_id({"name": "sample-1"}, 5)
    new_record = repo.create({"name": "sample-2"})

    assert new_record["id"] == 6


def test_create_with_id_does_not_lower_next_id_below_existing_counter(tmp_path):
    repo = JsonRepository(tmp_path / "samples.json")
    repo.create({"name": "sample-1"})  # id=1, next_id becomes 2

    repo.create_with_id({"name": "sample-manual"}, 1000)
    new_record = repo.create({"name": "sample-3"})

    assert new_record["id"] == 1001
