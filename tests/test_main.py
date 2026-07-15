"""Tests for `__main__.render_summary`'s active-order-count filtering, and
for `run()`'s graceful-shutdown behavior when stdin is exhausted."""

from sampleordersystem import __main__ as main_module
from sampleordersystem.__main__ import EOF_EXIT_MESSAGE, render_summary
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.persistence import JsonRepository


def build_repos(tmp_path):
    sample_repo = SampleRepository(JsonRepository(tmp_path / "samples.json"))
    order_repo = OrderRepository(JsonRepository(tmp_path / "orders.json"))
    return sample_repo, order_repo


def test_render_summary_excludes_released_and_rejected_orders(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample = sample_repo.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=0.9)

    reserved = order_repo.intake(sample_id=sample.id, customer_name="A", quantity=1)
    confirmed = order_repo.intake(sample_id=sample.id, customer_name="B", quantity=1)
    order_repo.update_status(confirmed.id, "CONFIRMED")
    producing = order_repo.intake(sample_id=sample.id, customer_name="C", quantity=1)
    order_repo.update_status(producing.id, "PRODUCING")
    released = order_repo.intake(sample_id=sample.id, customer_name="D", quantity=1)
    order_repo.update_status(released.id, "RELEASED")
    rejected = order_repo.intake(sample_id=sample.id, customer_name="E", quantity=1)
    order_repo.update_status(rejected.id, "REJECTED")

    assert reserved.status == "RESERVED"  # sanity: intake defaults to RESERVED

    summary = render_summary(sample_repo, order_repo, production_queue_waiting=0)

    assert "전체 주문 수: 3" in summary  # RESERVED + CONFIRMED + PRODUCING only


def test_render_summary_does_not_mention_total_stock(tmp_path):
    sample_repo, order_repo = build_repos(tmp_path)
    sample_repo.register(id=1, name="Wafer-A", avg_production_time=1.0, yield_rate=0.9)

    summary = render_summary(sample_repo, order_repo, production_queue_waiting=0)

    assert "총 재고" not in summary


def test_run_shuts_down_gracefully_on_eof_instead_of_raising(tmp_path, monkeypatch, capsys):
    # Fix 2: when stdin is exhausted (piped/batch input ran out, or in
    # principle Ctrl+D/Ctrl+Z), input() raises EOFError -- run()'s main loop
    # must catch it once at the outermost point and print a friendly
    # shutdown message instead of letting a raw traceback propagate.
    #
    # Redirect the data paths to a scratch tmp_path so this never touches
    # the real data/ directory, and force the very first input() call to
    # raise EOFError immediately (simulating stdin running dry right away).
    monkeypatch.setattr(main_module, "SAMPLES_PATH", tmp_path / "samples.json")
    monkeypatch.setattr(main_module, "ORDERS_PATH", tmp_path / "orders.json")

    def fake_input(*args, **kwargs):
        raise EOFError

    monkeypatch.setattr("builtins.input", fake_input)

    main_module.run()  # must not raise

    assert EOF_EXIT_MESSAGE in capsys.readouterr().out
