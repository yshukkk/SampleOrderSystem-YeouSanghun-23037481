"""Shared "parse an order id then look it up" helper.

`OrderController` (approve/reject) and `ShippingController` (ship) both
parse a raw input string as an order id, reporting an error and returning
`None` on a non-numeric id, then look the id up via `OrderRepository.find`,
reporting (and returning `None` for) an unknown order id -- otherwise
returning the found `Order`. `ORDER_NOT_FOUND_MESSAGE` was independently
defined with identical text in both controllers; it lives here now as the
single shared copy.
"""

from sampleordersystem.controller._parsing import INVALID_NUMBER_MESSAGE, parse_int
from sampleordersystem.model.order import Order, OrderRepository

ORDER_NOT_FOUND_MESSAGE = "존재하지 않는 주문 번호입니다: {order_id}"


def find_order_by_id(raw: str, order_repository: OrderRepository, write_func) -> Order | None:
    """Parse `raw` as an order id and look it up in `order_repository`.

    Reports (via `write_func`) and returns `None` for a non-numeric id or an
    unknown order id; otherwise returns the found `Order`.
    """
    order_id = parse_int(raw, write_func, INVALID_NUMBER_MESSAGE)
    if order_id is None:
        return None
    order = order_repository.find(order_id)
    if order is None:
        write_func(ORDER_NOT_FOUND_MESSAGE.format(order_id=order_id))
        return None
    return order
