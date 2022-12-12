from __future__ import annotations

import random
from typing import List, Optional, Tuple

from mazemaster.datastructures.models_and_schemas import ExcelCoordinate
from mazemaster.solvers.astar import AstarSolver
from mazemaster.solvers.bfs import BFSSolver
from mazemaster.solvers.dfs import DFSSolver
from mazemaster.solvers.gridmodels import (
    Dimension,
    GridLocation,
    GridNode,
    SolverProtocol,
    SquareGrid,
    backtrack_node_to_start,
    extracteinfo,
    get_steps_as_excel,
    get_steps_as_excel_list,
)
from tests.walldata import walldataset

from ordered_set import OrderedSet


# This is the same as using the @pytest.mark.anyio on all test functions in the module
# pytestmark = pytest.mark.anyio(scope="session")


def _search_defined_exit_astar() -> None:
    dim, start, wlist = walldataset[0]
    goal: GridLocation = GridLocation(*extracteinfo("A8"))  # testdata!

    walls_ordered: OrderedSet[GridLocation] = OrderedSet([GridLocation(*extracteinfo(w)) for w in wlist])
    grid: SquareGrid = SquareGrid.from_excel_array(dimension=dim, walldata=wlist)

    grid.print(start=start, end=goal)

    exitnode: Optional[GridNode] = AstarSolver.search_shortest_path(grid=grid, start=start, goal=goal)
    print(
        f"Dimension(width={grid.dimension.width}, height={grid.dimension.height}), GridLocation(row={start.row}, col={start.col}"
    )
    grid.print_walls_array()

    if exitnode:
        steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exitnode))

        grid.print(indent=4, start=start, end=exitnode.location, steps=steps)
        print(get_steps_as_excel(steps))
        print("\n")


def _search_longest_defined_path() -> None:
    dim, start, wlist = walldataset[2]
    goal: GridLocation = GridLocation(*extracteinfo("A10"))  # testdata!

    walls_ordered: OrderedSet[GridLocation] = OrderedSet([GridLocation(*extracteinfo(w)) for w in wlist])
    grid: SquareGrid = SquareGrid.from_excel_array(dimension=dim, walldata=wlist)

    grid.print(start=start, end=goal)

    exitnode: Optional[GridNode] = DFSSolver.search_longest_path(grid=grid, start=start, goal=goal)
    print(
        f"Dimension(width={grid.dimension.width}, height={grid.dimension.height}), GridLocation(row={start.row}, col={start.col}"
    )
    grid.print_walls_array()

    if exitnode:
        steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exitnode))

        grid.print(indent=4, start=start, end=exitnode.location, steps=steps)
        print(get_steps_as_excel_list(steps))
        print("\n")


def get_randomly_generatd_grid(
    start: GridLocation,
    end: GridLocation,
    obstacle_perc: float = 0.4,
    dimension: Dimension = Dimension(width=8, height=8),
) -> SquareGrid:

    rgrid: SquareGrid = SquareGrid.create_random_grid(
        dimension=dimension, obstacle_perc=obstacle_perc, startpos=start, endpos=end
    )

    return rgrid


def find_all_exits(grid: SquareGrid, start: GridLocation, solver: SolverProtocol) -> List[GridNode]:
    grid.print()

    exits: List[GridNode] = solver.search_all_available_exits(grid, start)

    print(
        f"Dimension(width={grid.dimension.width}, height={grid.dimension.height}), GridLocation(row={start.row}, col={start.col}"
    )
    grid.print_walls_array()
    print(f"exits found: {len(exits)}\n\n")

    for e in exits:
        steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(e))
        grid.print(indent=4, start=start, end=e.location, steps=steps)
        print(get_steps_as_excel(steps))
        print("\n")

    return exits


def find_longest(
    grid: SquareGrid, start: GridLocation, goal: GridLocation, solver: SolverProtocol
) -> Optional[List[ExcelCoordinate]]:
    # grid.print()

    exitnode: Optional[GridNode] = solver.search_longest_path(grid, start=start, goal=goal)

    print(f"\tLONGESTPATH FOUND: {exitnode}\n\n")

    ret: Optional[List[ExcelCoordinate]] = None
    if exitnode:
        steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exitnode))
        ret = [ExcelCoordinate(k) for k in get_steps_as_excel_list(steps)]

        grid.print(indent=6, start=start, end=exitnode.location, steps=steps)
        print("Walls: ", end="")
        grid.print_walls_array()
        # print(get_steps_as_excel(steps))
        print(ret)
        print("\n")

    return ret


