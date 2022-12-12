import json
from typing import List, Optional, Set, Tuple
from uuid import UUID

from fastapi import status
from fastapi.testclient import TestClient
from loguru import logger

from mazemaster.datastructures.models_and_schemas import MazeInput

import pytest
from httpx import AsyncClient, Response


# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio

mazeinput: dict = {
    "grid_size": "8x8",
    "entrance": "A1",
    "walls": [
        "C1",
        "G1",
        "A2",
        "C2",
        "E2",
        "G2",
        "C3",
        "E3",
        "B4",
        "C4",
        "E4",
        "F4",
        "G4",
        "B5",
        "E5",
        "B6",
        "D6",
        "E6",
        "G6",
        "H6",
        "B7",
        "D7",
        "G7",
        "B8",
    ],
}
mazesolution: List[str] = ["A1", "B1", "B2", "B3", "A3", "A4", "A5", "A6", "A7", "A8"]
mazesolution_max: List[str] = ["A1", "B1", "B2", "B3", "A3", "A4", "A5", "A6", "A7", "A8"]


mazeinput2: dict = {
    "grid_size": "10x10",
    "entrance": "A1",
    "walls": [
        "E4",
        "E10",
        "D8",
        "F5",
        "F8",
        "I4",
        "I10",
        "A6",
        "C3",
        "I7",
        "B4",
        "B10",
        "G6",
        "D1",
        "F1",
        "D10",
        "F4",
        "I3",
        "F10",
        "J8",
        "I6",
        "A2",
        "A8",
        "I9",
        "A5",
        "B6",
        "H10",
        "E2",
        "E8",
        "E5",
        "J1",
        "F6",
        "J4",
        "I2",
        "I8",
        "J10",
        "B2",
        "A4",
        "J7",
        "A7",
        "C4",
        "C10",
        "B8",
        "C7",
        "H6",
        "G4",
        "G10",
        "H9",
    ],
}
mazesolution2: List[str] = [
    "A1",
    "B1",
    "C1",
    "C2",
    "D2",
    "D3",
    "D4",
    "D5",
    "D6",
    "E6",
    "E7",
    "F7",
    "G7",
    "G8",
    "G9",
    "F9",
    "E9",
    "D9",
    "C9",
    "B9",
    "A9",
    "A10",
]
mazesolution2_max: List[str] = [
    "A1",
    "B1",
    "C1",
    "C2",
    "D2",
    "D3",
    "D4",
    "D5",
    "C5",
    "C6",
    "D6",
    "D7",
    "E7",
    "F7",
    "G7",
    "H7",
    "H8",
    "G8",
    "G9",
    "F9",
    "E9",
    "D9",
    "C9",
    "B9",
    "A9",
    "A10",
]

# access_token, refresh_token, username, use
@pytest.fixture(scope="module")
async def maze_create(
    fastapi_client: AsyncClient, create_user_modulescoped: Tuple[str, str, str, UUID]
) -> Tuple[int, UUID, str]:

    response_post: Response = await fastapi_client.post(
        "/maze",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}", "content-type": "application/json"},
        json=mazeinput,  # here, not really necessary to dump and re-load
    )

    response_post_json: dict = response_post.json()

    assert response_post.status_code == status.HTTP_201_CREATED
    assert UUID(response_post_json["owner_id"]) == create_user_modulescoped[3]
    assert response_post_json["hash"] == MazeInput(**mazeinput).get_maze_hash()
    assert int(response_post_json["mazenum"]) == 1
    assert "id" in response_post_json

    return 1, UUID(response_post_json["id"]), response_post_json["hash"]


@pytest.fixture(scope="module")
async def maze_create2(
    fastapi_client: AsyncClient, create_user_modulescoped: Tuple[str, str, str, UUID]
) -> Tuple[int, UUID, str]:

    response_post: Response = await fastapi_client.post(
        "/maze",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}", "content-type": "application/json"},
        json=mazeinput2,  # here, not really necessary to dump and re-load
    )

    response_post_json: dict = response_post.json()
    logger.debug(response_post_json)

    assert response_post.status_code == status.HTTP_201_CREATED
    assert UUID(response_post_json["owner_id"]) == create_user_modulescoped[3]
    assert response_post_json["hash"] == MazeInput(**mazeinput2).get_maze_hash()
    assert int(response_post_json["mazenum"]) == 2
    assert "id" in response_post_json

    return 2, UUID(response_post_json["id"]), response_post_json["hash"]


