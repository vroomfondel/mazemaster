from __future__ import annotations

import datetime
from typing import List, Literal, Optional, Set, Tuple, Union
from uuid import UUID

from loguru import logger

from mazemaster.utils.detadbwrapper import (
    AvailableDBS,
    create_new_entry,
    delete_entry,
    get_all_data,
    get_data_by_field,
    get_data_by_fields,
    get_data_by_key,
    update_data,
)

import pytz


_tzberlin: datetime.tzinfo = pytz.timezone("Europe/Berlin")

"""semantic layer for mangling data from 'here' to deta-base and vice versa => there is no orm for deta amd anyway, 
a semantic layer might be beneficial"""


async def check_valid_tokens_access_token_or_refresh_token(userid: UUID) -> Tuple[int, int]:
    valid_access_tokens_found: int = 0
    valid_refresh_tokens_found: int = 0

    now: datetime.datetime = datetime.datetime.now(tz=_tzberlin)

    deltokenids: List[UUID] = []

    for tokendata in await get_data_by_field(db=AvailableDBS.tokens_issued, fieldname="userid", fieldvalue=userid):
        expires_at: datetime.datetime = datetime.datetime.fromisoformat(tokendata["expires_at"])
        is_refresh_token: bool = tokendata["refresh_token_id"] is None
        is_valid: bool = expires_at.timestamp() > now.timestamp()
        if is_valid:
            valid_access_tokens_found += 0 if is_refresh_token else 1
            valid_refresh_tokens_found += 1 if is_refresh_token else 0

        logger.debug(f"{userid=} {type(expires_at)=} {expires_at=} {is_valid=} {is_refresh_token=}")
    return (valid_access_tokens_found, valid_refresh_tokens_found)


async def save_issued_token(
    tokenid: UUID,
    userid: UUID,
    keyid: str,
    expires_at: datetime.datetime,
    issued_at: datetime.datetime,
    refresh_token_id: Optional[UUID] = None,
) -> None:

    newentry: dict = {
        "id": tokenid,
        "refresh_token_id": refresh_token_id,
        "userid": userid,
        "keyid": keyid,
        "expires_at": expires_at,
        "issued_at": issued_at,
    }
    await create_new_entry(
        db=AvailableDBS.tokens_issued,
        key=tokenid,
        data=newentry,
        # expire_at=expires_at.timestamp()  # :-))
    )


async def get_refresh_tokenid_from_access_tokenid(userid: UUID, access_tokenid_used: UUID) -> Optional[UUID]:
    for tokendata in await get_data_by_fields(
        db=AvailableDBS.tokens_issued,
        fieldnames=["userid", "id"],
        fieldvalues=[userid, access_tokenid_used],
    ):  # könnte hier auch als query machen!
        return tokendata["refresh_token_id"]

    return None


### the following seems horribly redundant -> but when using a "real" db, this will only be one line each...
async def _clean_tokens_by_list(deltokenids: List[Tuple[UUID, str]]) -> None:
    for tokenid, expires_at in deltokenids:
        logger.debug(f"deleting token: {tokenid=}")

        newentry: dict[str, Union[str, UUID]] = {"id": tokenid, "expires_at": expires_at}
        await create_new_entry(
            db=AvailableDBS.tokens_deleted,
            key=tokenid,
            data=newentry,
            # expire_at=expires_at.timestamp()  # :-))
        )
        await delete_entry(db=AvailableDBS.tokens_issued, key=tokenid)


async def clean_tokens_by_access_tokenid(userid: UUID, access_tokenid_used: UUID) -> None:
    deltokenids: List[Tuple[UUID, str]] = []
    for tokendata in await get_data_by_fields(
        db=AvailableDBS.tokens_issued,
        fieldnames=["userid", "id"],
        fieldvalues=[userid, access_tokenid_used],
    ):  # könnte hier auch als query machen!:

        deltokenids.append((UUID(tokendata["id"]), tokendata["expires_at"]))
    await _clean_tokens_by_list(deltokenids)


async def clean_tokens_by_refresh_tokenid(
    userid: UUID, refresh_tokenid_used: UUID, refresh_tokenid_expires_at: datetime.datetime
) -> None:
    deltokenids: List[Tuple[UUID, str]] = []
    deltokenids.append((refresh_tokenid_used, refresh_tokenid_expires_at.isoformat()))

    for tokendata in await get_data_by_fields(
        db=AvailableDBS.tokens_issued,
        fieldnames=["userid", "refresh_token_id"],
        fieldvalues=[userid, refresh_tokenid_used],
    ):  # könnte hier auch als query machen!:

        deltokenids.append((UUID(tokendata["id"]), tokendata["expires_at"]))

    await _clean_tokens_by_list(deltokenids)


async def clean_tokens_by_userid(userid: UUID) -> None:
    deltokenids: List[Tuple[UUID, str]] = []
    for tokendata in await get_data_by_fields(
        db=AvailableDBS.tokens_issued, fieldnames=["userid"], fieldvalues=[userid]
    ):  # könnte hier auch als query machen!:
        logger.debug(f"{tokendata=}")

        deltokenids.append((UUID(tokendata["id"]), tokendata["expires_at"]))

    await _clean_tokens_by_list(deltokenids)


async def get_key_ids_by_designation(keydesignation: Literal["HS256", "RS256"] = "HS256") -> List[str]:
    ret: List[str] = []

    for keydata in await get_data_by_field(db=AvailableDBS.keys, fieldname="keydesignation", fieldvalue=keydesignation):
        ret.append(keydata["id"])

    return ret


async def is_token_in_deleted_tokens_db(tokenid: UUID) -> bool:
    _ret: List[dict] = await get_data_by_key(db=AvailableDBS.tokens_deleted, keyvalue=tokenid)

    return len(_ret) > 0


