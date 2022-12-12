from __future__ import annotations

import collections
import math
import re
import string
from functools import reduce
from queue import PriorityQueue as PriorityQueueBackend
from random import uniform
from re import Match, Pattern
from typing import (
    Dict,
    Generic,
    Iterator,
    List,
    NamedTuple,
    Optional,
    Protocol,
    Set,
    Tuple,
    TypeVar,
)

import cachetools
from loguru import logger

from ordered_set import OrderedSet


class SolverProtocol(Protocol):
    @staticmethod
    def search_all_available_exits(grid: SquareGrid, start: GridLocation) -> List[GridNode]:
        ...

    @staticmethod
    def search_shortest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        ...

    @staticmethod
    def search_longest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        ...


class MyStackFrame(NamedTuple):
    # visited: Optional[Set[GridLocation]] = None
    base_node: GridNode
    stackdepth: int


class StartInWallException(Exception):
    def __init__(self, *args):  # type:ignore
        super().__init__(*args)


class GoalInWallException(Exception):
    def __init__(self, *args):  # type:ignore
        super().__init__(*args)


class StartOutOfBoundsException(Exception):
    def __init__(self, *args):  # type:ignore
        super().__init__(*args)


class GoalOutOfBoundsException(Exception):
    def __init__(self, *args):  # type:ignore
        super().__init__(*args)


T = TypeVar("T")


def divmod_excel(n: int) -> Tuple[int, int]:
    a, b = divmod(n, 26)

    if b == 0:  # geht genau auf
        return a - 1, b + 26

    return a, b


def to_excel(num: int) -> str:
    chars = []

    hnum: int = num + 1  # 0-based nums -> 0 --> A

    while hnum > 0:
        hnum, r = divmod_excel(hnum)
        chars.append(string.ascii_uppercase[r - 1])
    return "".join(reversed(chars))


def from_excel(chars: str) -> int:
    return reduce(lambda r, x: r * 26 + 1 + x, map(string.ascii_uppercase.index, chars), 0)


_excel_pattern: str = r"^([A-Z]{1,})([1-9]\d*)$"
_excel_pattern_compiled: Pattern = re.compile(_excel_pattern)


def extracteinfo(excelstr: str) -> Tuple[int, int]:
    """gets the row and col as zero-based int in a tuple"""
    match: Optional[Match[str]] = _excel_pattern_compiled.match(excelstr)
    if not match:
        raise ValueError(f"INVALID: {excelstr}")

    chargroup: str = match.groups()[0]
    intgroup: str = match.groups()[1]

    ret: Tuple[int, int] = from_excel(chargroup) - 1, int(intgroup) - 1  # -1 => to account for A1 means col=0,row=0

    # print(f"{chargroup=} {intgroup=} => {ret=}")

    return ret


# @dataclass(slots=True)  # would be much faster!


def glt(gltp: GridLocation) -> str:
    return f"{to_excel(gltp.col)}{gltp.row + 1}"


class PriorityQueue(Generic[T]):
    def __init__(self, reverse: bool = False):
        self._backend: PriorityQueueBackend = PriorityQueueBackend()  # priorityqueuebackend is thread-safe!!!
        self._factor = -1 if reverse else 1

    def put(self, priority: float, item: T) -> None:
        self._backend.put((self._factor * priority, item))

    def pop(self) -> Tuple[float, T]:
        priority: float
        item: T
        priority, item = self._backend.get()

        return self._factor * priority, item

    def is_empty(self) -> bool:
        return self._backend.empty()

    def __len__(self) -> int:
        return self._backend.qsize()

    def __iter__(self) -> Iterator[Tuple[float, T]]:  # || Generator[YieldType, SendType, ReturnType]
        while not self.is_empty():
            yield self.pop()


class Stack(Generic[T]):
    def __init__(self) -> None:
        self._backend: collections.deque[T] = collections.deque()

    def is_empty(self) -> bool:
        return len(self._backend) == 0

    def push(self, item: T) -> None:
        self._backend.append(item)

    def pop(self) -> T:
        return self._backend.pop()

    def __repr__(self) -> str:
        return repr(self._backend)

    def __iter__(self) -> Iterator[T]:  # || Generator[YieldType, SendType, ReturnType]
        while not self.is_empty():
            yield self.pop()

    def __len__(self) -> int:
        return len(self._backend)

    def clear(self) -> None:
        self._backend.clear()


