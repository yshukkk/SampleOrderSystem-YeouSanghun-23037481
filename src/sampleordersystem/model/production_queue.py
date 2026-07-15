"""Production queue model: FIFO scheduling + PRD shortfall/yield/time formulas.

Pure model layer -- no persistence, no console I/O (per PLAN.md's layering
rule: `view` -> `controller` -> `model`). PLAN.md Phase 4 scope is to build
the queue and fill it (via `enqueue`, called from the controller's approval
branch); Phase 5 is the one that will *drain* it (auto-completing
PRODUCING -> CONFIRMED and crediting stock). Nothing here consumes the
queue -- `dequeue`/`peek` exist so a later `production_controller.py` has
something to call, but no such controller exists yet.

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

    `clock` is injectable (defaults to `time.monotonic`, immune to wall-clock
    adjustments) so tests can drive elapsed-time logic with a fake clock
    instead of real `time.sleep()`.
    """

    def __init__(self, clock=time.monotonic) -> None:
        self._items: deque[ProductionQueueItem] = deque()
        self._clock = clock

    def enqueue(self, item: ProductionQueueItem) -> None:
        was_empty = not self._items
        self._items.append(item)
        if was_empty:
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
