"""Tests for `SampleRepository` -- domain-convenience CRUD on top of `JsonRepository`."""

from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


def make_repository(tmp_path):
    return SampleRepository(JsonRepository(tmp_path / "samples.json"))


def test_register_assigns_id_and_starts_stock_at_zero(tmp_path):
    repository = make_repository(tmp_path)

    sample = repository.register(name="시료-A", avg_production_time=2.5, yield_rate=0.9)

    assert sample.id == 1
    assert sample.name == "시료-A"
    assert sample.avg_production_time == 2.5
    assert sample.yield_rate == 0.9
    assert sample.stock == 0


def test_register_assigns_auto_incrementing_ids(tmp_path):
    repository = make_repository(tmp_path)

    first = repository.register(name="시료-A", avg_production_time=1.0, yield_rate=1.0)
    second = repository.register(name="시료-B", avg_production_time=2.0, yield_rate=0.8)

    assert first.id == 1
    assert second.id == 2


def test_list_all_returns_registered_samples_in_order(tmp_path):
    repository = make_repository(tmp_path)
    repository.register(name="시료-A", avg_production_time=1.0, yield_rate=1.0)
    repository.register(name="시료-B", avg_production_time=2.0, yield_rate=0.8)

    samples = repository.list_all()

    assert [sample.name for sample in samples] == ["시료-A", "시료-B"]


def test_find_success(tmp_path):
    repository = make_repository(tmp_path)
    registered = repository.register(name="시료-A", avg_production_time=1.0, yield_rate=1.0)

    found = repository.find(registered.id)

    assert found == registered


def test_find_failure_for_nonexistent_id(tmp_path):
    repository = make_repository(tmp_path)
    repository.register(name="시료-A", avg_production_time=1.0, yield_rate=1.0)

    assert repository.find(999) is None


def test_search_by_name_matches_substring_case_insensitively(tmp_path):
    repository = make_repository(tmp_path)
    repository.register(name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)
    repository.register(name="wafer-B", avg_production_time=1.0, yield_rate=1.0)
    repository.register(name="Chip-C", avg_production_time=1.0, yield_rate=1.0)

    results = repository.search_by_name("wafer")

    assert {sample.name for sample in results} == {"Wafer-A", "wafer-B"}


def test_search_by_name_returns_empty_list_when_no_match(tmp_path):
    repository = make_repository(tmp_path)
    repository.register(name="Wafer-A", avg_production_time=1.0, yield_rate=1.0)

    assert repository.search_by_name("없음") == []


def test_repository_persists_across_repository_instances(tmp_path):
    path = tmp_path / "samples.json"
    SampleRepository(JsonRepository(path)).register(
        name="시료-A", avg_production_time=1.0, yield_rate=1.0
    )

    reloaded = SampleRepository(JsonRepository(path))

    assert [sample.name for sample in reloaded.list_all()] == ["시료-A"]
