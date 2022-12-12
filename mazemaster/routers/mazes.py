from concurrent.futures import Future
from typing import List, Literal, Optional, Union, cast
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from loguru import logger

from mazemaster.datastructures.models_and_schemas import (
    ExcelCoordinate,
    Maze,
    MazeInput,
    MazeOut,
    MazeSolution,
    MazeSolutionOut,
    MazeSolutionStatus,
    MazeUser,
)
from mazemaster.utils.auth import (
    get_current_user,
    responses_401_403_404,
    responses_401_403_404_409,
    responses_401_422,
)

from mazemaster.utils.mazesolverhelper import (
    TooManySolutionsProcessingException,
    trigger_solver,
)


router = APIRouter(tags=["mazes"])


@router.post(
    "",
    response_model=MazeOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    responses=responses_401_422,
)
async def create_maze(
    maze_data: MazeInput,
    maze_user: MazeUser = Depends(get_current_user),
) -> Maze:
    """creates a maze from input"""

    hash: str = maze_data.get_maze_hash()
    maze_already_there: Optional[Maze] = await Maze.get_maze_by_userid_and_hash(maze_user.id, hash)

    if maze_already_there:  # or return error ?! => but same is same ?!
        return maze_already_there

    # check for maze being logically valid (e.g. no|multiple exit, entrance oob, entrance in wall etc.) is made upon tried solution
    new_maze: Maze = Maze(
        owner_id=maze_user.id,
        grid_size=maze_data.grid_size,
        entrance=maze_data.entrance,
        walls=maze_data.walls,
        hash=maze_data.get_maze_hash(),
    )

    new_maze = await new_maze.create_new()  # shifts to and from DB

    return new_maze


@router.get(
    "/{mazenum}",
    response_model=MazeOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses=responses_401_403_404,
)
async def get_maze_by_mazenum(mazenum: int, maze_user: MazeUser = Depends(get_current_user)) -> Optional[Maze]:
    """get maze from user from db"""

    maze: Optional[Maze] = await Maze.get_maze_by_userid_and_mazenum(maze_user.id, mazenum)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with num {mazenum} not found for this user with userid={maze_user.id}",
        )

    return maze


@router.get(
    "/by-id/{mazeid}",
    response_model=MazeOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses=responses_401_403_404,
)
async def get_maze_by_mazeid(mazeid: UUID, maze_user: MazeUser = Depends(get_current_user)) -> Optional[Maze]:
    """get maze from user from db"""

    maze: Optional[Maze] = await Maze.get_maze_by_mazeid(mazeid)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with id={mazeid} not found for this user with userid={maze_user.id}",
        )

    if maze.owner_id != maze_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"maze with id does not belong to user id={maze_user.id}"
        )

    return maze


@router.delete(
    "/{mazenum}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=responses_401_403_404,
)
async def delete_maze_by_mazenum(mazenum: int, maze_user: MazeUser = Depends(get_current_user)) -> None:
    """get maze from user from db"""

    maze: Optional[Maze] = await Maze.get_maze_by_userid_and_mazenum(maze_user.id, mazenum)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with num {mazenum} not found for this user with userid={maze_user.id}",
        )

    await maze.delete()


@router.delete(
    "/by-id/{mazeid}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=responses_401_403_404,
)
async def delete_maze_by_mazeid(mazeid: UUID, maze_user: MazeUser = Depends(get_current_user)) -> None:
    """get maze from user from db"""

    maze: Optional[Maze] = await Maze.get_maze_by_mazeid(mazeid)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with id={mazeid} not found for this user with userid={maze_user.id}",
        )

    if maze.owner_id != maze_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"maze with id does not belong to user id={maze_user.id}"
        )

    await maze.delete()


