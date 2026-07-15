"""Production queue model: FIFO scheduling + PRD shortfall/yield/time formulas.

Pure model layer -- no persistence, no console I/O (per PLAN.md's layering
rule: `view` -> `controller` -> `model`). `OrderController`'s approval
branch fills the queue (via `enqueue`); `ProductionController` consumes it
via `dequeue()`/`peek()`, automatically, through `drain_ready_items()`.

Formulas, straight from PRD.md's "생산 라인" section, order fixed:
    부족분        = 주문 수량 - 현재 재고
    실 생산량      = ceil(부족분 / 수율)
    총 생산 시간    = 평균 생산시간 * 실 생산량
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass

from sampleordersystem.model.order import STATUS_PRODUCING, OrderRepository
from sampleordersystem.model.sample import SampleRepository


def calculate_shortfall(quantity: int, stock: int) -> int:
    """부족분 = 주문 수량 - 현재 재고.

    Callers are expected to only invoke this on the 재고 부족 branch (i.e.
    when ``stock < quantity``), where the result is always positive. For
    ``stock >= quantity`` the result would be <= 0; this function applies no
    clamping and simply returns the plain subtraction either way -- it is
    the caller's job (the controller) to only build a queue entry on the
    branch where a shortfall actually exists.
    """
    return quantity - stock


def calculate_actual_production(shortfall: int, yield_rate: float) -> int:
    """실 생산량 = ceil(부족분 / 수율).

    Always rounds *up* (`math.ceil`), even when the division is not exact,
    so the production line never under-produces relative to the shortfall
    after accounting for yield loss.
    """
    return math.ceil(shortfall / yield_rate)


def calculate_total_time(avg_production_time: float, actual_production: int) -> float:
    """총 생산 시간 = 평균 생산시간 * 실 생산량."""
    return avg_production_time * actual_production


@dataclass
class ProductionProgress:
    """Snapshot of the front-of-queue item's in-progress production.

    Returned by `ProductionQueue.front_progress()`. `produced_so_far` is
    always in `[0, item.actual_production]` -- it never exceeds the target,
    even once `is_front_ready()` is already True and `elapsed` has gone
    past `item.total_time`.
    """

    item: "ProductionQueueItem"
    elapsed: float
    produced_so_far: int


@dataclass
class ProductionQueueItem:
    """One entry in the FIFO production queue.

    Carries everything a later display (or Phase 5's completion logic)
    would need: which order/sample it is for, the original order quantity,
    and the three computed PRD figures.
    """

    order_id: int
    sample_id: int
    quantity: int
    shortfall: int
    actual_production: int
    total_time: float
    started_at: float | None = None


class ProductionQueue:
    """FIFO queue of `ProductionQueueItem`s.

    Since PRD.md's 생산 라인 is a single production line (one item produced
    at a time), only the front-of-queue item is ever actively "in
    production" -- its `started_at` is stamped the instant it becomes the
    front (either via `enqueue` into an empty queue, or via `dequeue`
    freeing up the line for the next item). Items waiting behind the front
    have `started_at is None` until their turn comes.

    `clock` is injectable (defaults to `time.time`, real wall-clock epoch
    seconds) so tests can drive elapsed-time logic with a fake clock instead
    of real `time.sleep()`. Wall-clock time is used (rather than
    `time.monotonic`, whose reference point is arbitrary and not comparable
    across separate process runs) so that a `started_at` value stamped in
    one process run remains meaningful -- and genuine elapsed time can be
    computed from it -- after that value is persisted and the process later
    restarts (see `rebuild_production_queue`). All of this class's
    elapsed-time math (`remaining_time()`, `is_front_ready()`,
    `front_progress()`) is purely relative (`self._clock() - front.
    started_at`), so switching the underlying clock function changes
    nothing about that logic -- only what `started_at` values now mean.
    """

    def __init__(self, clock=time.time) -> None:
        self._items: deque[ProductionQueueItem] = deque()
        self._clock = clock

    def enqueue(self, item: ProductionQueueItem) -> None:
        """Append `item`; if it becomes the front, start its timer.

        Only auto-stamps `started_at` to "now" when it is still `None` --
        an item restored from persisted data (see `rebuild_production_queue`)
        may already carry a real, previously-recorded `started_at`, which
        must be respected rather than overwritten, so genuine elapsed time
        (including time that passed while the process was not running) is
        honored.
        """
        was_empty = not self._items
        self._items.append(item)
        if was_empty and item.started_at is None:
            item.started_at = self._clock()

    def dequeue(self) -> ProductionQueueItem | None:
        """Remove and return the front (oldest) item, or None if empty."""
        if not self._items:
            return None
        item = self._items.popleft()
        if self._items and self._items[0].started_at is None:
            self._items[0].started_at = self._clock()
        return item

    def peek(self) -> ProductionQueueItem | None:
        """Return the front item without removing it, or None if empty."""
        if not self._items:
            return None
        return self._items[0]

    def remaining_time(self) -> float | None:
        """Seconds left before the front item's production finishes.

        `None` if the queue is empty. If the front item somehow has no
        `started_at` (should not happen given enqueue/dequeue's stamping),
        defensively treat it as "just started" -- full `total_time` left.
        """
        front = self.peek()
        if front is None:
            return None
        if front.started_at is None:
            return front.total_time
        return max(0.0, front.total_time - (self._clock() - front.started_at))

    def front_progress(self) -> ProductionProgress | None:
        """Snapshot of "현재까지의 생산량" for the front item, or None if empty.

        Does not duplicate `remaining_time()`/`is_front_ready()`'s elapsed-time
        logic beyond the same defensive `started_at is None` -> elapsed=0.0
        handling. `produced_so_far` is the floor of how many whole units'
        worth of elapsed time have passed, capped at `actual_production` so
        it never overshoots the target even long after production is ready.
        """
        front = self.peek()
        if front is None:
            return None

        elapsed = 0.0 if front.started_at is None else self._clock() - front.started_at

        if front.actual_production <= 0:
            produced_so_far = front.actual_production
        else:
            avg_production_time_per_unit = front.total_time / front.actual_production
            if avg_production_time_per_unit <= 0:
                produced_so_far = front.actual_production
            else:
                produced_so_far = min(
                    front.actual_production, int(elapsed // avg_production_time_per_unit)
                )

        return ProductionProgress(item=front, elapsed=elapsed, produced_so_far=produced_so_far)

    def is_front_ready(self) -> bool:
        """True only if the front item exists and its production time has elapsed."""
        front = self.peek()
        if front is None or front.started_at is None:
            return False
        return self._clock() - front.started_at >= front.total_time

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)


def rebuild_production_queue(
    order_repository: OrderRepository,
    sample_repository: SampleRepository,
    production_queue: ProductionQueue,
) -> None:
    """Repopulate an in-memory `ProductionQueue` from persisted PRODUCING orders.

    `ProductionQueue` itself is never persisted to JSON (see module
    docstring) -- only an order's final `status: "PRODUCING"` survives a
    restart. This is a **best-effort reconstruction**, not a true resume:
    the original 부족분/실생산량/총생산시간 values computed at approval time,
    and any elapsed production progress, are gone. This function
    recomputes those three figures from the sample's CURRENT stock (not
    the stock at original approval time, which isn't recoverable) via the
    same formulas the live approve-flow uses, and re-enqueues each
    restored item through the normal `enqueue()` path -- so the
    front-of-queue item's production timer restarts from zero at
    reconstruction time (its true elapsed progress before the restart is
    lost) UNLESS the order record carries a persisted `production_started_at`
    (a real wall-clock epoch-seconds timestamp, written by the controllers
    whenever a queue item's timer actually starts -- see `order_controller.
    py`/`production_controller.py`), in which case that exact value is
    passed through as the reconstructed item's `started_at` and `enqueue()`'s
    "only stamp if None" rule preserves it, so genuine elapsed time --
    including time that passed while the process was not running -- is
    honored across the restart. Orders with no such field (legacy data
    predating this fix, or an order that was queued but never became the
    front before the process ended) fall back to `started_at=None` and the
    existing best-effort "stamp on becoming front" behavior. This field is
    read directly from the raw JSON record here (not added to the `Order`
    dataclass) -- it is a production-queue-internal detail, not part of the
    order's own domain shape used elsewhere.

    Orders are processed in ascending `order.id` order as a deterministic
    stand-in for the original enqueue order (which is not recoverable
    either). An order whose linked sample no longer exists is skipped
    quietly (no console I/O happens here -- this runs at startup before
    any screen is wired up).
    """
    producing_orders = sorted(
        (order for order in order_repository.list_all() if order.status == STATUS_PRODUCING),
        key=lambda order: order.id,
    )

    for order in producing_orders:
        sample = sample_repository.find(order.sample_id)
        if sample is None:
            continue

        shortfall = max(0, calculate_shortfall(order.quantity, sample.stock))
        actual_production = calculate_actual_production(shortfall, sample.yield_rate)
        total_time = calculate_total_time(sample.avg_production_time, actual_production)

        # production_started_at is optional/repository-internal -- a record
        # without it (legacy data, or an order queued but never promoted to
        # front before the process ended) falls back to None via `.get()`.
        record = order_repository.find_raw(order.id)
        production_started_at = record.get("production_started_at") if record else None

        production_queue.enqueue(
            ProductionQueueItem(
                order_id=order.id,
                sample_id=sample.id,
                quantity=order.quantity,
                shortfall=shortfall,
                actual_production=actual_production,
                total_time=total_time,
                started_at=production_started_at,
            )
        )