async def test_maze_get_by_num(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        f"/maze/{maze_create[0]}",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}"},
    )

    response_get_json: dict = response_get.json()

    assert response_get.status_code == status.HTTP_200_OK
    assert UUID(response_get_json["owner_id"]) == create_user_modulescoped[3]
    assert response_get_json["hash"] == maze_create[2]
    assert int(response_get_json["mazenum"]) == maze_create[0]
    assert UUID(response_get_json["id"]) == maze_create[1]

    inwallsset: Set = set(mazeinput["walls"])
    outwallsset: Set = set(response_get_json["walls"])

    assert len(inwallsset.symmetric_difference(outwallsset)) == 0


async def test_maze_get_by_num2(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],  # ensure first is created...
    maze_create2: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        f"/maze/{maze_create2[0]}",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}"},
    )

    response_get_json: dict = response_get.json()
    logger.debug(response_get_json)

    assert response_get.status_code == status.HTTP_200_OK
    assert UUID(response_get_json["owner_id"]) == create_user_modulescoped[3]
    assert response_get_json["hash"] == maze_create2[2]
    assert int(response_get_json["mazenum"]) == maze_create2[0]
    assert UUID(response_get_json["id"]) == maze_create2[1]

    inwallsset: Set = set(mazeinput2["walls"])
    outwallsset: Set = set(response_get_json["walls"])

    assert len(inwallsset.symmetric_difference(outwallsset)) == 0


async def test_maze_get_by_id(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        f"/maze/by-id/{maze_create[1]}",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}"},
    )

    response_get_json: dict = response_get.json()

    response_get_json: dict = response_get.json()

    assert response_get.status_code == status.HTTP_200_OK
    assert UUID(response_get_json["owner_id"]) == create_user_modulescoped[3]
    assert response_get_json["hash"] == maze_create[2]
    assert int(response_get_json["mazenum"]) == maze_create[0]
    assert UUID(response_get_json["id"]) == maze_create[1]

    inwallsset: Set = set(mazeinput["walls"])
    outwallsset: Set = set(response_get_json["walls"])

    assert len(inwallsset.symmetric_difference(outwallsset)) == 0


async def test_maze_solve_min(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        "/maze/1/solution?steps=min",
        headers={
            "Authorization": f"Bearer {create_user_modulescoped[0]}"
        },  # here, not really necessary to dump and re-load
    )

    response_get_json: dict = response_get.json()

    assert response_get.status_code == status.HTTP_200_OK
    assert response_get_json["mazehash"] == maze_create[2]  # MazeInput(**mazeinput).get_maze_hash()

    inpathset: Set = set(mazesolution)
    outpathset: Set = set(response_get_json["path"])

    assert len(inpathset.symmetric_difference(outpathset)) == 0


async def test_maze_solve_max(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        "/maze/1/solution?steps=max",
        headers={
            "Authorization": f"Bearer {create_user_modulescoped[0]}"
        },  # here, not really necessary to dump and re-load
    )

    response_get_json: dict = response_get.json()
    logger.debug(response_get_json)

    assert response_get.status_code == status.HTTP_200_OK
    assert response_get_json["mazehash"] == maze_create[2]  # MazeInput(**mazeinput).get_maze_hash()

    inpathset: Set = set(mazesolution_max)
    outpathset: Set = set(response_get_json["path"])

    assert len(inpathset.symmetric_difference(outpathset)) == 0


async def test_maze_solve_min2(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],  # to ensure numbering...
    maze_create2: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        "/maze/2/solution?steps=min",
        headers={
            "Authorization": f"Bearer {create_user_modulescoped[0]}"
        },  # here, not really necessary to dump and re-load
    )

    response_get_json: dict = response_get.json()

    assert response_get.status_code == status.HTTP_200_OK
    assert response_get_json["mazehash"] == maze_create2[2]  # MazeInput(**mazeinput).get_maze_hash()

    inpathset: Set = set(mazesolution2)
    outpathset: Set = set(response_get_json["path"])

    assert len(inpathset.symmetric_difference(outpathset)) == 0


async def test_maze_solve_max2(
    fastapi_client: AsyncClient,
    maze_create: Tuple[int, UUID, str],  # to ensure numbering...
    maze_create2: Tuple[int, UUID, str],
    create_user_modulescoped: Tuple[str, str, str, UUID],
) -> None:
    response_get: Response = await fastapi_client.get(
        "/maze/2/solution?steps=max",
        headers={
            "Authorization": f"Bearer {create_user_modulescoped[0]}"
        },  # here, not really necessary to dump and re-load
    )

    response_get_json: dict = response_get.json()

    assert response_get.status_code == status.HTTP_200_OK
    assert response_get_json["mazehash"] == maze_create2[2]  # MazeInput(**mazeinput).get_maze_hash()

    inpathset: Set = set(mazesolution2_max)
    outpathset: Set = set(response_get_json["path"])

    assert len(inpathset.symmetric_difference(outpathset)) == 0
