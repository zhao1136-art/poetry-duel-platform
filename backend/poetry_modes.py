"""四种对诗模式的处理逻辑：组装提示词、调用 AI、附加韵律点评"""
import re

from . import ai_adapter, poem_db, prosody
from .prompts import SYSTEM_PROMPTS

_CN = re.compile(r"[\u4e00-\u9fff]")


def _clean(text: str) -> str:
    return text.strip()


def _tail_char(text: str) -> str:
    chars = _CN.findall(text)
    return chars[-1] if chars else ""


def build_structure_constraint(content: str, mode: str) -> str:
    """分析用户输入的结构与韵律，生成 AI 必须遵循的硬性约束文本"""
    if mode == "feihualing":
        return ""
    lines = [l.strip() for l in content.splitlines() if _CN.search(l)]
    if not lines:
        return ""
    lens = [prosody.char_count(l) for l in lines]
    tails = []
    for l in lines:
        chars = _CN.findall(l)
        if chars:
            tails.append(prosody.rhyme_group(chars[-1]) or "?")
    pieces = [f"原作为 {len(lines)} 句，每句字数依次为 {'、'.join(map(str, lens))} 字"]
    if any(t != "?" for t in tails):
        pieces.append(f"句尾韵辙为 {'、'.join(tails)}")
    pz_lines = ["".join(prosody.pingze_sequence(l)) for l in lines]
    if len(lines) <= 4 and all(len(p) <= 7 for p in pz_lines):
        pieces.append("平仄序列为 " + " / ".join(pz_lines))
    if mode == "duilian":
        head = "下联必须与上联字数完全相等、逐字平仄相对、词性相配"
    else:
        head = "回复必须逐句匹配原作的句数与字数，句尾押同一辙韵，平仄格律相谐"
    return f"【结构与韵律硬性要求】{head}（{'；'.join(pieces)}）。绝不可偏离上述结构与韵律。"


def build_prompt(mode: str, content: str) -> str:
    """组装 AI 用户提示词：基础指令 + 结构与韵律硬性约束"""
    content = _clean(content)
    base = {
        "duilian": f"请对出下联：{content}",
        "jielong": f"请接续此句：{content}",
        "changhe": f"请唱和这首诗：\n{content}",
        "feihualing": f"请给出含「{content[0]}」字的经典诗句，每句一行：" if content else "请给出含关键字字的经典诗句，每句一行：",
    }[mode]
    extra = build_structure_constraint(content, mode)
    return f"{base}\n{extra}" if extra else base


async def handle_duilian(content: str, force_local: bool = False, overrides: dict | None = None) -> dict:
    content = _clean(content)
    if not content:
        raise ValueError("上联内容不能为空")
    text, provider = await ai_adapter.generate(
        prompt=build_prompt("duilian", content),
        system=SYSTEM_PROMPTS["duilian"],
        mode="duilian",
        force_local=force_local,
        overrides=overrides,
    )
    note = None
    if provider != "mock":
        note = prosody.verify_duilian(content, text)
    return {"output": text, "provider": provider, "note": note, "mode": "duilian"}


async def handle_jielong(content: str, force_local: bool = False, overrides: dict | None = None) -> dict:
    content = _clean(content)
    if not content:
        raise ValueError("诗句内容不能为空")
    tail = _tail_char(content)
    text, provider = await ai_adapter.generate(
        prompt=build_prompt("jielong", content),
        system=SYSTEM_PROMPTS["jielong"],
        mode="jielong",
        force_local=force_local,
        overrides=overrides,
    )
    # 押韵校验：比较用户尾字与 AI 输出末句尾字
    note = None
    if tail:
        out_lines = [l for l in text.splitlines() if _CN.search(l)]
        out_tail = _tail_char(out_lines[-1]) if out_lines else ""
        if out_tail and provider != "mock":
            report = prosody.rhyme_report([tail, out_tail])
            note = {
                "ok": report["ok"],
                "notes": [
                    f"原句尾字「{tail}」属【{report['reports'][0]['group']}】辙",
                    f"续句尾字「{out_tail}」属【{report['reports'][1]['group']}】辙",
                    "押韵契合" if report["ok"] else "未押同韵，建议换韵脚",
                ],
            }
    return {"output": text, "provider": provider, "note": note, "mode": "jielong"}


async def handle_changhe(content: str, force_local: bool = False, overrides: dict | None = None) -> dict:
    content = _clean(content)
    if not content:
        raise ValueError("原诗内容不能为空")
    text, provider = await ai_adapter.generate(
        prompt=build_prompt("changhe", content),
        system=SYSTEM_PROMPTS["changhe"],
        mode="changhe",
        force_local=force_local,
        overrides=overrides,
    )
    return {"output": text, "provider": provider, "note": None, "mode": "changhe"}


def feihualing_library(content: str) -> str | None:
    """飞花令知识库检索：返回含字经典诗句文本；无命中返回 None"""
    content = _clean(content)
    if not content:
        return None
    hits = poem_db.find_by_char(content[0], limit=3)
    if not hits:
        return None
    return "\n".join(f"{h['line']}（{h['author']}·{h['dynasty']}）" for h in hits)


async def handle_feihualing(content: str, force_local: bool = False, overrides: dict | None = None) -> dict:
    """飞花令：AI 模型优先，模型不可用时以内置诗词库兜底"""
    content = _clean(content)
    if not content:
        raise ValueError("关键字不能为空")

    text, provider = await ai_adapter.generate(
        prompt=build_prompt("feihualing", content),
        system=SYSTEM_PROMPTS["feihualing"],
        mode="feihualing",
        force_local=force_local,
        overrides=overrides,
    )
    if provider == "mock" and not force_local:
        library_text = feihualing_library(content)
        if library_text:
            return {"output": library_text, "provider": "library", "note": None, "mode": "feihualing"}
    return {"output": text, "provider": provider, "note": None, "mode": "feihualing"}


async def handle_verify(content: str) -> dict:
    """韵律校验接口：对联/单句平仄押韵点评"""
    content = _clean(content)
    if not content:
        raise ValueError("内容不能为空")
    count = prosody.char_count(content)
    pz = "".join(prosody.pingze_sequence(content))
    tail = _tail_char(content)
    group = prosody.rhyme_group(tail) if tail else ""
    return {
        "count": count,
        "pingze": pz,
        "tail_char": tail,
        "rhyme_group": group or "?",
        "notes": [
            f"全句 {count} 字",
            f"平仄：{pz}",
            f"尾字「{tail}」属【{group}】辙" if group else "尾字无法判断韵部",
        ],
    }


HANDLERS = {
    "duilian": handle_duilian,
    "jielong": handle_jielong,
    "changhe": handle_changhe,
    "feihualing": handle_feihualing,
}
