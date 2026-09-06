"""AI 适配层：云端大模型 / 本地 Ollama / 内置 Mock 三通道，自动切换。

策略：云端优先（配置了 Key 且可用）→ 本地 Ollama → Mock 兜底。
统一接口 generate() / stream_generate()，返回 (文本, provider)。
"""
import asyncio
import random

import httpx

from .config import config

# Mock 内置模板（按模式）
_MOCK_BY_MODE = {
    "duilian": [
        "绿水本无忧，因风皱面；青山原不老，为雪白头。",
        "海内存知己，天涯若比邻。",
        "风声雨声读书声，声声入耳；家事国事天下事，事事关心。",
        "春回大地千山秀，日暖神州万木荣。",
        "松竹梅岁寒三友，桃李杏春风一家。",
    ],
    "jielong": [
        "春风又绿江南岸，明月何时照我还。",
        "山重水复疑无路，柳暗花明又一村。",
        "沉舟侧畔千帆过，病树前头万木春。",
        "长风破浪会有时，直挂云帆济沧海。",
        "问渠那得清如许，为有源头活水来。",
    ],
    "changhe": [
        "君问归期未有期，巴山夜雨涨秋池。\n何当共剪西窗烛，却话巴山夜雨时。",
        "独在异乡为异客，每逢佳节倍思亲。\n遥知兄弟登高处，遍插茱萸少一人。",
        "好雨知时节，当春乃发生。\n随风潜入夜，润物细无声。",
        "白日依山尽，黄河入海流。\n欲穷千里目，更上一层楼。",
    ],
    "feihualing": [
        "月落乌啼霜满天，江枫渔火对愁眠。",
        "海上生明月，天涯共此时。",
        "举杯邀明月，对影成三人。",
        "二十四桥明月夜，玉人何处教吹箫。",
    ],
}


class AIAdapterError(Exception):
    pass


def _mock_text(mode: str) -> str:
    pool = _MOCK_BY_MODE.get(mode, _MOCK_BY_MODE["jielong"])
    return random.choice(pool)


def _resolve(overrides: dict | None) -> dict:
    """合并请求级配置与 .env 配置：请求配置优先，留空则回退 .env"""
    o = overrides or {}
    return {
        "cloud_base_url": (o.get("cloud_url") or config.cloud_base_url).strip().rstrip("/"),
        "cloud_api_key": (o.get("cloud_key") or config.cloud_api_key).strip(),
        "cloud_model": (o.get("cloud_model") or config.cloud_model).strip(),
        "local_base_url": (o.get("local_url") or config.local_base_url).strip().rstrip("/"),
        "local_model": (o.get("local_model") or config.local_model).strip(),
    }


def _cloud_available(eff: dict) -> bool:
    return bool(eff["cloud_api_key"] and eff["cloud_base_url"] and eff["cloud_model"])


async def _probe(url: str, key: str = "", timeout: float | None = None) -> bool:
    """探测某端点可用性（GET /models）"""
    timeout = timeout or config.health_timeout
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{url}/models", headers=headers)
            return resp.status_code == 200
    except Exception:
        return False


async def check_cloud(eff: dict | None = None) -> bool:
    eff = eff or _resolve(None)
    if not _cloud_available(eff):
        return False
    return await _probe(eff["cloud_base_url"], eff["cloud_api_key"])


async def check_local(eff: dict | None = None) -> bool:
    eff = eff or _resolve(None)
    return await _probe(eff["local_base_url"])


async def health(overrides: dict | None = None) -> dict:
    eff = _resolve(overrides)
    cloud, local = await asyncio.gather(check_cloud(eff), check_local(eff))
    return {
        "cloud": cloud,
        "local": local,
        "mock": True,
        "cloud_configured": _cloud_available(eff),
        "cloud_model": eff["cloud_model"],
        "local_model": eff["local_model"],
    }


async def _request_nonstream(base_url: str, api_key: str, model: str, messages: list[dict]) -> str:
    async with httpx.AsyncClient(timeout=config.request_timeout) as client:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        resp = await client.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "stream": False},
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


async def _request_stream(base_url: str, api_key: str, model: str, messages: list[dict]):
    """流式请求，逐段产出文本"""
    async with httpx.AsyncClient(timeout=config.request_timeout) as client:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers=headers,
            json={"model": model, "messages": messages, "stream": True},
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                import json
                try:
                    data = json.loads(payload)
                    delta = data["choices"][0]["delta"].get("content")
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
                if delta:
                    yield delta


async def generate(prompt: str, system: str, mode: str = "jielong", force_local: bool = False, overrides: dict | None = None) -> tuple[str, str]:
    """非流式生成。返回 (文本, provider)；provider ∈ cloud/local/mock"""
    eff = _resolve(overrides)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    if not force_local and _cloud_available(eff) and await check_cloud(eff):
        try:
            text = await _request_nonstream(
                eff["cloud_base_url"], eff["cloud_api_key"], eff["cloud_model"], messages
            )
            if text:
                return text, "cloud"
        except Exception:
            pass

    if await check_local(eff):
        try:
            text = await _request_nonstream(
                eff["local_base_url"], "", eff["local_model"], messages
            )
            if text:
                return text, "local"
        except Exception:
            pass

    return _mock_text(mode), "mock"


async def stream_generate(prompt: str, system: str, mode: str = "jielong", force_local: bool = False, overrides: dict | None = None):
    """流式生成。逐段产出 dict：{"provider": ..., "delta": ...}；结束产出 {"done": True, "provider": ...}"""
    eff = _resolve(overrides)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    if not force_local and _cloud_available(eff) and await check_cloud(eff):
        try:
            async for delta in _request_stream(
                eff["cloud_base_url"], eff["cloud_api_key"], eff["cloud_model"], messages
            ):
                yield {"provider": "cloud", "delta": delta}
            yield {"done": True, "provider": "cloud"}
            return
        except Exception:
            pass

    if await check_local(eff):
        try:
            async for delta in _request_stream(
                eff["local_base_url"], "", eff["local_model"], messages
            ):
                yield {"provider": "local", "delta": delta}
            yield {"done": True, "provider": "local"}
            return
        except Exception:
            pass

    # Mock：分段吐字模拟流式
    text = _mock_text(mode)
    for i in range(0, len(text), 3):
        yield {"provider": "mock", "delta": text[i:i + 3]}
        await asyncio.sleep(0.03)
    yield {"done": True, "provider": "mock"}
