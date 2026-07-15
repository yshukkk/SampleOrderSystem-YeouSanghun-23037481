"""Pure unit tests for the Order state-transition rules in `model/order.py`.

Phase 3 only wires order *intake* into the controller/menu, but the full
transition rule set (reject/approve/complete_production/release) is built
as pure, persistence-free functions on the model per PLAN.md's permissive
wording for this phase -- so it is tested here in isolation, ahead of any
controller wiring that later phases will add.
"""

import pytest

from sampleordersystem.model.order import (
    Order,
    approve,
    complete_production,
    reject,
    release,
)


def make_order(status: str, quantity: int = 10) -> Order:
    return Order(id=1, sample_id=1, customer_name="홍길동", quantity=quantity, status=status)


def test_reject_from_reserved_returns_rejected():
    order = make_order("RESERVED")

    assert reject(order) == "REJECTED"


def test_reject_from_non_reserved_status_raises():
    order = make_order("CONFIRMED")

    with pytest.raises(ValueError):
        reject(order)


def test_approve_with_sufficient_stock_returns_confirmed():
    order = make_order("RESERVED", quantity=5)

    assert approve(order, stock=5) == "CONFIRMED"


def test_approve_with_insufficient_stock_returns_producing():
    order = make_order("RESERVED", quantity=10)

    assert approve(order, stock=3) == "PRODUCING"


def test_approve_from_non_reserved_status_raises():
    order = make_order("PRODUCING")

    with pytest.raises(ValueError):
        approve(order, stock=100)


def test_complete_production_from_producing_returns_confirmed():
    order = make_order("PRODUCING")

    assert complete_production(order) == "CONFIRMED"


def test_complete_production_from_non_producing_status_raises():
    order = make_order("RESERVED")

    with pytest.raises(ValueError):
        complete_production(order)


def test_release_from_confirmed_returns_released():
    order = make_order("CONFIRMED")

    assert release(order) == "RELEASED"


def test_release_from_non_confirmed_status_raises():
    order = make_order("RESERVED")

    with pytest.raises(ValueError):
        release(order)


def test_rejected_status_has_no_outgoing_transitions():
    order = make_order("REJECTED")

    with pytest.raises(ValueError):
        reject(order)
    with pytest.raises(ValueError):
        approve(order, stock=100)


def test_released_status_has_no_outgoing_transitions():
    order = make_order("RELEASED")

    with pytest.raises(ValueError):
        release(order)
