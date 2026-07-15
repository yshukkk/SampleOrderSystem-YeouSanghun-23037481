"""Controller for the Production Line console screen (PRD "5. 생산 라인").

Drains the FIFO `ProductionQueue` that `OrderController`'s approval branch
fills (Phase 4): shows queue status/backlog, lists queued items without
removing them (non-destructive, FIFO order), and processes production
completion for the front item -- transitioning that order PRODUCING ->
CONFIRMED (via `order_model.complete_production`) and crediting the
produced quantity back onto the sample's stock.

Completion is now genuinely time-gated: the front-of-queue item's
`started_at` is stamped by `ProductionQueue` the instant it becomes the
front (see `model/production_queue.py`), and "생산 완료 처리" only actually
completes the item once real elapsed time (per the queue's injectable
clock) has reached its computed 총생산시간 (`ProductionQueue.is_front_ready()`).
Selecting the action before that reports the remaining time and makes no
state change at all (no dequeue, no order transition, no stock credit).

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

EXIT_MESSAGE = "생산 라인 메뉴를 종료합니다."
UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"
EMPTY_QUEUE_MESSAGE = "생산 완료 처리할 항목이 없습니다."
NOT_READY_MESSAGE = "아직 생산이 완료되지 않았습니다: 남은 시간={remaining_time}"
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
            "3": self._complete_production,
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

        if choice == "4":
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
        `is_front_ready()` -- this does not re-check readiness itself, to
        avoid duplicating that check across `drain_ready_items()` and
        `_complete_production()`. Returns the formatted success/failure
        message; does not print it.
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

        updated_sample = self._sample_repository.add_stock(item.sample_id, item.actual_production)
        if updated_sample is None:
            return SAMPLE_NOT_FOUND_FOR_QUEUE_ITEM_MESSAGE.format(sample_id=item.sample_id)

        return COMPLETE_SUCCESS_MESSAGE.format(
            order_id=order.id,
            status=new_status,
            actual_production=item.actual_production,
            sample_id=item.sample_id,
        )

    def _complete_production(self) -> None:
        """Manual "생산 완료 처리" menu action (choice "3").

        Since `run_once()` now drains everything ready at the top of every
        call, by the time this runs there will almost never be anything
        newly ready that wasn't already caught there -- this action is now
        a redundant-but-harmless manual force-check rather than the sole
        completion path. Kept working standalone (still reports empty/
        not-ready correctly) since it's reachable on its own via choice "3".
        """
        if len(self.production_queue) == 0:
            self._write(EMPTY_QUEUE_MESSAGE)
            return

        if not self.production_queue.is_front_ready():
            self._write(
                NOT_READY_MESSAGE.format(remaining_time=self.production_queue.remaining_time())
            )
            return

        self._write(self._complete_front_item())
