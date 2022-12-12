from __future__ import annotations

import asyncio
import datetime
from random import randint, random, sample, uniform
from typing import List, Literal, Optional, Set, Tuple, Union
from uuid import UUID

from loguru import logger

from mazemaster.datastructures.models_and_schemas import (
    ExcelCoordinate,
    MazeInput,
    GridSize,
)

from mazemaster.utils.configuration import settings

from mazemaster.utils.detadbwrapper import (
    AvailableDBS,
    create_new_entry,
)

import pytz


_tzberlin: datetime.tzinfo = pytz.timezone("Europe/Berlin")


def generate_pseudo_user_data() -> dict:
    import urllib.parse as ul
    from uuid import uuid4

    from mazemaster.utils.auth import (
        create_password_hash,
        generate_random_bytes,
    )

    from faker import Faker
    from faker.providers.misc.en_US import Provider as MProvider
    from faker.providers.person.en_GB import Provider as PProvider

    fake = Faker()
    fake.add_provider(MProvider)
    fake.add_provider(PProvider)

    tt: str = ""  # ugly, but logging messes this up (at least) if loglevel is DEBUG
    ret: dict = {}
    for i in range(0, 10):
        pw: str = (
            fake.password(length=9, special_chars=False, digits=True, upper_case=True, lower_case=True) + f"-{i:02}"
        )
        hash: str = create_password_hash(pw)
        userid: UUID = uuid4()
        username: str = f"{fake.unique.name().replace(' ', '')}-{i:02}"

        line: dict = {
            "id": userid,
            "password_hashed": hash,
            "username": username,
            "password_plain_not_in_real_db": pw,
        }
        ret[userid] = line

        lstr: str = f'"{username}": {line}, \t#  \t{ul.quote_plus(pw)}'

        tt += lstr + "\n"

    print(tt)

    return ret


def generate_pseudo_keydata() -> dict:
    import mazemaster.utils.auth as auth
    from mazemaster.utils.auth import generate_random_bytes

    import jwtjwkhelper

    now: datetime.datetime = datetime.datetime.now(_tzberlin)

    tt: str = ""  # ugly, but logging messes this up (at least) if loglevel is DEBUG

    ret: dict = {}

    for i in range(0, 2):
        rsa: jwtjwkhelper.RSAKeyPairPEM = jwtjwkhelper.create_rsa_key_pairs_return_as_pem(amount=1)[0]
        keyid: str = auth.get_hash_of_str(
            rsa.publickey_pem
        )  # getting it from public part since that should als be able for anyone not possessing the private key-part

        line: dict = {
            "id": keyid,
            "created_at": now.isoformat(),
            "invalidated_at": None,
            "keydesignation": "RS256",
            "public": rsa.publickey_pem,
            "private": rsa.privatekey_pem,
            "password_encrypted": False,
        }
        ret[keyid] = line

        lstr: str = f'"{keyid}": {line},\n'
        tt += lstr

    for i in range(0, 2):
        key: str = generate_random_bytes()
        hkeyid: str = auth.get_hash_of_str(key)

        hline: dict = {
            "id": hkeyid,
            "created_at": now.isoformat(),
            "invalidated_at": None,
            "keydesignation": "HS256",
            "public": None,
            "private": key,
            "password_encrypted": False,
        }
        ret[hkeyid] = hline

        hlstr: str = f'"{hkeyid}": {hline},\n'
        tt += hlstr

    print(tt)

    return ret


def generate_pseudo_maze_data(user_id: UUID, amount: int = 10) -> dict[str, dict]:
    from uuid import uuid4

    from mazemaster.solvers.gridmodels import to_excel

    tt: str = ""  # ugly, but logging messes this up (at least) if loglevel is DEBUG

    ret: dict = {}

    for i in range(0, amount):
        mazeid: UUID = uuid4()
        obstacle_perc: float = uniform(0.1, 0.9)
        cols: int = randint(1, 100)
        rows: int = randint(1, 100)
        grid_size: GridSize = GridSize(f"{cols}x{rows}")
        entrance_col: int = randint(0, rows)
        entrance_row: int = 0
        entrance: ExcelCoordinate = ExcelCoordinate(
            f"{to_excel(entrance_col)}{entrance_row+1}"
        )  # ExcelCoordinate(value=f"{to_excel(entrance_col)}{entrance_row+1}")
        exit_row: int = rows - 1

        num_exits: int = randint(1, 3)  # this does not mean, the exit is reachable!!!
        exit_cols: List[int] = sample(range(-1, cols), num_exits)

        # if uniform(0, 1.0) < obstacle_perc:
        walls: List[ExcelCoordinate] = []
        for row in range(rows):
            for column in range(cols):
                if column == entrance_col and row == entrance_row:
                    continue

                e_coord: ExcelCoordinate = ExcelCoordinate(
                    f"{to_excel(column)}{row+1}"
                )  # ExcelCoordinate(value=f"{to_excel(column)}{row+1}")

                if uniform(0, 1.0) < obstacle_perc:
                    walls.append(e_coord)

                # special-case: add line at the bottom aside exit
                if row == rows - 1:
                    if column in exit_cols:  # do not "overpaint" exits
                        continue

                    walls.append(e_coord)

        mi: MazeInput = MazeInput(grid_size=grid_size, walls=walls, entrance=entrance)
        mhash: str = mi.get_maze_hash()

        medict: dict = mi.dict()
        medict["id"] = mazeid
        medict["hash"] = mhash
        medict["mazenum"] = i + 1
        medict["owner_id"] = user_id

        ret[mazeid] = medict

        lstr: str = f'"{mazeid}": {medict},\n'
        tt += lstr

    print(tt)

    return ret


async def generate_pseudo_data_to_db() -> None:
    _pseudo_key_db = generate_pseudo_keydata()
    for key, values in _pseudo_key_db.items():
        await create_new_entry(db=AvailableDBS.keys, key=key, data=values)

    _pseudo_user_db = generate_pseudo_user_data()
    for key, values in _pseudo_user_db.items():
        logger.debug(f"{key=} {values=}")
        await create_new_entry(db=AvailableDBS.users, key=key, data=values)

    _pseudo_maze_db = {}
    for i, us in enumerate(_pseudo_user_db.values()):
        if i % 3 == 0:
            _me: dict = generate_pseudo_maze_data(us["id"])
            _pseudo_maze_db.update(_me)

    for key, values in _pseudo_maze_db.items():
        await create_new_entry(db=AvailableDBS.mazes, key=key, data=values)


if __name__ == "__main__":
    asyncio.run(generate_pseudo_data_to_db())
