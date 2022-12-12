from __future__ import annotations

from mazemaster.solvers.gridmodels import Queue, Stack


# This is the same as using the @pytest.mark.anyio on all test functions in the module
# pytestmark = pytest.mark.anyio(scope="session")
def test_container():
    s: Stack[int] = Stack()
    q: Queue[int] = Queue()
    for i in range(0, 100):
        s.push(i)
        q.push(i)

    for k in s:
        print(k)

    for i in range(0, 100):
        q.push(i)

    for k in q:
        print(k)


# def test_mazehash():
#     for dim, start, wlist in walldataset:
#         walls_unsorted: List[ExcelCoordinate] = [ExcelCoordinate(k) for k in wlist]  # value=k
#         sorted_walls: List[ExcelCoordinate] = sorted(walls_unsorted)  # , key=lambda x: x.value)
#
#         entrance_excel: ExcelCoordinate = ExcelCoordinate(
#             f"{to_excel(start.col)}{start.row+1}"
#         )  # ExcelCoordinate(value=f"{to_excel(start.col)}{start.row+1}")
#
#         hash_sorted: str = Maze.static_get_maze_hash(
#             grid_size=f"{dim.width}x{dim.height}", entrance=entrance_excel, walls=sorted_walls
#         )
#         hash_unsorted: str = Maze.static_get_maze_hash(
#             grid_size=f"{dim.width}x{dim.height}", entrance=entrance_excel, walls=walls_unsorted
#         )
#
#         hash_fail: str = Maze.static_get_maze_hash(
#             grid_size=f"{dim.width+1}x{dim.height}", entrance=entrance_excel, walls=sorted_walls
#         )
#
#         hash_fail2: str = Maze.static_get_maze_hash(
#             grid_size=f"{dim.width+1}x{dim.height}",
#             entrance=entrance_excel,  # ExcelCoordinate(entrance_excel),  # + "8"),  # .value
#             walls=sorted_walls,
#         )
#
#         assert hash_unsorted == hash_sorted
#         assert hash_unsorted != hash_fail
#         assert hash_fail2 != hash_unsorted
