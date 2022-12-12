from __future__ import annotations

import datetime
import re
import string
from enum import Enum, auto
from functools import reduce
from hashlib import sha256
from re import Match, Pattern
from typing import Any, List, Optional, Tuple, cast
from uuid import UUID, uuid4

from loguru import logger
from pydantic import (
    BaseModel,
    ConstrainedStr,
    Field,
    root_validator,
    validate_model,
    validator,
)

from mazemaster.solvers.gridmodels import _excel_pattern_compiled
from mazemaster.utils.datapersistence import (
    delete_maze,
    delete_user,
    get_all_mazes_from_db_by_userid,
    get_all_users_from_db,
    get_maze_from_db_by_id,
    get_maze_from_db_by_userid_and_hash,
    get_maze_from_db_by_userid_and_mazenum,
    get_maze_solution_from_db_by_hash,
    get_user_from_db_by_id,
    get_user_from_db_by_username,
    save_maze,
    save_maze_solution,
    save_user,
)


_password_pattern = "^(?=.*?[A-Z])(?=.*?[a-z])(?=.*?[0-9])(?=.*?[#?!@$%^&*-]).*$"
_password_pattern_compiled = re.compile(_password_pattern)

_username_pattern = "^(?=.*?[A-Z])(?=.*?[a-z]|[-]).*$"  # "^(?=.*?[a-z])(?=.*?[0-9]).*$"
_username_pattern_compiled = re.compile(_username_pattern)

_gridsize_pattern: str = r"^([1-9]\d*)x([1-9]\d*)$"
_gridsize_pattern_compiled: Pattern = re.compile(_gridsize_pattern)


def from_excel(chars: str) -> int:
    return reduce(lambda r, x: r * 26 + 1 + x, map(string.ascii_uppercase.index, chars), 0)


class MStrEnum(str, Enum):
    """StrEnum is introduced in 3.11 and not available in runtime 3.9"""

    @staticmethod
    def _generate_next_value_(name: str, start: int, count: int, last_values: list) -> Any:
        return name.upper()


# class UserType(MStrEnum):
#     """possible user-roles"""
#
#     MAZEUSER = auto()
#     # MAZEREADER = auto()
#     # MAZEADMIN = auto()


class KeyDesignation(MStrEnum):
    """possible key-designations"""

    RS256 = auto()
    HS256 = auto()


class MazeSolutionStatus(MStrEnum):
    """Maze Solution Status"""

    NEW = auto()
    SOLVED_MIN = auto()
    SOLVED_MAX = auto()
    FAILED_MAX = auto()
    INVALID_GEOMETRY = auto()
    INVALID_ENTRY_INWALL = auto()
    INVALID_ENTRY_OUTOFBOUNDS = auto()
    INVALID_NOEXIT = auto()
    INVALID_MULTIEXIT = auto()
    SYSTEM_FAIL = auto()
    PROCESSING = auto()


class CheckableBaseModel(BaseModel):
    """
    base-model for pydantic-models being able to call the
    check-method anytime during the runtime/after their instantiation

    extended to be able to use field-name-alias as well as field-names for de-serializing
    """

    def check(self) -> None:
        *_, validation_error = validate_model(self.__class__, self.__dict__)
        if validation_error:
            raise validation_error

    class Config:
        allow_population_by_field_name = True


class ExcelCoordinate(ConstrainedStr):
    regex: Pattern[str] = _excel_pattern_compiled


class GridSize(ConstrainedStr):  # using GridSize = pydantic.constr(regex=_gridsize_pattern) causes mypy to complain!
    regex: Pattern[str] = _gridsize_pattern_compiled


class KeyDictEntry(BaseModel):
    """entry-format for the key-'database'"""

    id: str
    created_at: datetime.datetime
    invalidated_at: Optional[datetime.datetime]
    keydesignation: KeyDesignation
    public: Optional[str]
    private: Optional[str]
    password_encrypted: bool

    @root_validator(skip_on_failure=True)
    def check_private_or_public_key_present(cls, values: dict) -> dict:
        # logger.debug(values)
        assert values.get("private") or values.get("public")

        return values


class RefreshToken(BaseModel):
    """just a model containing the 'refresh_token'"""

    refresh_token: str


class TokenWithRefreshToken(BaseModel):
    """
    the targeted token-format with access_token, refresh_token and
    token_type (which is assumed to always be 'Bearer')
    """

    access_token: str
    token_type: str
    refresh_token: str


class TokenWithRefreshTokenAndMessage(TokenWithRefreshToken):
    """
    extension of the targeted token-format for being able to convey an additional 'message' to the api-user
    """

    message: Optional[str]


class UserSelf(BaseModel):
    """model for retrieving user-data which represents the user himitherself | more data visible"""

    id: UUID
    # usertype: UserType
    username: str
    # get mazes count ?!


