"""Shared numeric-input-parsing helpers for console controllers.

`SampleController`, `OrderController`, and `ShippingController` each parsed
raw input strings as `int`/`float`, reporting an error via their injected
`output_func` and returning `None` on failure. The parsing *logic* was
identical everywhere; only the exact error-message wording differed in one
case (`SampleController`'s id-parsing uses "ID는 정수로 입력해야 합니다"
instead of the generic "숫자로 입력해야 합니다" the other two use), so the
message template is a parameter here rather than a single hardcoded string
-- callers that share the exact same wording can also share one constant
(see `INVALID_NUMBER_MESSAGE` below), while `SampleController` keeps its
own `INVALID_ID_MESSAGE` for the id-specific wording.
"""

# Shared by OrderController's/ShippingController's int parsing and
# SampleController's float parsing -- all three use this exact wording.
INVALID_NUMBER_MESSAGE = "숫자로 입력해야 합니다: {raw}"


def parse_int(raw: str, write_func, message_template: str) -> int | None:
    """Parse `raw` as an `int`, reporting `message_template.format(raw=raw)`
    via `write_func` and returning `None` on failure."""
    try:
        return int(raw)
    except ValueError:
        write_func(message_template.format(raw=raw))
        return None


def parse_float(raw: str, write_func, message_template: str) -> float | None:
    """Parse `raw` as a `float`, reporting `message_template.format(raw=raw)`
    via `write_func` and returning `None` on failure."""
    try:
        return float(raw)
    except ValueError:
        write_func(message_template.format(raw=raw))
        return None
