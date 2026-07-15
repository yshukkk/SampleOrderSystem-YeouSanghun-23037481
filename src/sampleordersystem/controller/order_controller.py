"""Controller for the Order intake console screen.

Phase 3 scope only: order *intake* (creation at status `RESERVED`).
Approval/rejection (and everything downstream) is Phase 4+ and is
intentionally not wired into this controller yet.

Follows the same injected `input_func`/`output_func` pattern as
`SampleController` so it can be driven end-to-end in tests without a real
console.
"""

from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus

UNKNOWN_SAMPLE_MESSAGE = "등록되지 않은 시료 ID입니다: {sample_id}"
INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EXIT_MESSAGE = "주문 메뉴를 종료합니다."
INTAKE_SUCCESS_MESSAGE = "주문이 접수되었습니다: ID={order_id} 상태={status}"


class OrderController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(
        self,
        order_repository: OrderRepository,
        sample_repository: SampleRepository,
        input_func=input,
        output_func=print,
    ):
        self._order_repository = order_repository
        self._sample_repository = sample_repository
        self._read = input_func
        self._write = output_func
        self._actions = {
            "1": self._intake_order,
        }

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(menus.render_order_menu())
        choice = self._read().strip()

        if choice == "2":
            self._write(EXIT_MESSAGE)
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True

    def _intake_order(self) -> None:
        sample_id_raw = self._read().strip()
        sample_id = self._parse_int(sample_id_raw)
        if sample_id is None:
            return

        customer_name = self._read().strip()

        quantity_raw = self._read().strip()
        quantity = self._parse_int(quantity_raw)
        if quantity is None:
            return

        sample = self._sample_repository.find(sample_id)
        if sample is None:
            self._write(UNKNOWN_SAMPLE_MESSAGE.format(sample_id=sample_id))
            return

        order = self._order_repository.intake(
            sample_id=sample_id,
            customer_name=customer_name,
            quantity=quantity,
        )
        self._write(
            INTAKE_SUCCESS_MESSAGE.format(order_id=order.id, status=order.status)
        )

    def _parse_int(self, raw: str) -> int | None:
        try:
            return int(raw)
        except ValueError:
            self._write(INVALID_NUMBER_MESSAGE.format(raw=raw))
            return None
