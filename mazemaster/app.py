import asyncio
import os
from typing import Any, Dict, List, Optional, Union

from fastapi import Depends, FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse, PlainTextResponse
from loguru import logger

from mazemaster import routers

import mazemaster.utils.configuration as conf


from .utils.configuration import settings


__app_description = """
API-design for a maze solving system. Mazes may only have one exit; reaching the exit is defined as "reaching the last line in the maze".

Mazes may be solved with "minimum" steps and Mazes may be solved with "maximum" steps.
 
- Used this to test the basis from the fastapi-demo-app ( https://github.com/vroomfondel/vendingmachine )
- Used this to try out https://web.deta.sh/ as a simple demo-runtime-platform.
- Used this to bang my head against the wall about a proper/tuned (non-recursive) DFS-longest-path implementation

Tried to adhere:
- GET	A GET method (or GET request) is used to retrieve a representation of a resource. It should be used SOLELY for retrieving data and should not alter.
- PUT	A PUT method (or PUT request) is used to update a resource. For instance, if you know that a blog post resides at http://www.example.com/blogs/123, you can update this specific post
- by using the PUT method to put a new resource representation of the post.
- POST	A POST method (or POST request) is used to create a resource. For instance, when you want to add a new blog post but have no idea
- where to store it, you can use the POST method to post it to a URL and let the server decide the URL.
- PATCH	A PATCH method (or PATCH request) is used to modify a resource. It contains the changes to the resource, instead of the complete resource.
- DELETE	A DELETE method (or DELETE request) is used to delete a resource identified by a URI.

"""

__app_tags_metadata: List[Dict[str, Any]] = []


app = FastAPI(
    title="FastapiMazemaster",
    description=__app_description,
    version="0.0.1",
    contact={"name": "Henning Thieß", "url": "https://github.com/vroomfondel"},
    license_info={"name": "MIT", "url": "https://github.com/vroomfondel/mazemaster/LICENSE.txt"},
    openapi_tags=__app_tags_metadata,
)


# deta does not trigger on startup-event (anymore?!)


@app.on_event("startup")
async def startup_event() -> None:
    if conf._startup_event_called:
        return None

    conf._startup_event_called = True

    logger.info("Calling startup event")

    from mazemaster.datastructures.models_and_schemas import KeyDesignation
    from mazemaster.utils import auth

    logger.debug(f"DETA_RUNTIME_DETECTED: {settings.deta_runtime_detected()}")
    logger.debug(f"TIMZEONE SET: {settings.TZ} || {os.getenv('TZ')}")

    if settings.JWT_KEYID == "AUTO":  # AUTO-setting matching keyid if KEYID is set to "AUTO"
        kdes: KeyDesignation = KeyDesignation[settings.JWT_ALGORITHM]
        keyid: Optional[str] = await auth.retrieve_AUTO_keyid(kdes)
        if not keyid:
            raise RuntimeError(f"Key with ID {keyid} and designation {kdes.value} not found.")
        settings.JWT_KEYID = keyid  # overwrite with selected...
        logger.info(f"AUTO-SELECTED KEYID={keyid} for JWT_ALGORITHM={kdes}")


if settings.deta_runtime_detected():
    conf._startup_event_callable = startup_event

app.include_router(routers.users, prefix="")

app.include_router(routers.mazes, prefix="/maze")


def _wants_explicitly_json_response(request: Request) -> bool:
    ah: Optional[str] = request.headers.get("Accept")
    if ah and ah == "application/json":
        return True
    return False


@app.get("/healthz", tags=["k8s"])  # health-ping-endpoint | e.g. for k8s-deployment
async def healthz(
    wants_explicitly_json_response: bool = Depends(_wants_explicitly_json_response),
) -> Union[JSONResponse, PlainTextResponse]:
    """retuns alive => to be used as liveness-probe"""
    if wants_explicitly_json_response:
        return JSONResponse(content=jsonable_encoder({"status": "alive"}))
    else:
        # assuming plain/text
        return PlainTextResponse(content="status: alive")


@app.get("/ready", tags=["k8s"])  # ready-ping-endpoint | e.g. for k8s-deployment
async def health(
    wants_explicitly_json_response: bool = Depends(_wants_explicitly_json_response),
) -> Union[JSONResponse, PlainTextResponse]:
    """retuns ready => to be used as ready-probe"""
    if wants_explicitly_json_response:
        return JSONResponse(content=jsonable_encoder({"status": "ready"}))
    else:
        # assuming plain/text
        return PlainTextResponse(content="status: ready")


# include ROOT/static-routers last..
app.include_router(routers.ROOT)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("Calling shutdown event")
