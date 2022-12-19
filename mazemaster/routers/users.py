import datetime
from typing import List, Optional, Tuple, Union
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, status, Request
from loguru import logger

from ..datastructures.models_and_schemas import (
    Maze,
    MazeUser,
    RefreshToken,
    TokenWithRefreshToken,
    TokenWithRefreshTokenAndMessage,
    UserName,
    UserOther,
    UserSelf,
    UserWithPassword,
    UserWithPasswordHashAndID,
    UserPassword,
)
from ..utils import auth
from ..utils.auth import (
    CredentialsException,
    UnScopedOAuth2PasswordRequestForm,
    check_if_user_has_session,
    clean_tokens_by_access_tokenid,
    clean_tokens_by_refresh_tokenid,
    clean_tokens_by_userid,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_current_user_n_payload,
    get_PROBABLYEXPIRED_current_user_with_payload,
    get_user_with_payload_from_token,
    myratelimit,
    responses_401,
    responses_403_429,
    verify_password,
    create_password_hash,
)
from ..utils.configuration import settings
from starlette.background import BackgroundTasks


router = APIRouter(tags=["user"])


@router.post(
    "/user",
    dependencies=[Depends(myratelimit)],
    response_model=UserSelf,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
    responses=responses_403_429,
)
async def create_user(userregisterdata: UserWithPassword) -> Optional[MazeUser]:
    """used to create a user
    -> should check for maximum users on the system to avoid overload
    -> limiting this endpoint via ip-filters seems futile in the realms of ipv6.
    -> anyhow, implementing a rudimentary, very adaptable, version using
    cachetools (and not using slowapi or such) "for fun and profit"
    """

    hashed_pw: str = auth.create_password_hash(userregisterdata.password)
    datadict: dict
    new_user_db: Optional[MazeUser]
    try:

        new_user: MazeUser = MazeUser(username=userregisterdata.username, password_hashed=hashed_pw)
        new_user_db = await new_user.create_new()

        return new_user_db
    except ValueError as ex:
        logger.debug(ex)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(ex))


@router.get(
    "/users", response_model=List[Union[UserSelf, UserOther]], response_model_exclude_none=True, responses=responses_401
)
async def read_users(me: MazeUser = Depends(get_current_user)) -> List[Union[UserSelf, UserOther]]:
    """get all users currently in 'DB' and print their userid+usertype; print full self-data for user-self"""
    dd: List[MazeUser] = await UserWithPasswordHashAndID.get_all_users()
    return [UserOther(**ud.dict()) if ud.id != me.id else UserSelf(**ud.dict()) for ud in dd]


@router.post(
    "/token/refresh", response_model=TokenWithRefreshToken, status_code=status.HTTP_201_CREATED, responses=responses_401
)
async def refresh_token(
    background_tasks: BackgroundTasks,  # trigger backgroud task to cleanse old tokens
    refresh_token_supplied: RefreshToken,
    request: Request,
    me_n_payload_PROBABLYEXPIRED: Tuple[MazeUser, dict] = Depends(get_PROBABLYEXPIRED_current_user_with_payload),
) -> dict:
    """get new request-token, access-token pair and kill the old refresh-tokens alltogether"""

    request_url_base: str = str(request.base_url)

    me: MazeUser = me_n_payload_PROBABLYEXPIRED[0]
    current_token_payload: dict = me_n_payload_PROBABLYEXPIRED[1]

    logger.debug(f"{me=}")
    logger.debug(f"{current_token_payload=}")
    logger.debug(f"{refresh_token_supplied=}")

    refresh_token_user: MazeUser
    refresh_token_payload: dict
    refresh_token_user, refresh_token_payload = await get_user_with_payload_from_token(
        refresh_token_supplied.refresh_token, verify_exp=True
    )  # throws-exception if anything goes wrong!

    if refresh_token_user.id != me.id:
        raise CredentialsException()

    refresh_token_new: str
    refresh_token_new_id: UUID
    refresh_token_new, refresh_token_new_id = await create_refresh_token(
        userid=me.id, request_url_base=request_url_base
    )

    access_token_new: str
    access_token_new_id: UUID
    access_token_new, access_token_new_id = await create_access_token(userid=me.id, request_url_base=request_url_base)

    refresh_token_expires_dt: datetime.datetime = datetime.datetime.fromtimestamp(int(refresh_token_payload["exp"]))

    if settings.deta_runtime_detected():
        await clean_tokens_by_refresh_tokenid(
            userid=me.id,
            refresh_tokenid_used=refresh_token_payload["tokenid"],
            refresh_token_expires_at=refresh_token_expires_dt,
        )
    else:
        background_tasks.add_task(
            clean_tokens_by_refresh_tokenid,
            userid=me.id,
            refresh_tokenid_used=refresh_token_payload["tokenid"],
            refresh_token_expires_at=refresh_token_expires_dt,
        )

    return {
        "access_token": access_token_new,
        "token_type": "bearer",
        "refresh_token": refresh_token_new,
    }