def raise_solution_error_if_needed(solution: MazeSolution, mazehash: str, also_max_fail: bool = False) -> None:
    # structural pattern matching -> 3.10!
    if also_max_fail:
        if solution.status == MazeSolutionStatus.FAILED_MAX:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="The maze is probably too complex to be solved here... sorry :-/",
            )

    if solution.status == MazeSolutionStatus.PROCESSING:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="There is already a solving-process running... please try again later",
        )  # nevertheless, 429 does not seem fitting
    elif solution.status == MazeSolutionStatus.INVALID_MULTIEXIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The maze has more than one exit and is invalid as such.",
        )
    elif solution.status == MazeSolutionStatus.INVALID_NOEXIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The maze has no reachable exit and is invalid as such.",
        )
    elif solution.status == MazeSolutionStatus.INVALID_GEOMETRY:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The maze has no reachable exit and is invalid as such.",
        )
    elif solution.status == MazeSolutionStatus.INVALID_ENTRY_INWALL:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The entrance to the maze is in a wall and is invalid as such.",
        )
    elif solution.status == MazeSolutionStatus.INVALID_ENTRY_OUTOFBOUNDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The entrance to the maze is not even inside the maze and is invalid as such.",
        )
    elif solution.status == MazeSolutionStatus.SYSTEM_FAIL:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unfortunately, the system could not compute the solution to the maze with hash={mazehash}",
        )
    # /ugly endif-cascade


@router.get(
    "/{mazenum}/solution",
    response_model=MazeSolutionOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses=responses_401_403_404_409,
)
async def get_mazesolution_by_mazenum(
    mazenum: int, steps: Literal["min", "max"] = Query(), maze_user: MazeUser = Depends(get_current_user)
) -> Optional[MazeSolutionOut]:
    """get maze solution for maze by mazenum"""

    ret: Optional[MazeSolutionOut] = None

    maze: Optional[Maze] = await Maze.get_maze_by_userid_and_mazenum(maze_user.id, mazenum)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with num {mazenum} not found for this user with userid={maze_user.id}",
        )

    maze_hash = maze.hash

    solution: Optional[MazeSolution] = await MazeSolution.get_solution_for_maze(maze_hash)
    if not solution:
        solution = MazeSolution(mazehash=maze_hash)
        solution = await solution.create_new()

    raise_solution_error_if_needed(solution=solution, mazehash=maze_hash)

    try:
        if steps == "max":
            raise_solution_error_if_needed(solution=solution, mazehash=maze_hash, also_max_fail=True)

        if solution.solution_min and steps == "min":
            ret = MazeSolutionOut(path=solution.solution_min, mazehash=solution.mazehash)
        elif solution.solution_max and steps == "max":
            ret = MazeSolutionOut(path=solution.solution_max, mazehash=solution.mazehash)
        else:
            # also creates min-solution if missing
            res: Optional[Union[Future, List[ExcelCoordinate]]] = await trigger_solver(
                solution=solution, maze=maze, steps=steps
            )
            if res:
                path: Optional[List[ExcelCoordinate]] = None
                if type(res) == Future:
                    try:
                        path = res.result(timeout=8)  # type: ignore # 8s timeout -> deta has 10s timeout per request
                        if path:
                            ret = MazeSolutionOut(path=path, mazehash=solution.mazehash)
                    except TimeoutError as te:
                        raise HTTPException(
                            status_code=500, detail="Solution is still being processed... please come back later"
                        )
                else:
                    path = cast(List[ExcelCoordinate], res)
                    ret = MazeSolutionOut(path=path, mazehash=solution.mazehash)
            else:
                # re-read status from db
                solution = await MazeSolution.get_solution_for_maze(maze_hash)
                if solution:  # mypy
                    raise_solution_error_if_needed(
                        solution=solution, mazehash=maze_hash, also_max_fail=True if steps == "max" else False
                    )
    except TooManySolutionsProcessingException as tmspe:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(tmspe))

    return ret


@router.get(
    "/by-id/{mazeid}/solution",
    response_model=MazeSolutionOut,
    response_model_exclude_none=True,
    status_code=status.HTTP_200_OK,
    responses=responses_401_403_404_409,
)
async def get_mazesolution_by_mazeid(
    mazeid: UUID, steps: Literal["min", "max"] = Query(), maze_user: MazeUser = Depends(get_current_user)
) -> Optional[MazeSolutionOut]:
    """get maze solution for maze by id"""

    maze: Optional[Maze] = await Maze.get_maze_by_mazeid(mazeid)
    if not maze:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"maze with id={mazeid} not found for this user with userid={maze_user.id}",
        )

    if maze.owner_id != maze_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"maze with id does not belong to user id={maze_user.id}"
        )

    return await get_mazesolution_by_mazenum(mazenum=maze.mazenum, steps=steps, maze_user=maze_user)
