from sqlalchemy import select, func
import logging
from typing import Annotated, Dict
import asyncio
import json

from fastapi_websocket_pubsub import PubSubEndpoint
from starlette.websockets import WebSocket
from fastapi import FastAPI, Query, status, Depends, HTTPException
from fastapi.routing import APIRouter

from app.settings import settings
from app.utils import verify_access_token
from sqlalchemy.ext.asyncio import AsyncSession
from app.configs.db import get_session
from app.models.watchlist import Watchlist
from app.models.user import User
from app.models import Tick


app = FastAPI()
router = APIRouter()
endpoint = PubSubEndpoint(broadcaster=settings.REDIS_URL)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@router.websocket("/pubsub")
async def websocket_rpc_endpoint(
    websocket: WebSocket,
    session: AsyncSession = Depends(get_session),
    token: Annotated[str | None, Query()] = None,
):
    try:
        if not token:
            raise Exception("Missing token")
        if token != settings.WEBSOCKET_API_KEY:
            token_data = verify_access_token(token, Exception("InvalidToken"))
            user = await session.scalars(select(User).where(
                User.id == token_data.user_id, User.status == "approved", User.state == "enabled"
            ))
            user = user.first()
            if not user:
                raise Exception("User not found or not available")
    except Exception as e:
        logger.error(e)
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)  # Policy Violation
        return
    finally:
        await session.close()
    await endpoint.main_loop(websocket)

app.include_router(router)

async def events(topic, data):
    await endpoint.publish(topic, data)

@app.post("/trigger/{topic}")
async def trigger_events(topic: str, token: str, data: Dict, session: AsyncSession = Depends(get_session)):
    if token != settings.WEBSOCKET_API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API Key")
    previous_tick = await session.execute(
        select(Tick.ask)
        .where(
            Tick.symbol_id == data["symbol_id"],
            Tick.datetime_msc < data["datetime_msc"]
        )
        .order_by(Tick.datetime_msc.desc())
        .limit(1)
    )
    previous_tick = previous_tick.scalars().first()
    res = {
        "symbol_id": data["symbol_id"],
        "price": data["ask"],
    }
    if previous_tick is not None:
        change = res["price"] - previous_tick
        change_percentage = (change / previous_tick) * 100 if previous_tick != 0 else 0
        res["change"] = change
        res["change_percentage"] = change_percentage
        res["compare_to_previous_tick"] = res["price"] > previous_tick
    
    asyncio.create_task(events(topic, res))
    return 200
