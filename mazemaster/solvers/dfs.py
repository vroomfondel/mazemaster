from __future__ import annotations

from random import shuffle
from typing import  Dict, List, Optional, Set

from loguru import logger

from mazemaster.solvers.astar import AstarSolver
from mazemaster.solvers.gridmodels import (
    GridLocation,
    GridNode,
    MyStackFrame,
    SquareGrid,
    Stack,
    StartInWallException,
    StartOutOfBoundsException,
    backtrack_node_to_start,
    get_steps_as_excel_list,
)

from ordered_set import OrderedSet
from ratelimit import RateLimitException, limits


# SEE ALSO
# http://algo2.iti.kit.edu/kalp/
# https://informatika.stei.itb.ac.id/~rinaldi.munir/Stmik/2018-2019/Makalah/Makalah-Stima-2019-006.pdf

# => this solver needs tuning!!!


@limits(calls=50, period=1.0)
def _debuglog_limit(*args) -> None:  # type: ignore
    logger.debug(*args)


def debuglog_limit(*args) -> None:  # type: ignore
    try:
        logger.debug(*args)
    except RateLimitException as ex:
        # yikes.
        pass


def getmaxdict(sub_solved_maxpath: Dict[GridLocation, Dict[GridLocation, float]]) -> Dict[GridLocation, float]:
    ret: Dict[GridLocation, float] = {}
    for k in sub_solved_maxpath.keys():
        subdict: Optional[Dict[GridLocation, float]] = sub_solved_maxpath.get(k)
        if subdict:
            ret[k] = max([v for v in subdict.values()])

    return ret


def getmax(
    sub_solved_maxpath: Dict[GridLocation, Dict[GridLocation, float]], base_node: GridLocation
) -> Optional[float]:
    subdict: Optional[Dict[GridLocation, float]] = sub_solved_maxpath.get(base_node)
    if subdict:
        return max([v for v in subdict.values()])

    return None


