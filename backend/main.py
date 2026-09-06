"""AI 对诗平台后端入口"""
import json

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from . import ai_adapter, poetry_modes
from .config import config
from .prompts import MODES

app = FastAPI(title="AI 自动对诗平台", version="1.0.0")


class NoCacheMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response


app.add_middleware(NoCacheMiddleware)


class DuelRequest(BaseModel):
    mode: str
    content: str
    force_local: bool = False
    cloud_url: str = ""
    cloud_key: str = ""
    cloud_model: str = ""
    local_url: str = ""
    local_model: str = ""


class VerifyRequest(BaseModel):
    content: str


class HealthRequest(BaseModel):
    cloud_url: str = ""
    cloud_key: str = ""
    cloud_model: str = ""
    local_url: str = ""
    local_model: str = ""


def _overrides(req: DuelRequest | HealthRequest) -> dict:
    return {
        "cloud_url": req.cloud_url,
        "cloud_key": req.cloud_key,
        "cloud_model": req.cloud_model,
        "local_url": req.local_url,
        "local_model": req.local_model,
    }


@app.get("/api/health")
async def health_get():
    return await ai_adapter.health()


@app.post("/api/health")
async def health_post(req: HealthRequest):
    return await ai_adapter.health(_overrides(req))


@app.get("/api/modes")
async def modes():
    return {"modes": MODES}


@app.post("/api/duel")
async def duel(req: DuelRequest):
    if req.mode not in poetry_modes.HANDLERS:
        raise HTTPException(status_code=400, detail=f"未知模式: {req.mode}")
    try:
        result = await poetry_modes.HANDLERS[req.mode](req.content, req.force_local, _overrides(req))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@app.post("/api/duel/stream")
async def duel_stream(req: DuelRequest):
    if req.mode not in poetry_modes.HANDLERS:
        raise HTTPException(status_code=400, detail=f"未知模式: {req.mode}")

    async def gen():
        # 飞花令：AI 模型优先，模型不可用时以内置诗词库兜底
        if req.mode == "feihualing":
            frames = []
            async for frame in ai_adapter.stream_generate(
                prompt=poetry_modes.build_prompt(req.mode, req.content),
                system=poetry_modes.SYSTEM_PROMPTS[req.mode],
                mode=req.mode,
                force_local=req.force_local,
                overrides=_overrides(req),
            ):
                frames.append(frame)
            last_provider = frames[-1].get("provider") if frames else ""
            if last_provider == "mock" and not req.force_local:
                library_text = poetry_modes.feihualing_library(req.content)
                if library_text:
                    yield f"data: {json.dumps({'provider': 'library', 'delta': library_text})}\n\n"
                    yield f"data: {json.dumps({'done': True, 'provider': 'library'})}\n\n"
                    return
            for frame in frames:
                yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
            return
        try:
            async for frame in ai_adapter.stream_generate(
                prompt=poetry_modes.build_prompt(req.mode, req.content),
                system=poetry_modes.SYSTEM_PROMPTS[req.mode],
                mode=req.mode,
                force_local=req.force_local,
                overrides=_overrides(req),
            ):
                yield f"data: {json.dumps(frame, ensure_ascii=False)}\n\n"
        except ValueError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.post("/api/verify")
async def verify(req: VerifyRequest):
    try:
        return await poetry_modes.handle_verify(req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/")
async def index():
    return FileResponse(config.frontend_dir / "index.html")


app.mount("/", StaticFiles(directory=str(config.frontend_dir)), name="static")