async def get_key_by_id_and_designation(
    keyid: str, keydesignation: Literal["HS256", "RS256"] = "HS256"
) -> Optional[dict]:
    keydata: dict
    for keydata in await get_data_by_fields(
        db=AvailableDBS.keys, fieldnames=["keydesignation", "id"], fieldvalues=[keydesignation, keyid]
    ):
        return keydata

    return None


async def get_user_from_db_by_username(username: str) -> Optional[dict]:
    userdata: dict
    for userdata in await get_data_by_field(db=AvailableDBS.users, fieldname="username", fieldvalue=username):
        return userdata

    return None


async def get_user_from_db_by_id(userid: UUID) -> Optional[dict]:
    userdata: dict
    for userdata in await get_data_by_key(db=AvailableDBS.users, keyvalue=userid):
        return userdata

    return None


async def get_maze_from_db_by_userid_and_hash(userid: UUID, hash: str) -> Optional[dict]:
    mazedata: dict
    for mazedata in await get_data_by_fields(
        db=AvailableDBS.mazes, fieldnames=["owner_id", "hash"], fieldvalues=[userid, hash]
    ):
        return mazedata

    return None


async def get_maze_from_db_by_userid_and_mazenum(userid: UUID, mazenum: int) -> Optional[dict]:
    mazedata: dict
    for mazedata in await get_data_by_fields(
        db=AvailableDBS.mazes, fieldnames=["owner_id", "mazenum"], fieldvalues=[userid, mazenum]
    ):
        return mazedata

    return None


async def get_maze_from_db_by_hash(hash: str) -> Optional[dict]:
    mazedata: dict
    for mazedata in await get_data_by_field(db=AvailableDBS.mazes, fieldname="hash", fieldvalue=hash):
        return mazedata

    return None


async def get_maze_solution_from_db_by_hash(mazehash: str) -> Optional[dict]:
    solutiondata: dict
    for solutiondata in await get_data_by_field(
        db=AvailableDBS.maze_solutions, fieldname="mazehash", fieldvalue=mazehash
    ):
        return solutiondata

    return None


async def get_maze_from_db_by_id(mazeid: UUID) -> Optional[dict]:
    mazedata: dict
    for mazedata in await get_data_by_key(db=AvailableDBS.mazes, keyvalue=mazeid):
        return mazedata

    return None


async def get_all_mazes_from_db_by_userid(userid: UUID) -> List[dict]:
    ret: List[dict] = []
    mazedata: dict
    for mazedata in await get_data_by_field(AvailableDBS.mazes, fieldname="owner_id", fieldvalue=userid):
        ret.append(mazedata)

    return ret


async def get_all_mazes_from_db() -> List[dict]:
    ret: List[dict] = []
    mazedata: dict
    for mazedata in await get_all_data(db=AvailableDBS.mazes):
        ret.append(mazedata)

    return ret


async def get_all_maze_solutions_from_db_for_maze(mazeid: UUID) -> List[dict]:
    ret: List[dict] = []
    mazedata: dict
    for mazedata in await get_data_by_field(AvailableDBS.maze_solutions, fieldname="mazeid", fieldvalue=mazeid):
        ret.append(mazedata)

    return ret


async def _save(db: AvailableDBS, id: UUID, data: dict, new_entry: bool = False) -> dict:
    logger.debug(f"{db=} {id=} {data=} {new_entry=}")

    ret: dict

    if new_entry:
        ret = await create_new_entry(db=db, key=id, data=data)
        return ret

    prev_data: List[dict] = await get_data_by_key(db=db, keyvalue=id)

    prev_data[0].update(**data)

    del prev_data[0]["key"]

    logger.debug(f"trying update with {prev_data[0]=} on {id=} in {db=}")
    await update_data(db=db, key=id, full_data=prev_data[0])

    return prev_data[0]


async def save_maze(mazeid: UUID, data: dict, new_maze: bool = False) -> dict:
    return await _save(db=AvailableDBS.mazes, id=mazeid, data=data, new_entry=new_maze)


async def save_maze_solution(solution_id: UUID, data: dict, new_solution: bool = False) -> dict:
    return await _save(db=AvailableDBS.maze_solutions, id=solution_id, data=data, new_entry=new_solution)


async def delete_maze(mazeid: UUID) -> None:
    await delete_entry(db=AvailableDBS.mazes, key=mazeid)


async def delete_user(mazeid: UUID) -> None:
    await delete_entry(db=AvailableDBS.users, key=mazeid)


async def save_user(userid: UUID, username: str, data: dict, new_user: bool = False) -> dict:
    logger.debug(f"{userid=} {data=} {new_user=}")

    ret: dict

    if new_user:
        user_exists: Optional[dict] = await get_user_from_db_by_username(username)

        if user_exists:
            raise ValueError(f"USER WITH THAT USERNAME ALREADY EXISTS! {username=}")

        ret = await create_new_entry(db=AvailableDBS.users, key=userid, data=data)
        return ret

    prev_data: List[dict] = await get_data_by_key(AvailableDBS.users, keyvalue=userid)
    if len(prev_data) == 0 or prev_data[0]["username"] != username:
        raise RuntimeError(f"USERID,USERNAME MISMATCH IN DB! {userid=} {username=}")

    del prev_data[0]["key"]

    prev_data[0].update(**data)
    await update_data(db=AvailableDBS.users, key=userid, full_data=prev_data[0])

    return prev_data[0]


async def get_all_users_from_db() -> List[dict]:
    ret: List[dict] = []
    userdata: dict
    for userdata in await get_all_data(db=AvailableDBS.users):
        ret.append(userdata)

    return ret