class DFSSolver:
    _debugprint: bool = True  # DFSSolver is WIP!

    @staticmethod
    def search_all_available_exits(grid: SquareGrid, start: GridLocation) -> List[GridNode]:
        raise NotImplementedError()

    @staticmethod
    def search_shortest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        raise NotImplementedError()

    @staticmethod
    def search_longest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        """brute-forcing with O(n*m) time/space-complexity (space probably more since i carry some stuff around ;-) )"""
        if start in grid.walls:
            raise StartInWallException("invalid start location => start is in wall")

        if start.col < 0 or start.row >= grid.dimension.width:
            raise StartOutOfBoundsException("invalid start location => start is out of bounds")

        startnode: GridNode = GridNode(
            location=start, parent=None, cost=0.0, heuristic=grid.manhattan_heuristic(start, goal)
        )

        overall_pathfound_longest: Optional[GridNode] = None

        frontier: Stack[MyStackFrame] = Stack()

        reachablemap: Set[GridLocation] = AstarSolver.create_reachable_map_min(grid=grid, goal=goal)

        sub_solved_maxpath: Dict[GridLocation, Dict[GridLocation, float]] = {}  # base_nodeloc -> next_nodeloc,float

        frontier.push(MyStackFrame(base_node=startnode, stackdepth=1))
        goalcount: int = 0

        whilecount: int = 0
        #############
        while not frontier.is_empty():
            whilecount = whilecount + 1
            stackframe: MyStackFrame = frontier.pop()
            base_node: GridNode = stackframe.base_node
            recurdepth: int = stackframe.stackdepth
            current_location: GridLocation = base_node.location

            steps: OrderedSet[GridLocation]

            if DFSSolver._debugprint and whilecount % 250_000 == 0:
                logger.debug(
                    "(LOOPINFO) goalcount={} recurdepth={} len(sub_solved_maxpath)={} base_node.cost={} base_node={} len(frontier)={} whilecount={}".format(
                        goalcount,
                        recurdepth,
                        len(sub_solved_maxpath),
                        int(base_node.cost),
                        base_node,
                        len(frontier),
                        whilecount,
                    )
                )

                if overall_pathfound_longest:
                    steps = OrderedSet(backtrack_node_to_start(overall_pathfound_longest))
                    grid.print(
                        indent=8,
                        start=start,
                        end=overall_pathfound_longest.location,
                        steps=steps,
                        costs=getmaxdict(sub_solved_maxpath),
                        reachablemap=reachablemap,
                    )

                    print("WALLS: ", end="")
                    grid.print_walls_array()
                    print(f"CURRENT_LONGEST_PATH: {get_steps_as_excel_list(steps)}")

            if recurdepth >= 1000 or whilecount >= 100_000_000:
                logger.debug("BREAKING")
                if overall_pathfound_longest:
                    steps = OrderedSet(backtrack_node_to_start(overall_pathfound_longest))
                    grid.print(
                        indent=8,
                        start=start,
                        end=overall_pathfound_longest.location,
                        steps=steps,
                        costs=getmaxdict(sub_solved_maxpath),
                    )

                break

            if goal == current_location:
                goalcount += 1
                if not overall_pathfound_longest or overall_pathfound_longest.cost < base_node.cost:
                    overall_pathfound_longest = base_node

                # backtrack solution into sub_solved_maxpath
                backtrack_node: Optional[GridNode] = base_node
                while backtrack_node:
                    parentlocation: GridLocation
                    if not backtrack_node.parent:
                        parentlocation = GridLocation(-1, -1)
                    else:
                        parentlocation = backtrack_node.parent.location

                    subdict: Optional[Dict[GridLocation, float]] = sub_solved_maxpath.get(parentlocation)
                    if not subdict:
                        subdict = {}
                        sub_solved_maxpath[parentlocation] = subdict

                    has_solution: Optional[float] = subdict.get(backtrack_node.location)
                    if not has_solution or has_solution < backtrack_node.cost:
                        subdict[backtrack_node.location] = backtrack_node.cost

                    backtrack_node = backtrack_node.parent

                if DFSSolver._debugprint:
                    debuglog_limit(
                        "(GOALINFO) goalcount={} recurdepth={} len(sub_solved_maxpath)={} base_node.cost=={} base_node={} len(frontier)={} whilecount={}".format(
                            goalcount,
                            recurdepth,
                            len(sub_solved_maxpath),
                            base_node.cost,
                            base_node,
                            len(frontier),
                            whilecount,
                        )
                    )

                    steps = OrderedSet(backtrack_node_to_start(overall_pathfound_longest))
                    grid.print(
                        indent=8,
                        start=start,
                        end=overall_pathfound_longest.location,
                        steps=steps,
                        costs=getmaxdict(sub_solved_maxpath),
                    )

                    print(get_steps_as_excel_list(steps))

                continue

            # visited.add(current_location)

            sorted_neighbors: List[GridLocation] = grid.get_sorted_neighbours_cached(
                current_location=current_location, goal=goal
            )
            shuffled_neighbors: List[GridLocation] = sorted_neighbors.copy()
            shuffle(shuffled_neighbors)

            for neighbor in shuffled_neighbors:
                if base_node.has_visited(neighbor):
                    # i was here already myself
                    continue

                neigh_heuristic: int = grid.manhattan_heuristic(neighbor, goal)
                neigh_cost: float = base_node.cost + 1

                neigh_has_solution: Optional[float] = None
                cur_subdict: Optional[Dict[GridLocation, float]] = sub_solved_maxpath.get(current_location)
                if cur_subdict:
                    neigh_has_solution = cur_subdict.get(neighbor)

                if (
                    neigh_has_solution and neigh_has_solution > neigh_cost
                ):  # this might be an optimization in favor of missing "some" paths
                    # skip this "too cheap" path
                    continue

                neighbor_node: GridNode = GridNode(
                    location=neighbor, parent=base_node, cost=neigh_cost, heuristic=neigh_heuristic
                )

                frontier.push(MyStackFrame(base_node=neighbor_node, stackdepth=recurdepth + 1))

        #############

        return overall_pathfound_longest
