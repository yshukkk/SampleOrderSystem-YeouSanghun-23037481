"""Shared test doubles used by the controller test suites.

`FakeConsole` was independently defined, identically, in every
`tests/controller/test_*_controller.py` file. It lives here once now and is
imported explicitly (`from tests.support import FakeConsole`) by each test
module, mirroring this project's existing style of explicit imports rather
than relying on conftest.py fixture auto-injection (a plain class defined in
conftest.py is not auto-available the way a `@pytest.fixture` function is,
so an explicit-import module is the clearer, more correct home for a shared
test double like this).
"""


class FakeConsole:
    """Supplies canned answers to input() calls and records print() calls."""

    def __init__(self, answers):
        self._answers = iter(answers)
        self.printed = []

    def read(self):
        return next(self._answers)

    def write(self, line):
        self.printed.append(line)

    def printed_text(self):
        return "\n".join(self.printed)