class UserOther(BaseModel):
    """restricted model for retrieving user-data which represents users not being the user himitherself"""

    id: UUID
    # usertype: UserType


def _pydantic_username_validator(value: str) -> str:
    """extra validator for username-validation"""
    if not _username_pattern_compiled.match(value):
        raise ValueError("username pattern does not match")
    return value


class UserName(CheckableBaseModel):
    """just a username-schema containing the pattern and limits"""

    username: str = Field(min_length=8, max_length=42, regex=_username_pattern)

    _username_validator = validator("username", pre=False, allow_reuse=True)(_pydantic_username_validator)


class UserWithPassword(UserName):  # UserWithNameAndType):
    """
    extension of the username+type-schema/model
    """

    password: str = Field(min_length=8, max_length=42, regex=_password_pattern)


class UserWithPasswordHashAndID(UserName):  # UserWithNameAndType):
    """the main representation for a user from DB"""

    id: UUID = Field(default_factory=uuid4)
    password_hashed: str

    @staticmethod
    def get_user_from_dict(user: dict) -> Optional[MazeUser]:
        return MazeUser(**user)

    @staticmethod
    async def get_user(
        username: Optional[UserName] = None, userid: Optional[UUID] = None
    ) -> Optional[MazeUser]:  # sanitizes lookup via pydantic + validator
        assert (username and not userid) or (userid and not username), f"username XOR userid may be supplied"

        userdict: Optional[dict] = None
        if username:
            userdict = await get_user_from_db_by_username(username.username)
        elif userid:
            userdict = await get_user_from_db_by_id(userid)

        if userdict:
            return UserWithPasswordHashAndID.get_user_from_dict(userdict)
        else:
            return None

    @staticmethod
    async def get_all_users() -> List[MazeUser]:
        userdicts: List[dict] = await get_all_users_from_db()

        ret: List[MazeUser] = []
        for ud in userdicts:
            r: Optional[MazeUser] = UserWithPasswordHashAndID.get_user_from_dict(ud)
            if r:
                ret.append(r)
            else:
                logger.error("UNKNOWN USERTYPE IN DB FOUND!!!")
        return ret

    async def save(self) -> Optional[MazeUser]:
        data_saved: dict = await save_user(self.id, self.username, self.dict())

        retb: MazeUser = cast(MazeUser, self.copy(update=data_saved))
        return retb

    async def create_new(self) -> Optional[MazeUser]:
        data_saved: dict = await save_user(self.id, self.username, self.dict(), new_user=True)

        rets: MazeUser = cast(MazeUser, self.copy(update=data_saved))

        return rets

    async def delete_me(self) -> None:
        await delete_user(self.id)


class MazeUser(UserWithPasswordHashAndID):
    ...


class MazeInput(CheckableBaseModel):
    """maze datatype for posting maze-model from users"""

    entrance: ExcelCoordinate
    grid_size: GridSize = Field(
        alias="gridSize",
        description="columns first! => e.g. for grid with 10 columns and 5 rows, this is: 10x5",
    )
    walls: List[ExcelCoordinate] = Field(
        unique_items=True
    )  # may even be 0 walls, but it has to be submitted as empty array then...

    # @validator("walls", each_item=True)
    # def _walls_validator(cls, value) -> str:
    #     logger.debug(f"{value=}")
    #     if _excel_pattern_compiled.match(value):
    #         return value
    #     raise ValueError(f"does not seem to depict excel-coordinate: {value}")

    # @validator("entrance")
    # def _entrance_validator(cls, value) -> str:
    #     logger.debug(f"{value=}")
    #     if _excel_pattern_compiled.match(value):
    #         return value
    #     raise ValueError(f"does not seem to depict excel-coordinate: {value}")

    @staticmethod
    def static_get_maze_hash(grid_size: GridSize, entrance: ExcelCoordinate, walls: List[ExcelCoordinate]) -> str:
        """also sorts the list!!!"""
        m = sha256()

        m.update(entrance.encode("utf8"))
        m.update(grid_size.encode("utf8"))

        for w in sorted(walls):  # , key=lambda x: x.value):
            m.update(w.encode("utf8"))
        return m.hexdigest()

    def get_maze_hash(self) -> str:
        return Maze.static_get_maze_hash(grid_size=self.grid_size, entrance=self.entrance, walls=self.walls)

    # @validator("grid_size")
    # def _grid_size_validator(cls, value: str) -> str:
    #     if _gridsize_pattern_compiled.match(value):
    #         return value
    #     else:
    #         raise ValueError(f"gridsize does not seem to conform to pattern {value} vs. {_gridsize_pattern}")

    def get_grid_size_as_int_tuple(self) -> Tuple[int, int]:
        """return grid_size as int-tuple WIDTH,HEIGHT"""
        match: Optional[Match] = _gridsize_pattern_compiled.match(self.grid_size)
        if not match:
            # should never come here since everything is pre-check; alternatively raise error
            return -1, -1
        return int(match.groups()[0]), int(match.groups()[1])


