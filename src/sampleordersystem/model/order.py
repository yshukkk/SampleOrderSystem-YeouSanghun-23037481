"""Order entity, its JSON-file-backed CRUD repository, and pure state-transition rules.

`Order` mirrors the domain model in PRD.md (id/sample_id/customer_name/
quantity/status). `OrderRepository` wraps a `JsonRepository` instance the
same way `SampleRepository` does, adding only the intake convenience method
this phase needs: creating a new order with status `RESERVED`.

This module also defines the *full* state-transition rule set from PRD.md's
state machine (RESERVED -> REJECTED/CONFIRMED/PRODUCING, PRODUCING ->
CONFIRMED, CONFIRMED -> RELEASED) as pure functions with no persistence and
no console I/O, so the rules themselves can be unit-tested in isolation.
As of Phase 4, `OrderController` wires `reject()`/`approve()` (RESERVED ->
REJECTED/CONFIRMED/PRODUCING); `complete_production()`/`release()` remain
unwired until Phase 5/6.
"""

from __future__ import annotations

from dataclasses import dataclass

from sampleordersystem.persistence import JsonRepository

STATUS_RESERVED = "RESERVED"
STATUS_REJECTED = "REJECTED"
STATUS_PRODUCING = "PRODUCING"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_RELEASED = "RELEASED"

INVALID_TRANSITION_MESSAGE = "허용되지 않은 상태 전이입니다: {current} -> {target}"


@dataclass
class Order:
    id: int
    sample_id: int
    customer_name: str
    quantity: int
    status: str

    @classmethod
    def from_record(cls, record: dict) -> "Order":
        return cls(
            id=record["id"],
            sample_id=record["sample_id"],
            customer_name=record["customer_name"],
            quantity=record["quantity"],
            status=record["status"],
        )


class OrderRepository:
    """Domain-convenience wrapper around a `JsonRepository` of orders."""

    def __init__(self, repository: JsonRepository) -> None:
        self._repository = repository

    def intake(self, sample_id: int, customer_name: str, quantity: int) -> Order:
        """Create a new order. Status always starts at RESERVED (PRD)."""
        record = self._repository.create(
            {
                "sample_id": sample_id,
                "customer_name": customer_name,
                "quantity": quantity,
                "status": STATUS_RESERVED,
            }
        )
        return Order.from_record(record)

    def list_all(self) -> list[Order]:
        return [Order.from_record(record) for record in self._repository.list_all()]

    def find(self, order_id: int) -> Order | None:
        record = self._repository.find(order_id)
        if record is None:
            return None
        return Order.from_record(record)

    def update_status(self, order_id: int, status: str) -> Order | None:
        """Persist a new status for an existing order.

        Returns the updated `Order`, or `None` if `order_id` does not exist
        (caller decides how to report that -- in practice the controller
        already looked the order up via `find()` before computing the new
        status, so this should only fail if the order was deleted in
        between, which nothing in this system currently does).
        """
        updated = self._repository.update(order_id, status=status)
        if not updated:
            return None
        return self.find(order_id)


# --- Pure state-transition rules (PRD state machine) ------------------------
#
# These functions are not called from any controller or menu at this phase
# (Phase 3 only exposes intake). They exist here because PLAN.md Phase 3
# explicitly permits pre-building the full transition rule set on the model,
# and expressing it as pure functions keeps it independently unit-testable
# ahead of the controller wiring that later phases will add.

VALID_TRANSITIONS: dict[str, set[str]] = {
    STATUS_RESERVED: {STATUS_REJECTED, STATUS_CONFIRMED, STATUS_PRODUCING},
    STATUS_PRODUCING: {STATUS_CONFIRMED},
    STATUS_CONFIRMED: {STATUS_RELEASED},
}


def _transition(current_status: str, required_source: str, target_status: str) -> str:
    allowed = VALID_TRANSITIONS.get(current_status, set())
    if current_status != required_source or target_status not in allowed:
        raise ValueError(
            INVALID_TRANSITION_MESSAGE.format(current=current_status, target=target_status)
        )
    return target_status


def reject(order: Order) -> str:
    """RESERVED -> REJECTED."""
    return _transition(order.status, STATUS_RESERVED, STATUS_REJECTED)


def approve(order: Order, stock: int) -> str:
    """RESERVED -> CONFIRMED (재고 충분, stock >= quantity) or PRODUCING (재고 부족)."""
    target = STATUS_CONFIRMED if stock >= order.quantity else STATUS_PRODUCING
    return _transition(order.status, STATUS_RESERVED, target)


def complete_production(order: Order) -> str:
    """PRODUCING -> CONFIRMED."""
    return _transition(order.status, STATUS_PRODUCING, STATUS_CONFIRMED)


def release(order: Order) -> str:
    """CONFIRMED -> RELEASED."""
    return _transition(order.status, STATUS_CONFIRMED, STATUS_RELEASED)