class Queue(Stack[T]):
    def __init__(self) -> None:
        super().__init__()

    def pop(self) -> T:
        return self._backend.popleft()


class GridLocation(NamedTuple):
    col: int
    row: int = 1


class PathHint(NamedTuple):
    north: int = -1
    east: int = -1
    south: int = -1
    west: int = -1


class Dimension(NamedTuple):
    width: int = -1
    height: int = -1


class GridNode:
    def __init__(
        self,
        location: GridLocation,
        parent: Optional[GridNode],
        cost: float = 0.0,
        heuristic: float = 0.0,
        # maxhint: Optional[PathHint] = None,
    ) -> None:
        self.location: GridLocation = location
        self.parent: Optional[GridNode] = parent
        self.cost: float = cost
        self.heuristic: float = heuristic
        self._visited: Optional[Set[GridLocation]] = None

        # self.maxhint: PathHint = maxhint or PathHint()

    # needed for PriorityQueue when two priorities are the same
    def __lt__(self, other: GridNode) -> bool:
        return (self.cost + self.heuristic) < (other.cost + other.heuristic)

    def __repr__(self) -> str:
        return f"GridNode(location=[col={self.location.col},row={self.location.row}], cost={self.cost} heuristic={self.heuristic})"

    def has_visited(self, location: GridLocation) -> bool:
        if not self._visited:
            self._visited = set()
            nc: GridNode = self
            while nc.parent:
                self._visited.add(nc.location)
                nc = nc.parent

        return location in self._visited


