"""Jellyfin 集成接口。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.providers.player import factory as jf

router = APIRouter()


class JellyfinConfigOut(BaseModel):
    url: str
    api_key_set: bool
    configured: bool


class JellyfinConfigIn(BaseModel):
    url: str
    api_key: str | None = None


@router.get("/config")
def get_config() -> JellyfinConfigOut:
    cfg = jf.read_config()
    return JellyfinConfigOut(
        url=cfg.get("url") or "",
        api_key_set=bool(cfg.get("api_key")),
        configured=jf.is_configured(),
    )


@router.put("/config")
def update_config(payload: JellyfinConfigIn) -> dict:
    cur = jf.read_config()
    new_cfg = {
        "url": payload.url.rstrip("/"),
        "api_key": payload.api_key if payload.api_key is not None else cur.get("api_key", ""),
    }
    jf.save_config(new_cfg)
    return {"status": "saved"}


@router.post("/test")
async def test() -> dict:
    p = jf.create_provider()
    if not p:
        return {"ok": False, "error": "not_configured"}
    return await p.health_check()


@router.get("/libraries")
async def list_libraries() -> list[dict]:
    if not jf.is_configured():
        raise HTTPException(status_code=400, detail="not_configured")
    p = jf.create_provider()
    if not p:
        raise HTTPException(status_code=500)
    return await p.list_libraries()