class Maze(MazeInput):
    """
    product datatype for usage from/to db
    """

    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    hash: str
    mazenum: int = Field(default=1)

    @validator("hash", always=True)
    def _validate_hash(cls, value: str, values: dict) -> str:
        """rather sets the hash than validates it!!!"""
        return Maze.static_get_maze_hash(
            entrance=values["entrance"], grid_size=values["grid_size"], walls=values["walls"]
        )

    @staticmethod
    async def get_maze_by_mazeid(mazeid: UUID) -> Optional[Maze]:
        maze_dict: Optional[dict] = await get_maze_from_db_by_id(mazeid)
        logger.debug(f"{maze_dict=}")
        if not maze_dict:
            return None

        return Maze(**maze_dict)

    @staticmethod
    async def get_maze_by_userid_and_hash(userid: UUID, hash: str) -> Optional[Maze]:
        maze_dict: Optional[dict] = await get_maze_from_db_by_userid_and_hash(userid, hash)
        logger.debug(f"{maze_dict=}")
        if not maze_dict:
            return None

        return Maze(**maze_dict)

    @staticmethod
    async def get_maze_by_userid_and_mazenum(userid: UUID, mazenum: int) -> Optional[Maze]:
        maze_dict: Optional[dict] = await get_maze_from_db_by_userid_and_mazenum(userid=userid, mazenum=mazenum)
        logger.debug(f"{maze_dict=}")
        if not maze_dict:
            return None

        return Maze(**maze_dict)

    @staticmethod
    async def delete_all_mazes_belonging_to_user(userid: UUID) -> None:
        mazeids: List[dict] = await get_all_mazes_from_db_by_userid(userid)

        to_delete_mazes: List[Maze] = []
        for pd in mazeids:
            p: Maze = Maze(**pd)
            to_delete_mazes.append(p)

        for delmaze in to_delete_mazes:
            await delmaze.delete()

    async def save(self) -> Maze:
        data_saved: dict = await save_maze(self.id, self.dict())
        ret: Maze = self.copy(update=data_saved)
        return ret

    async def delete(self) -> None:
        logger.debug(f"Deleting maze: {self.id}")
        await delete_maze(self.id)

    async def create_new(self) -> Maze:
        all_user_mazes_dict: List[dict] = await get_all_mazes_from_db_by_userid(
            userid=self.owner_id
        )  # inefficient -> something like "count" would be nice -> not available in deta-base ?!
        self.mazenum = len(all_user_mazes_dict) + 1

        data_saved: dict = await save_maze(self.id, self.dict(), new_maze=True)
        ret: Maze = self.copy(update=data_saved)
        return ret


class MazeSolution(BaseModel):
    """
    data schema/model being used as the response for a resolution for a maze
    """

    id: UUID = Field(default_factory=uuid4)
    mazehash: str
    detected_exit: Optional[ExcelCoordinate]
    solution_min: Optional[List[ExcelCoordinate]]
    solution_max: Optional[List[ExcelCoordinate]]
    status: MazeSolutionStatus = MazeSolutionStatus.NEW

    @staticmethod
    async def get_solution_for_maze(mazehash: str) -> Optional[MazeSolution]:
        solution_dict: Optional[dict] = await get_maze_solution_from_db_by_hash(mazehash)
        logger.debug(f"{solution_dict=}")
        if not solution_dict:
            return None

        return MazeSolution(**solution_dict)

    async def save(self) -> MazeSolution:
        dict_me: dict = self.dict()
        dict_me["status"] = self.status.value

        logger.debug(dict_me)

        data_saved: dict = await save_maze_solution(self.id, dict_me)
        ret: MazeSolution = self.copy(update=data_saved)

        return ret

    async def delete(self) -> None:
        await delete_maze(self.id)

    async def create_new(self) -> MazeSolution:
        dict_me: dict = self.dict()
        dict_me["status"] = self.status.value
        data_saved: dict = await save_maze_solution(self.id, dict_me, new_solution=True)
        ret: MazeSolution = self.copy(update=data_saved)
        return ret


class MazeSolutionOut(BaseModel):
    path: List[ExcelCoordinate]
    # from here on only for debug ?!
    mazehash: str


class MazeOut(BaseModel):
    entrance: ExcelCoordinate
    gridSize: GridSize
    walls: List[ExcelCoordinate]
    mazenum: int
    # from here on only for debug ?!
    id: UUID
    owner_id: UUID
    hash: str
