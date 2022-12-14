from __future__ import annotations

import random
from typing import List, Optional, Tuple, Iterator, Match

from loguru import logger

from mazemaster.datastructures.models_and_schemas import (
    ExcelCoordinate,
    _password_pattern_compiled,
    _gridsize_pattern_compiled,
    _username_pattern_compiled,
)

# This is the same as using the @pytest.mark.anyio on all test functions in the module
# pytestmark = pytest.mark.anyio(scope="session")

# username (i.e. happyUser)
# password (i.e. iTk19!n)


def test_grid_size_pattern():
    for i in range(-1000, 1000):
        for k in range(-1000, 1000):
            gs: str = f"{i}x{k}"
            m: Match = _gridsize_pattern_compiled.match(gs)

            if i <= 0 or k <= 1:
                if m:
                    logger.debug(f"GS {gs=}")

                assert not m
                continue

            if not m:
                logger.debug(f"GS {gs=} {m=}")

            assert m

            comp: str = f"{m.groups()[0]}x{m.groups()[1]}"
            assert gs == comp


def test_password_pattern():
    testpass: List[Tuple[str, bool]] = [
        ("iTk19!n", True),
        ("haha09101", False),
        ("LAALA111128", False),
        ("!kakakKK888p!", True),
        ("1Jjajauuhupp88!!!", True),
    ]

    for to_test_password, expeted_ok in testpass:
        mi: Iterator[Match] = _password_pattern_compiled.finditer(to_test_password)
        for m in mi:
            assert not m or expeted_ok


def test_username_pattern():
    testuser: List[Tuple[str, bool]] = [
        ("happyUser", True),
        ("someuser", False),
        ("some-uSer-123!", True),
        ("11111123!", False),
    ]

    for to_test_username, expeted_ok in testuser:
        mi: Iterator[Match] = _username_pattern_compiled.finditer(to_test_username)
        for m in mi:
            assert not m or expeted_ok
