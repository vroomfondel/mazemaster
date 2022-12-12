from __future__ import annotations

from typing import Dict, List, Optional, Set

from loguru import logger

from mazemaster.solvers.gridmodels import (
    GoalInWallException,
    GoalOutOfBoundsException,
    GridLocation,
    GridNode,
    PriorityQueue,
    SquareGrid,
    StartInWallException,
    StartOutOfBoundsException,
)


class AstarSolver:
    @staticmethod
    def search_all_available_exits(grid: SquareGrid, start: GridLocation) -> List[GridNode]:
        """special case when exit is not defined, but exit is on the bottom most line"""
        if start in grid.walls:
            raise StartInWallException("invalid start location => start is in wall")

        if start.col < 0 or start.row >= grid.dimension.width:
            raise StartOutOfBoundsException("invalid start location => start is out of bounds")

        goalline: int = grid.dimension.height - 1
        current_pseudo_goal: GridLocation = GridLocation(col=start.col, row=goalline)  # same col, last row
        # worklist
        frontier: PriorityQueue[GridNode] = PriorityQueue()
        frontier.put(
            0.0,
            GridNode(
                location=start, parent=None, cost=0.0, heuristic=grid.manhattan_heuristic(start, current_pseudo_goal)
            ),
        )

        ret: List[GridNode] = []  # return empty list if no exit found

        explored: Dict[GridLocation, float] = {}

        # keep going while there is more to explore
        while not frontier.is_empty():
            current_node: GridNode
            prio: float
            prio, current_node = frontier.pop()
            # logger.debug(f"{prio=} {current_node=}")

            current_location: GridLocation = current_node.location

            current_pseudo_goal = GridLocation(col=current_location.col, row=goalline)  # same col, last row

            if current_location.row == current_pseudo_goal.row and current_location.col == current_pseudo_goal.col:
                ret.append(current_node)

            # check next
            for neighbor in grid.allowed_neighbors(current_location):
                neigh_pseudo_goal: GridLocation = GridLocation(col=neighbor.col, row=goalline)  # same col, last row

                neigh_heuristic: int = grid.manhattan_heuristic(
                    neighbor, neigh_pseudo_goal
                )  # might cause over-estimation!!!
                neigh_cost: float = current_node.cost + 1

                if neighbor not in explored or explored[neighbor] > neigh_cost:
                    explored[neighbor] = neigh_cost  # found a faster path...
                    frontier.put(
                        neigh_cost,  # + heuristic not needed since __lt__ is defined in GridNode for PriorityQueue
                        GridNode(location=neighbor, parent=current_node, cost=neigh_cost, heuristic=neigh_heuristic),
                    )

        return ret

    @staticmethod
    def is_deadend(
        grid: SquareGrid, start_location: GridLocation, visited: Set[GridLocation], goal: GridLocation
    ) -> bool:
        logger.debug("uncached...")
        # no sanity-checks done here!!!

        # worklist
        frontier: PriorityQueue[GridNode] = PriorityQueue()
        frontier.put(
            0.0,
            GridNode(
                location=start_location, parent=None, cost=0.0, heuristic=grid.manhattan_heuristic(start_location, goal)
            ),
        )

        explored: Dict[GridLocation, float] = {}

        # keep going while there is more to explore
        while not frontier.is_empty():
            current_node: GridNode
            prio: float
            prio, current_node = frontier.pop()

            current_location: GridLocation = current_node.location
            if current_location == goal:
                return False

            # check next
            for neighbor in grid.allowed_neighbors(current_location):
                if neighbor in visited:
                    continue

                neigh_heuristic: int = grid.manhattan_heuristic(neighbor, goal)
                neigh_cost: float = current_node.cost + 1

                if neighbor not in explored or explored[neighbor] > neigh_cost:
                    explored[neighbor] = neigh_cost  # found a faster path...
                    frontier.put(
                        neigh_cost,
                        # + heuristic not needed since __lt__ is defined in GridNode for PriorityQueue
                        GridNode(location=neighbor, parent=current_node, cost=neigh_cost, heuristic=neigh_heuristic),
                    )

        return True

    @staticmethod
    def create_reachable_map_min(grid: SquareGrid, goal: GridLocation) -> Set[GridLocation]:
        ret: Set[GridLocation] = set()

        if goal in grid.walls:
            raise GoalInWallException("invalid goal location => start is in wall")

        if goal.col < 0 or goal.row >= grid.dimension.width:
            raise GoalOutOfBoundsException("invalid start location => start is in wall")

        for row in range(0, grid.dimension.height):
            for col in range(0, grid.dimension.width):
                start: GridLocation = GridLocation(col=col, row=row)

                if start in grid.walls or start.col < 0 or start.row >= grid.dimension.width:
                    continue

                found: Optional[GridNode] = AstarSolver.search_shortest_path(grid=grid, start=start, goal=goal)
                if found:
                    ret.add(start)

        return ret

    @staticmethod
    def search_shortest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        if start in grid.walls:
            raise StartInWallException("invalid start location => start is in wall")

        if start.col < 0 or start.row >= grid.dimension.width:
            raise StartOutOfBoundsException("invalid start location => start is out of bounds")

        # worklist
        frontier: PriorityQueue[GridNode] = PriorityQueue()
        frontier.put(
            0.0, GridNode(location=start, parent=None, cost=0.0, heuristic=grid.manhattan_heuristic(start, goal))
        )

        explored: Dict[GridLocation, float] = {}

        # keep going while there is more to explore
        while not frontier.is_empty():
            current_node: GridNode
            prio: float
            prio, current_node = frontier.pop()

            current_location: GridLocation = current_node.location
            if current_location.row == goal.row and current_location.col == goal.col:
                return current_node

            # check next
            for neighbor in grid.allowed_neighbors(current_location):
                neigh_heuristic: int = grid.manhattan_heuristic(neighbor, goal)
                neigh_cost: float = current_node.cost + 1

                if neighbor not in explored or explored[neighbor] > neigh_cost:
                    explored[neighbor] = neigh_cost  # found a faster path...
                    frontier.put(
                        neigh_cost,
                        # + heuristic not needed since __lt__ is defined in GridNode for PriorityQueue
                        GridNode(location=neighbor, parent=current_node, cost=neigh_cost, heuristic=neigh_heuristic),
                    )

        return None

    @staticmethod
    def search_longest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        raise NotImplementedError()