@router.delete("/token", status_code=status.HTTP_204_NO_CONTENT, responses=responses_401)
async def logout_this_token(me_n_payload: Tuple[MazeUser, dict] = Depends(get_current_user_n_payload)) -> None:
    """this is a "logout" mimic for token-based-auth"""
    me: MazeUser = me_n_payload[0]
    payload: dict = me_n_payload[1]

    await clean_tokens_by_access_tokenid(me.id, UUID(payload["tokenid"]))


@router.delete("/token/all", status_code=status.HTTP_204_NO_CONTENT, responses=responses_401)
async def logout_this_and_all_my_other_tokens(me: MazeUser = Depends(get_current_user)) -> None:
    """this is a "logout-all" mimic for token-based-auth"""

    await clean_tokens_by_userid(me.id)


@router.post(
    "/login",  # "/token"
    response_model=TokenWithRefreshTokenAndMessage,
    response_model_exclude_none=True,
    responses=responses_401,
    status_code=status.HTTP_201_CREATED,
)
async def login_for_access_token(request: Request, form_data: UnScopedOAuth2PasswordRequestForm = Depends()) -> dict:
    logger.debug(f"{form_data.username=} {form_data.password=}")
    user: Optional[MazeUser] = await UserWithPasswordHashAndID.get_user(UserName(username=form_data.username))
    logger.debug(f"Return USER: {user}")
    if not user or not verify_password(form_data.password, user.password_hashed):
        raise CredentialsException()

    request_url_base: str = str(request.base_url)

    msg: Optional[str] = None
    has_sessions: bool = await check_if_user_has_session(user.id)
    if has_sessions:
        msg = "There is already an active session [access_token] using your account"

    refresh_token: str
    refresh_token_id: UUID
    refresh_token, refresh_token_id = await create_refresh_token(userid=user.id, request_url_base=request_url_base)

    access_token: str
    access_token_id: UUID
    access_token, access_token_id = await create_access_token(userid=user.id, request_url_base=request_url_base)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "refresh_token": refresh_token,
        "message": msg,
    }


@router.get("/me", response_model=UserSelf, response_model_exclude_none=True, responses=responses_401)
async def read_user_me(me: MazeUser = Depends(get_current_user)) -> UserSelf:
    """get myself"""
    return UserSelf(**me.dict())


@router.patch("/me", response_model=UserSelf, response_model_exclude_none=True, responses=responses_401)
async def update_user(userpass: UserPassword, me: MazeUser = Depends(get_current_user)) -> Optional[MazeUser]:
    """updates the user - in this regard only changeable data atm is password."""

    hashed_pw: str = create_password_hash(userpass.password)
    me.password_hashed = hashed_pw

    saved_user: Optional[MazeUser] = me.copy(update=me.dict())
    if saved_user:
        return await saved_user.save()

    return None


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT, response_model_exclude_none=True, responses=responses_401)
async def delete_user(me: MazeUser = Depends(get_current_user)) -> None:
    """delete this user - users can only delete themselves.
    => deletes also all mazes from user
    => cleans all access-tokens+refresh-tokens in db
    => DOES NOT delete the shared solution for the mazes (based on the maze-hash)...
    """

    await Maze.delete_all_mazes_belonging_to_user(me.id)
    await clean_tokens_by_userid(me.id)
    await me.delete_me()
