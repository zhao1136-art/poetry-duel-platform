"""经典诗词知识库：加载 data/poems.json，提供含字检索"""
import json

from .config import config

_poems: list[dict] = []


def _load() -> list[dict]:
    global _poems
    if _poems:
        return _poems
    path = config.data_dir / "poems.json"
    with open(path, encoding="utf-8") as f:
        _poems = json.load(f)
    return _poems


def all_poems() -> list[dict]:
    return _load()


def find_by_char(char: str, limit: int = 5) -> list[dict]:
    """返回包含指定字的诗句（优先经典名句），最多 limit 条"""
    if not char:
        return []
    hits: list[dict] = []
    for poem in _load():
        for line in poem.get("lines", []):
            if char in line:
                hits.append({
                    "line": line,
                    "title": poem["title"],
                    "author": poem["author"],
                    "dynasty": poem["dynasty"],
                })
                break
    # 优先短句、名篇，简单去重后截取
    seen: set[str] = set()
    result: list[dict] = []
    for hit in hits:
        if hit["line"] in seen:
            continue
        seen.add(hit["line"])
        result.append(hit)
        if len(result) >= limit:
            break
    return result


def find_by_char_count(char: str) -> int:
    return len(find_by_char(char, limit=100))