class SquareGrid:
    def __init__(self, dimension: Dimension, walls: Optional[Set[GridLocation]] = None):
        self.dimension = dimension
        self.walls: Set[GridLocation] = walls or set()

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=4096, ttl=600))
    def passable_and_in_bounds(self, loc: GridLocation) -> bool:
        grid: SquareGrid = self
        if loc in grid.walls:
            return False

        return 0 <= loc.col < grid.dimension.width and 0 <= loc.row < grid.dimension.height

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=4096, ttl=600))
    def allowed_neighbors(self, loc: GridLocation) -> List[GridLocation]:
        """not being out of bound and not e.g. in a wall"""
        grid: SquareGrid = self
        neighbors = [
            GridLocation(loc.col + 1, loc.row),
            GridLocation(loc.col - 1, loc.row),
            GridLocation(loc.col, loc.row - 1),
            GridLocation(loc.col, loc.row + 1),
        ]  # E W N S

        ret: List[GridLocation] = []
        for k in neighbors:
            if grid.passable_and_in_bounds(k):
                ret.append(k)

        return ret

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=4096, ttl=600))
    def get_sorted_neighbours_cached(self, goal: GridLocation, current_location: GridLocation) -> List[GridLocation]:
        # logger.debug(f"NOT IN CACHE: {current_location=}, {goal=}")

        grid: SquareGrid = self

        sorted_neighbors: List[GridLocation] = sorted(
            grid.allowed_neighbors(current_location), key=lambda x: grid.manhattan_heuristic(x, goal), reverse=True
        )
        return sorted_neighbors

    @cachetools.cached(cache=cachetools.TTLCache(maxsize=4096, ttl=600))
    def manhattan_heuristic(self, a: GridLocation, b: GridLocation) -> int:
        (x1, y1) = a
        (x2, y2) = b
        return abs(x1 - x2) + abs(y1 - y2)

    @staticmethod
    def from_walls_onezero_array(dimension: Dimension, walldatastr: List[str]) -> SquareGrid:
        ret: SquareGrid = SquareGrid(dimension)

        walls: List[GridLocation] = []

        for row_c, row in enumerate(walldatastr):
            for col_c, col in enumerate(row):
                if col == "1":
                    walls.append(GridLocation(col=col_c, row=row_c))

        ret.walls = set(walls)

        return ret

    @staticmethod
    def from_excel_array(dimension: Dimension, walldata: List[str]) -> SquareGrid:
        walls: Set[GridLocation] = set([GridLocation(*extracteinfo(w)) for w in walldata])

        ret: SquareGrid = SquareGrid(dimension)
        ret.walls = walls

        return ret

    @staticmethod
    def create_random_grid(
        dimension: Dimension, obstacle_perc: float, startpos: GridLocation, endpos: GridLocation
    ) -> SquareGrid:
        walls: Set[GridLocation] = set()

        for row in range(dimension.height):
            for column in range(dimension.width):
                gl: GridLocation = GridLocation(row=row, col=column)
                if gl == startpos or gl == endpos:
                    continue

                if uniform(0, 1.0) < obstacle_perc:
                    walls.add(gl)

                # special-case: add line at the bottom aside exit
                if row == dimension.height - 1:
                    walls.add(gl)

        rgrid: SquareGrid = SquareGrid(dimension=dimension, walls=walls)

        return rgrid

    def print(
        self,
        indent: int = 0,
        start: Optional[GridLocation] = None,
        end: Optional[GridLocation] = None,
        steps: Optional[OrderedSet[GridLocation]] = None,
        costs: Optional[Dict[GridLocation, float]] = None,
        reachablemap: Optional[Set[GridLocation]] = None,
    ) -> None:

        try:
            from colorama import (  # importing here since it is only needed here => colorama is in -dev requirements
                Back,
                Fore,
            )
        except:
            return

        linecolumnwidth: int = math.floor(math.log10(self.dimension.height)) + 1
        columnwidth: int = len(to_excel(self.dimension.width)) + 1
        if costs:
            # assumes int-costs!!!
            columnwidth = max(columnwidth, max([int(math.log10(round(v))) + 1 for v in costs.values() if v > 0]) + 3)
        if steps:
            columnwidth = max(columnwidth, round(math.log10(len(steps))) + 3)

        # print(f"{columnwidth=} {linecolumnwidth=}")
        w: str = "@"
        e: str = " "
        g: str = "G"
        s: str = "S"
        # print("\N{grinning face}")
        p: str = "X"  # "\N{ATHLETIC SHOE}"
        dead: str = "\u274C"

        ind: str = " " * indent

        rccolor: str = Back.WHITE + Fore.BLACK
        rcreset: str = Fore.RESET + Back.RESET

        print(f"{ind}{' '*linecolumnwidth} ", end="")

        print(
            rccolor + "".join([f"{to_excel(col):^{columnwidth}}" for col in range(0, self.dimension.width)]) + rcreset
        )
        for row in range(0, self.dimension.height):
            print(f"{ind}{rccolor}{row + 1:0{linecolumnwidth}}{rcreset} ", end="")
            for col in range(0, self.dimension.width):
                mepoint: GridLocation = GridLocation(row=row, col=col)
                if mepoint in self.walls:
                    print(f"{Fore.RED}{w:^{columnwidth}}", end=Fore.RESET)
                elif reachablemap and not mepoint in reachablemap:
                    print(f"{Back.WHITE}{dead:^{columnwidth}}", end=Back.RESET)
                elif start and mepoint == start:
                    print(f"{Fore.BLUE}{s:^{columnwidth}}", end=Fore.RESET)
                elif end and mepoint == end:
                    print(f"{Fore.GREEN}{g:^{columnwidth}}", end=Fore.RESET)
                elif costs and mepoint in costs:
                    mc: str = f"{costs[mepoint]:.1f}"
                    print(f"{Back.BLUE}{mc:^{columnwidth}}", end=Back.RESET)
                elif steps and mepoint in steps:
                    stepnum: str = f"[{len(steps)-steps.index(mepoint)}]"
                    print(f"{Back.BLUE}{stepnum:^{columnwidth}}", end=Back.RESET)
                else:
                    print(f"{e:^{columnwidth}}", end="")
            print()

    def print_walls_array(self) -> None:
        w: GridLocation
        print("[" + ", ".join([f'"{to_excel(w.col)}{w.row + 1}"' for w in self.walls]) + "]")


def get_steps_as_excel_list(steps: OrderedSet[GridLocation]) -> List[str]:
    ret: List[str] = []

    for i in range(0, len(steps)):
        s: GridLocation = steps[len(steps) - i - 1]
        ret.append(f"{to_excel(s.col)}{s.row + 1}")
    return ret


def get_steps_as_excel(steps: OrderedSet[GridLocation]) -> str:
    ret = ""

    for i, s in enumerate(get_steps_as_excel_list(steps)):
        if i > 0:
            ret += " -> "
        ret += f"({s})"
    return ret


def backtrack_node_to_start(node: GridNode) -> Iterator[GridLocation]:
    ret: Queue[GridLocation] = Queue()
    ret.push(node.location)  # also include exit-node

    while node.parent is not None:
        node = node.parent
        ret.push(node.location)

    return iter(ret)
