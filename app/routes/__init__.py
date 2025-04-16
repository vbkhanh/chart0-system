from fastapi import APIRouter
from app.routes import (
    symbol_routes, bar_routes, tick_routes, user_routes, auth_routes,
    indicator_routes, watchlist_routes, snapshot_routes, drawing_routes,
    tokyo_stock, export
)


api_router = APIRouter()

api_router.include_router(symbol_routes.router, tags=["symbols"])
api_router.include_router(bar_routes.router, tags=["chart bars"])
api_router.include_router(tick_routes.router, tags=["ticks"])
api_router.include_router(user_routes.router, tags=["users"])
api_router.include_router(auth_routes.router, tags=["authentication"])
api_router.include_router(indicator_routes.router, tags=["indicators"])
api_router.include_router(watchlist_routes.router, tags=["watchlists"])
api_router.include_router(snapshot_routes.router, tags=["snapshots"])
api_router.include_router(drawing_routes.router, tags=["drawings"])
api_router.include_router(tokyo_stock.router, tags=["tokyo stocks"])
api_router.include_router(export.router, tags=["export files"])