def makerandomrun(randomcount: int = 3) -> None:
    """runs over the walldata-testset and tries the solvers/creates solutions-map for further use
    :param randomcount => if gt 0, then random mazes are generated and tried to solve...
    """
    solvers_short: List[SolverProtocol] = [BFSSolver]  # , AstarSolver]
    solvers_long: List[SolverProtocol] = [DFSSolver]

    randsolutions: List[
        Tuple[Optional[GridLocation], int, Optional[List[ExcelCoordinate]], Optional[List[ExcelCoordinate]]]
    ] = []

    for i in range(0, randomcount):
        rdimension: Dimension = Dimension(width=10, height=10)
        rstart = GridLocation(row=0, col=0)
        rend_col_rand: int = random.randint(0, rdimension.width - 1)
        rend = GridLocation(row=rdimension.height - 1, col=rend_col_rand)  # 0 vs 1-based-index

        randgrid: SquareGrid = SquareGrid.create_random_grid(
            startpos=rstart, endpos=rend, dimension=rdimension, obstacle_perc=0.2
        )

        for solvershort in solvers_short:
            longestpath: Optional[List[ExcelCoordinate]] = None
            shortestpath: Optional[List[ExcelCoordinate]] = None
            exitloc: Optional[GridLocation] = None
            exitcount: int = -1

            print(f"WORKING ON RANDOMGRID #{i+1}")
            print(f"Trying to use {solvershort.__name__} for find all paths...")  # type: ignore

            try:
                exits: List[GridNode] = find_all_exits(randgrid, rstart, solvershort)
                exitcount = len(exits)

                if exitcount == 1:
                    steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exits[0]))
                    shortestpath = [ExcelCoordinate(k) for k in get_steps_as_excel_list(steps)]

                    exitloc = exits[0].location

                if len(exits) == 1 and exitloc:
                    for solverlong in solvers_long:
                        print(f"Trying to use {solverlong.__name__} for longest path...")  # type: ignore
                        try:
                            longestpath = find_longest(grid=randgrid, start=rstart, solver=solverlong, goal=exitloc)
                        except NotImplementedError as nie:
                            print("Longest path search not implemented for this solver...")

                randsolutions.append((exitloc, exitcount, shortestpath, longestpath))
            except NotImplementedError as nie:
                print("Find all paths search not implemented for this solver...")

            print("#" * 80)

        print("RANDOMDATA!!!\nSOLUTIONS [fitting for e.g. walldata.solutions]")
        print(randsolutions)


def makeverboserun() -> None:
    """runs over the walldata-testset and tries the solvers/creates solutions-map for further use
    :param randomcount => if gt 0, then random mazes are generated and tried to solve...
    """
    solvers_short: List[SolverProtocol] = [AstarSolver]  # BFSSolver]  # ,
    solvers_long: List[SolverProtocol] = [DFSSolver]

    solutions: List[
        Tuple[Optional[GridLocation], int, Optional[List[ExcelCoordinate]], Optional[List[ExcelCoordinate]]]
    ] = []

    for solvershort in solvers_short:
        for count in range(0, len(walldataset)):
            longestpath: Optional[List[ExcelCoordinate]] = None
            shortestpath: Optional[List[ExcelCoordinate]] = None
            exitloc: Optional[GridLocation] = None
            exitcount: int = -1

            dim, start, wlist = walldataset[count]

            print(f"WORKING ON WALLDATASET #{count}")
            print(f"Trying to use {solvershort.__name__} for find all paths...")  # type: ignore
            # walls_ordered: OrderedSet[GridLocation] = OrderedSet([GridLocation(*extracteinfo(w)) for w in wlist])
            grid: SquareGrid = SquareGrid.from_excel_array(dimension=dim, walldata=wlist)

            try:
                exits: List[GridNode] = find_all_exits(grid, start, solvershort)
                exitcount = len(exits)

                if len(exits) >= 1:
                    steps: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exits[0]))
                    shortestpath = [ExcelCoordinate(k) for k in get_steps_as_excel_list(steps)]

                    exitloc = exits[0].location

                if exitcount == 1:
                    for solverlong in solvers_long:
                        print(f"Trying to use {solverlong.__name__} for longest path...")  # type: ignore
                        try:
                            longestpath = find_longest(
                                grid=grid, start=start, solver=solverlong, goal=exits[0].location
                            )
                        except NotImplementedError as nie:
                            print("Longest path search not implemented for this solver...")

                solutions.append((exitloc, exitcount, shortestpath, longestpath))
            except NotImplementedError as nie:
                print("Find all paths search not implemented for this solver...")

            print("#" * 80)

    print(solutions)  # => can be copied to walldata.solutions and then "make lint" ;-)


if __name__ == "__main__":
    makerandomrun(randomcount=1)

    # _search_longest_defined_path()
    # ['A1', 'B1', 'C1', 'C2', 'D2', 'D3', 'E3', 'F3', 'F2', 'G2', 'G1', 'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'G7', 'G8', 'H8', 'H9', 'G9', 'F9', 'E9', 'D9', 'C9', 'B9', 'A9', 'A10']

    # _search_defined_exit_astar()

    # makeverboserun()
    # makerandomrun(randomcount=1)  # <- some occur with too many "options" -> too many loops needed
