"""Shared dispatch boilerplate for menu-driven controllers.

`SampleController`, `OrderController`, `ProductionController`, and
`MonitoringController` all shared the exact same `run_once()` shape: print
the menu, read one choice, compare it against the sub-menu's exit choice,
look the choice up in a `_actions` dict, report `UNKNOWN_CHOICE_MESSAGE`
if nothing matched, otherwise call the action and keep looping. This module
factors that shape out once so each controller only supplies what's
actually specific to it (its own menu renderer, exit choice, exit message,
and `_actions` dict).

`ShippingController`'s flow does NOT fit this shape any more (it dropped
the numbered-menu/`_actions`-dict dispatch entirely in favor of an
auto-list-then-prompt loop), so it does not use `MenuController` -- it only
imports `UNKNOWN_CHOICE_MESSAGE` from here, since that message text is
still shared even though the surrounding control flow differs.
"""

UNKNOWN_CHOICE_MESSAGE = "잘못된 메뉴 번호입니다: {choice}"


class MenuController:
    """Base class for controllers whose `run_once()` is "render menu, read
    one choice, dispatch via `self._actions`, or exit."

    Subclasses must set, before `run_once()` is first called:
      - `self._read`/`self._write`: the injected input/output hooks.
      - `self._actions`: a `dict[str, Callable[[], None]]` mapping menu
        choice strings to zero-arg handler methods.

    and must implement `_render_menu()` and `_exit()` (see below).
    """

    def _render_menu(self) -> str:
        """Return the rendered menu text to print before reading a choice."""
        raise NotImplementedError

    def _is_exit_choice(self, choice: str) -> bool:
        """Return whether `choice` is this sub-menu's "뒤로가기" choice."""
        raise NotImplementedError

    def _exit_message(self) -> str:
        """Return the message to print when the exit choice is chosen."""
        raise NotImplementedError

    def run_once(self) -> bool:
        """Show the menu, handle one choice, and report whether to continue."""
        self._write(self._render_menu())
        choice = self._read().strip()

        if self._is_exit_choice(choice):
            self._write(self._exit_message())
            return False

        action = self._actions.get(choice)
        if action is None:
            self._write(UNKNOWN_CHOICE_MESSAGE.format(choice=choice))
            return True

        action()
        return True
