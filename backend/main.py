import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from analytics.player_search import load_players
from backend.models.schemas import HealthResponse
from backend.routers.players import router as players_router
from backend.routers.compare import router as compare_router
from backend.services.player_service import make_player_id


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    df = load_players()
    id_map: dict[int, int] = {}
    for pos in range(len(df)):
        row = df.iloc[pos]
        h = make_player_id(
            str(row["player_name"]),
            str(row["club"]),
            str(row["competition"]),
            str(row["season"]),
        )
        if h in id_map:
            existing = df.iloc[id_map[h]]
            logger.warning(
                "Hash collision detected (id=%d): '%s' (%s, %s, %s) collides with '%s' (%s, %s, %s)",
                h,
                row["player_name"], row["club"], row["competition"], row["season"],
                existing["player_name"], existing["club"], existing["competition"], existing["season"],
            )
        id_map[h] = pos
    app.state.df = df
    app.state.id_map = id_map
    logger.info("Dataset loaded: %d players, %d unique IDs", len(df), len(id_map))
    yield


app = FastAPI(
    title="Football Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(players_router, prefix="/api/v1")
app.include_router(compare_router, prefix="/api/v1")


@app.get("/health", response_model=HealthResponse)
def health(request: Request):
    df = request.app.state.df
    return {"status": "ok", "dataset_loaded": True, "player_count": len(df)}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
