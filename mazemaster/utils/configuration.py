import os
import pathlib
import sys
from pathlib import Path
from typing import Literal, Optional, Callable

from loguru import logger
from pydantic import BaseSettings, Field

import pytz


mepath: pathlib.Path = pathlib.Path(__file__)
medir: pathlib.Path = mepath.parent
parentdir: pathlib.Path = medir.parent
startdir: pathlib.Path = parentdir.parent


class Settings(BaseSettings):
    # https://pydantic-docs.helpmanual.io/usage/settings/
    JWT_TOKEN_URL: str = Field(default="/login")  # /users/token")
    JWT_KEYID: str = Field(default="AUTO")
    JKU_URL: Optional[str] = Field(default="AUTO")
    JWT_ALGORITHM: Literal["HS256", "RS256"] = Field(default="RS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = Field(default=10080)  # 1w
    LOGURU_LEVEL: str = Field(default="DEBUG")  # explicitely setting log-level to DEBUG if not set in ENV
    TZ: str = Field(default="Europe/Berlin")  # explicitely setting TZ in ENV to Europe/Berlin if unset
    DETA_RUNTIME: str = Field(default="False")
    DETA_PROJECT_KEY: Optional[str]
    PASSWORD_PATTERN: str = Field(default=r"^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).*$")
    USERNAME_PATTERN: str = Field(default=r"^(?=.*?[A-Z])(?=.*?[a-z]|[-]).*$")
    GRIDSIZE_PATTERN: str = Field(default=r"^([1-9]\d*)x(?=[2-9]|[1-9][0-9])(\d*)$")

    def deta_runtime_detected(self) -> bool:
        print(f"{self.DETA_RUNTIME=}")
        return self.DETA_RUNTIME == "true"

    class Config:
        case_sensitive = True
        env_file = Path(startdir, ".detaSECRET")  # can be multiple files -> os.ENV has priority!


# deta-related "workaround"
_startup_event_called: bool = False
_startup_event_callable: Optional[Callable] = None

settings: Settings = Settings(TZ="Europe/Berlin")
if settings.deta_runtime_detected():
    logger.debug("DETA RUNTIME DETECTED.")

os.environ["TZ"] = settings.TZ
pytz.timezone(settings.TZ)  # ensure via error-raise, that TZ actually exists and is well-understood


logger.remove()
logger.add(sys.stderr, level=settings.LOGURU_LEVEL)
logger.debug(f"{mepath=}\n{medir=}\n{parentdir=}\n{startdir=}")
