import asyncio
import json
import os
import platform
from typing import Generator, Tuple
from uuid import UUID

from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from loguru import logger

from mazemaster.app import app, shutdown_event, startup_event
from mazemaster.utils.configuration import settings

import pytest
from httpx import AsyncClient, Response


if not settings.DETA_PROJECT_KEY:
    print("DETA_PROJECT_KEY NOT SET AND IS NEEDED FOR 'DETA-BASE' -> FAIL")
    print("TO GET ONE FOR FREE (AT THE MOMENT AT LEAST) HOP OVER TO: https://docs.deta.sh/docs/base/about")
    exit(123)


@pytest.fixture(scope="session")
def anyio_backend():
    """needed to also session-scope the anyio-backend"""
    return "trio"  # backend == asyncio causes report-errors in conjunction with python 3.9 and exceptiongroups


# This is the same as using the @pytest.mark.anyio on all test functions in the module
pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
async def fapi() -> FastAPI:
    logger.disable("mazemaster")  # muting logger for everything in+below mazemaster-package

    fapi = app

    await startup_event()

    @fapi.get("/exceptme")  # exception-ping-endpoint
    async def exceptme() -> None:
        raise HTTPException(detail="intentionally thrown", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    yield fapi

    await shutdown_event()
    ## teardown-code for fapp goes here


@pytest.fixture(scope="session")
async def fastapi_client(fapi: FastAPI) -> AsyncClient:  # TestClient:
    return AsyncClient(app=fapi, base_url="http://test")


@pytest.fixture(scope="module")
async def get_new_access_token(
    fastapi_client: AsyncClient, create_user_modulescoped: Tuple[str, str, str, UUID]
) -> str:

    refresh_request_json: dict = {"refresh_token": create_user_modulescoped[1]}

    refresh_response: Response = await fastapi_client.post(
        "/token/refresh",
        headers={"Authorization": f"Bearer {create_user_modulescoped[0]}", "content-type": "application/json"},
        json=refresh_request_json,
    )

    refresh_response_json: dict = refresh_response.json()
    logger.trace("RESPONSE::")
    logger.trace(json.dumps(refresh_response_json, indent=4, default=str))

    assert refresh_response.status_code == status.HTTP_201_CREATED
    assert "access_token" in refresh_response_json
    assert "refresh_token" in refresh_response_json
    assert "token_type" in refresh_response_json and refresh_response_json["token_type"] == "bearer"

    new_access_token: str = refresh_response_json["access_token"]

    return new_access_token


@pytest.fixture(scope="module")
async def create_user_modulescoped(fastapi_client: AsyncClient) -> Tuple[str, str, str, UUID]:
    """returns tuple (access_token, refresh_token, username, userid)"""
    pf: str = f"{platform.node()}-{os.getpid()}!"
    username: str = f"PyTest-MAZERMOD-{pf}"
    password: str = "MEissECRE4ddd!"
    response: Response = await fastapi_client.post(
        "/user",
        json={"username": username, "password": password},
        headers={"content-type": "application/json"},
    )

    # logger.trace(response.text)
    response_data = response.json()
    # logger.trace(response_data)

    assert response.status_code == 201
    assert "username" in response_data and response_data["username"] == username
    assert "id" in response_data

    userid: UUID = UUID(response_data["id"])

    response = await fastapi_client.post(
        "/login",
        data={"username": username, "password": password, "grant_type": "password"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    # print(response_data)
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "token_type" in response_data and response_data["token_type"] == "bearer"

    yield response_data["access_token"], response_data["refresh_token"], username, userid

    response_del: Response = await fastapi_client.delete(
        "/me", headers={"Authorization": f"Bearer {response_data['access_token']}"}
    )


@pytest.fixture(scope="session")
async def create_user(fastapi_client: AsyncClient) -> Tuple[str, str, str, UUID]:
    """returns tuple (access_token, refresh_token, username, userid)"""
    pf: str = f"{platform.node()}-{os.getpid()}!"
    username: str = f"PyTest-MAZER-{pf}"
    password: str = "MEissECRE4ddd!"
    response: Response = await fastapi_client.post(
        "/user",
        json={"username": username, "password": password},
        headers={"content-type": "application/json"},
    )

    # logger.trace(response.text)
    response_data = response.json()
    # logger.trace(response_data)

    assert response.status_code == 201
    assert "username" in response_data and response_data["username"] == username
    assert "id" in response_data

    userid: UUID = UUID(response_data["id"])

    response = await fastapi_client.post(
        "/login",
        data={"username": username, "password": password, "grant_type": "password"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    # print(response_data)
    assert "access_token" in response_data
    assert "refresh_token" in response_data
    assert "token_type" in response_data and response_data["token_type"] == "bearer"

    yield response_data["access_token"], response_data["refresh_token"], username, userid

    response_del: Response = await fastapi_client.delete(
        "/me", headers={"Authorization": f"Bearer {response_data['access_token']}"}
    )
