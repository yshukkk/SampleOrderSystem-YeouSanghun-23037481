"""Controller for the Production Line console screen (PRD "5. 생산 라인").

Drains the FIFO `ProductionQueue` that `OrderController`'s approval branch
fills (Phase 4): shows queue status/backlog, lists queued items without
removing them (non-destructive, FIFO order), and processes production
completion for the front item -- transitioning that order PRODUCING ->
CONFIRMED (via `order_model.complete_production`) and crediting the
produced quantity back onto the sample's stock.

Completion is now genuinely time-gated and fully automatic: the
front-of-queue item's `started_at` is stamped by `ProductionQueue` the
instant it becomes the front (see `model/production_queue.py`), and
`drain_ready_items()` only actually completes an item once real elapsed
time (per the queue's injectable clock) has reached its computed
총생산시간 (`ProductionQueue.is_front_ready()`). There is no manual
"생산 완료 처리" menu action any more -- `drain_ready_items()` runs at the
top of every `run_once()` (and again at the top of `__main__.py`'s main
loop), so a ready item completes as soon as control returns to either of
those points, with no menu choice needed to trigger it.

The `ProductionQueue` instance passed in here must be the *same* object
`OrderController` enqueues onto (shared by `__main__.py`), so that an order
approved via the order sub-menu is immediately visible in this one within
the same process run. Orders/samples are always re-read from their
JsonRepository-backed repositories (no caching layer of any kind lives in
this controller) -- every listing/status action reflects the latest
persisted state, even though the queue itself is in-memory only.

Follows the same injected `input_func`/`output_func` pattern as
`SampleController`/`OrderController` so it can be driven end-to-end in
tests without a real console.
"""

from sampleordersystem.model import order as order_model
from sampleordersystem.model.order import OrderRepository
from sampleordersystem.model.production_queue import ProductionQueue
from sampleordersystem.model.sample import SampleRepository
from sampleordersystem.view import menus, tables

EXIT_MESSAGE = "생산 라인 메뉴에서 돌아갑니다."
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
ORDER_NOT_FOUND_FOR_QUEUE_ITEM_MESSAGE = "생산 큐 항목에 연결된 주문을 찾을 수 없습니다: {order_id}"
SAMPLE_NOT_FOUND_FOR_QUEUE_ITEM_MESSAGE = "생산 큐 항목에 연결된 시료를 찾을 수 없습니다: {sample_id}"
COMPLETE_SUCCESS_MESSAGE = (
    "생산이 완료되었습니다: 주문 ID={order_id} 상태={status} "
    "재고 증가={actual_production} (시료ID={sample_id})"
)


class ProductionController:
    """Runs one menu round-trip per call to `run_once()`."""

    def __init__(
        self,
        order_repository: OrderRepository,
        sample_repository: SampleRepository,
        production_queue: ProductionQueue,
        input_func=input,
        output_func=print,
    ):
        self._order_repository = order_repository
        self._sample_repository = sample_repository
        self.production_queue = production_queue
        self._read = input_func
        self._write = output_func
        self._actions = {
            "1": self._show_status,
            "2": self._list_queue,
        }

    def run_once(self) -> bool:
        """Drain whatever is ready, show the menu, handle one choice, and
        report whether to continue.

        Draining happens FIRST, before the menu is even rendered, so any
        item that became ready since the last poll is already completed
        (and its completion message already shown) by the time the user
        sees this screen -- see `drain_ready_items()`.
        """
        for message in self.drain_ready_items():
            self._write(message)

        self._write(menus.render_production_menu())
        choice = self._read().strip()

        if choice == "3":
            self._write(EXIT_MESSAGE)
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True

    def _show_status(self) -> None:
        progress = self.production_queue.front_progress()
        self._write(tables.render_production_status(len(self.production_queue), progress))

    def _list_queue(self) -> None:
        # Non-destructive: iterate/peek only, never dequeue, so listing the
        # queue does not consume it.
        items = list(self.production_queue)
        self._write(tables.render_production_queue_table(items))

    def drain_ready_items(self) -> list[str]:
        """Auto-complete every front-of-queue item that is already ready.

        Loops for as long as the (new) front item is ready, so several
        items that all became ready between polls (e.g. multiple short
        productions queued back to back) are all completed in one call,
        not just the first. Pure logic + persistence side effects -- does
        not print anything itself; returns the formatted success message
        for each completed item so callers (`run_once()`, `__main__.py`'s
        main loop) can decide whether/how to display them.

        This is the "자동 전환" mechanism PRD.md describes for 생산 라인:
        since this app is single-threaded with no background timers,
        there is no way to complete an item while control is elsewhere
        (e.g. blocked on `input()` in another sub-menu) -- draining can
        only happen at a point the code actually regains control. Calling
        this at the top of every `run_once()` iteration, and additionally
        once per main-loop iteration in `__main__.py`, are the two such
        points in this app: together they mean nothing sits completed-but-
        unprocessed for longer than one poll interval.
        """
        messages = []
        while len(self.production_queue) > 0 and self.production_queue.is_front_ready():
            messages.append(self._complete_front_item())
        return messages

    def _complete_front_item(self) -> str:
        """Complete the current front-of-queue item.

        Assumes the caller has already confirmed the front item exists and
        `is_front_ready()` -- this does not re-check readiness itself, since
        `drain_ready_items()` (its only caller) already guarantees both.
        Returns the formatted success/failure message; does not print it.
        """
        item = self.production_queue.dequeue()

        order = self._order_repository.find(item.order_id)
        if order is None:
            return ORDER_NOT_FOUND_FOR_QUEUE_ITEM_MESSAGE.format(order_id=item.order_id)

        try:
            new_status = order_model.complete_production(order)
        except ValueError as exc:
            return str(exc)

        self._order_repository.update_status(order.id, new_status)

        # dequeue() may have just promoted a new front item and stamped its
        # timer to "now" (real wall-clock time, since started_at was None) --
        # persist that real start time onto its order record too, so it also
        # survives a restart (mirrors the same persistence done in
        # `order_controller.py`'s approve flow for the immediately-front case).
        new_front = self.production_queue.peek()
        if new_front is not None and new_front.started_at is not None:
            self._order_repository.update_status(
                new_front.order_id,
                order_model.STATUS_PRODUCING,
                production_started_at=new_front.started_at,
            )

        updated_sample = self._sample_repository.add_stock(item.sample_id, item.actual_production)
        if updated_sample is None:
            return SAMPLE_NOT_FOUND_FOR_QUEUE_ITEM_MESSAGE.format(sample_id=item.sample_id)

        return COMPLETE_SUCCESS_MESSAGE.format(
            order_id=order.id,
            status=new_status,
            actual_production=item.actual_production,
            sample_id=item.sample_id,
        )
