from __future__ import annotations

from typing import List, Optional

from mazemaster.solvers.gridmodels import (
    GridLocation,
    GridNode,
    Queue,
    SquareGrid,
    StartInWallException,
    StartOutOfBoundsException,
)


from ordered_set import OrderedSet


class BFSSolver:
    @staticmethod
    def search_all_available_exits(grid: SquareGrid, start: GridLocation) -> List[GridNode]:
        if start in grid.walls:
            raise StartInWallException("invalid start location => start is in wall")

        if start.col < 0 or start.row >= grid.dimension.width:
            raise StartOutOfBoundsException("invalid start location => start is out of bounds")

        ret: List[GridNode] = []  # empty list returned -> none found

        # worklist
        frontier: Queue[GridNode] = Queue()
        frontier.push(GridNode(location=start, parent=None))

        explored: OrderedSet[GridLocation] = OrderedSet()

        # keep going while there is more to explore
        while not frontier.is_empty():
            current_node: GridNode = frontier.pop()
            current_location: GridLocation = current_node.location

            if current_location.row == grid.dimension.height - 1:
                ret.append(current_node)
                # return ret  # to return only ONE exit at most
                # continue

            # check next
            for neighbor in grid.allowed_neighbors(current_location):
                if neighbor in explored:
                    continue

                explored.add(neighbor)

                frontier.push(GridNode(location=neighbor, parent=current_node))

        return ret

    @staticmethod
    def search_shortest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        if start in grid.walls:
            raise StartInWallException("invalid start location => start is in wall")

        if start.col < 0 or start.row >= grid.dimension.width:
            raise StartOutOfBoundsException("invalid start location => start is out of bounds")

        # worklist
        frontier: Queue[GridNode] = Queue()
        frontier.push(GridNode(location=start, parent=None))

        explored: OrderedSet[GridLocation] = OrderedSet()

        # keep going while there is more to explore
        while not frontier.is_empty():
            current_node: GridNode = frontier.pop()
            current_location: GridLocation = current_node.location

            if current_location.row == goal.row and current_location.col == goal.col:
                return current_node
                # return ret  # to return only ONE exit at most
                # continue

            # check next
            for neighbor in grid.allowed_neighbors(current_location):
                if neighbor in explored:
                    continue

                explored.add(neighbor)

                frontier.push(GridNode(location=neighbor, parent=current_node))

        return None

    @staticmethod
    def search_longest_path(grid: SquareGrid, start: GridLocation, goal: GridLocation) -> Optional[GridNode]:
        raise NotImplementedError()
