from __future__ import annotations

import asyncio
from asyncio import AbstractEventLoop
from concurrent.futures import Future, ThreadPoolExecutor
from threading import Semaphore
from typing import Any, List, Literal, Optional, Tuple, Union, cast

from loguru import logger

from mazemaster.datastructures.models_and_schemas import (
    ExcelCoordinate,
    Maze,
    MazeSolution,
    MazeSolutionStatus,
)
from mazemaster.solvers.bfs import BFSSolver
from mazemaster.solvers.dfs import DFSSolver
from mazemaster.solvers.gridmodels import (
    Dimension,
    GridLocation,
    GridNode,
    SolverProtocol,
    SquareGrid,
    StartInWallException,
    StartOutOfBoundsException,
    backtrack_node_to_start,
    extracteinfo,
    get_steps_as_excel_list,
    to_excel,
)

import anyio
from anyio import Lock
from ordered_set import OrderedSet


solution_workers_max: int = 3
solution_tasks_max_in_queue: int = 2
semaphore: Semaphore = Semaphore(solution_tasks_max_in_queue)

_maze_process_check_lock = Lock()

executor: Optional[ThreadPoolExecutor] = None
try:
    executor = ThreadPoolExecutor(solution_workers_max)
    logger.debug(f"ThreadPoolExecutor successfully instantiated with max. {solution_workers_max} threads")
except Exception as ex:
    logger.exception("ThreadPoolExecutor could not be instantiated", exception=ex)


class TooManySolutionsProcessingException(Exception):
    def __init__(self, *args) -> None:  # type: ignore
        super().__init__(*args)


async def solver(
    solution: MazeSolution,
    maze: Maze,
    steps: Literal["min", "max"],
    solverimpl_min: SolverProtocol,
    solverimpl_max: SolverProtocol,
) -> Optional[List[ExcelCoordinate]]:
    ret: Optional[List[ExcelCoordinate]] = None

    width, height = maze.get_grid_size_as_int_tuple()
    dim: Dimension = Dimension(width=width, height=height)
    grid: SquareGrid = SquareGrid.from_excel_array(dimension=dim, walldata=[str(k) for k in maze.walls])

    if solution.status == MazeSolutionStatus.NEW:
        solution.status = MazeSolutionStatus.PROCESSING
        await solution.save()

        exits: Optional[List[GridNode]] = None

        if dim.width <= 0 or dim.height <= 1:
            solution.status = MazeSolutionStatus.INVALID_GEOMETRY
            await solution.save()  # reload into self.dict ?!
            return None

        try:
            exits = solverimpl_min.search_all_available_exits(
                grid=grid, start=GridLocation(*extracteinfo(maze.entrance))
            )  # maze.entrance.value)))
        except StartOutOfBoundsException as oob:
            logger.exception("start is out of bounds", exception=oob)
            solution.status = MazeSolutionStatus.INVALID_ENTRY_OUTOFBOUNDS
        except StartInWallException as iw:
            logger.exception("start is in wall", exception=iw)
            solution.status = MazeSolutionStatus.INVALID_ENTRY_INWALL
        except Exception as ex:
            logger.exception("undefined error", exception=ex)
            solution.status = MazeSolutionStatus.SYSTEM_FAIL

        if exits and len(exits) == 1:
            solution.status = MazeSolutionStatus.SOLVED_MIN
            solution.detected_exit = ExcelCoordinate(f"{to_excel(exits[0].location.col)}{exits[0].location.row+1}")

            _steps_ordered_set: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exits[0]))
            _steps_excel: List[str] = get_steps_as_excel_list(_steps_ordered_set)

            solution.solution_min = [ExcelCoordinate(k) for k in _steps_excel]
        elif exits and len(exits) == 0:
            solution.status = MazeSolutionStatus.INVALID_NOEXIT
        elif exits and len(exits) > 1:
            solution.status = MazeSolutionStatus.INVALID_MULTIEXIT

        await solution.save()  # reload into self.dict ?!

    if steps == "min" and (
        solution.status == MazeSolutionStatus.SOLVED_MIN
        or solution.status == MazeSolutionStatus.SOLVED_MAX
        or solution.status == MazeSolutionStatus.FAILED_MAX
    ):
        ret = solution.solution_min
    elif steps == "max" and solution.status == MazeSolutionStatus.SOLVED_MAX:
        ret = solution.solution_max
    elif solution.detected_exit and steps == "max" and solution.status == MazeSolutionStatus.SOLVED_MIN:
        solution.status = MazeSolutionStatus.PROCESSING
        await solution.save()

        goal: GridLocation = GridLocation(*extracteinfo(solution.detected_exit))  # .value))
        start: GridLocation = GridLocation(*extracteinfo(maze.entrance))  # .value))
        exit_grid_node: Optional[GridNode] = None

        try:
            exit_grid_node = solverimpl_max.search_longest_path(grid=grid, start=start, goal=goal)
        except Exception as eex:
            logger.exception("undefined error", exception=eex)

        if exit_grid_node:
            solution.status = MazeSolutionStatus.SOLVED_MAX
            # saved: MazeSolution = await solution.save()  # could even save twice here...

            steps_ordered_set: OrderedSet[GridLocation] = OrderedSet(backtrack_node_to_start(exit_grid_node))
            steps_excel: List[str] = get_steps_as_excel_list(steps_ordered_set)

            solution.solution_max = [ExcelCoordinate(k) for k in steps_excel]
            await solution.save()  # reload into self.dict ?!

            ret = solution.solution_max
        else:
            solution.status = MazeSolutionStatus.FAILED_MAX
            await solution.save()

    return ret


def maze_solution_calculation_done(future: Future) -> None:
    global semaphore
    logger.debug(f"{future.cancelled()=} {future.done()=} {future.result()=}")
    semaphore.release()


async def trigger_solver(
    solution: MazeSolution, maze: Maze, steps: Literal["min", "max"]
) -> Optional[Union[Future, List[ExcelCoordinate]]]:
    global semaphore, executor, _maze_process_check_lock

    solverimpl_min: SolverProtocol = BFSSolver  # or Astar
    solverimpl_max: SolverProtocol = DFSSolver

    if solution.status == MazeSolutionStatus.PROCESSING:
        logger.debug(f"Already processing: {maze.hash=} {steps=}")
        return None

    if not executor:  # could be if deta-runtime does not allow a threadpool-executor
        path: Optional[List[ExcelCoordinate]] = await solver(
            solution=solution, maze=maze, steps=steps, solverimpl_min=solverimpl_min, solverimpl_max=solverimpl_max
        )
        return path
    else:
        proceed: bool = semaphore.acquire(blocking=False)

        if not proceed:
            raise TooManySolutionsProcessingException(
                "There are already too many mazes trying to be solved... please come back later..."
            )

        future: Future[Optional[List[ExcelCoordinate]]] = executor.submit(asyncio.run, solver(solution=solution, maze=maze, steps=steps, solverimpl_min=solverimpl_min, solverimpl_max=solverimpl_max))  # type: ignore
        future.add_done_callback(maze_solution_calculation_done)
        logger.debug(f"Added solver for maze {maze.hash=} with {steps=} to threadpool...")

        return future
