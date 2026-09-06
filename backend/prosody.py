"""韵律引擎：平仄判断、押韵检测、字数统计（基于 pypinyin，普通话近似）"""
import re

from pypinyin import lazy_pinyin, Style

# 十三辙韵部映射（韵母 → 韵部）
_RHYME_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("发花", ("a", "ia", "ua")),
    ("梭波", ("o", "e", "uo")),
    ("乜斜", ("ie", "ve")),
    ("姑苏", ("u",)),
    ("一七", ("i", "v", "er")),
    ("怀来", ("ai", "uai")),
    ("灰堆", ("ei", "ui")),
    ("遥条", ("ao", "iao")),
    ("由求", ("ou", "iu")),
    ("言前", ("an", "ian", "uan", "van")),
    ("人辰", ("en", "in", "un", "vn")),
    ("江阳", ("ang", "iang", "uang")),
    ("中东", ("eng", "ing", "ong", "iong")),
]


def _final_of(char: str) -> str:
    """取单字韵母（无声调），非汉字返回空串"""
    if not re.match(r"[\u4e00-\u9fff]", char):
        return ""
    pinyin = lazy_pinyin(char, style=Style.FINALS, strict=False)
    return pinyin[0] if pinyin else ""


def _tone_of(char: str) -> int:
    """取单字声调：1-4，轻声为 5，非汉字/无拼音为 0"""
    if not re.match(r"[\u4e00-\u9fff]", char):
        return 0
    pinyin = lazy_pinyin(char, style=Style.TONE3, strict=False)
    if not pinyin:
        return 0
    m = re.search(r"[1-5]$", pinyin[0])
    return int(m.group(0)) if m else 0


def char_count(text: str) -> int:
    """中文字符数量（不计标点/空格）"""
    return len(re.findall(r"[\u4e00-\u9fff]", text))


def pingze(char: str) -> str:
    """单字平仄：一二声为平，三四声为仄，轻声归平；无法判断返回 '?'"""
    tone = _tone_of(char)
    if tone in (1, 2, 5):
        return "平"
    if tone in (3, 4):
        return "仄"
    return "?"


def pingze_sequence(text: str) -> list[str]:
    """返回整句逐字平仄序列（忽略标点）"""
    return [pingze(c) for c in text if re.match(r"[\u4e00-\u9fff]", c)]


def rhyme_group(char: str) -> str:
    """单字所属韵部名，无法判断返回空串"""
    final = _final_of(char)
    if not final:
        return ""
    for name, finals in _RHYME_GROUPS:
        for f in finals:
            if final == f or final.endswith(f):
                return name
    return ""


def is_rhyme(chars: list[str]) -> bool:
    """一组字是否押韵（至少两个有效韵部且相同）"""
    groups = [rhyme_group(c) for c in chars if rhyme_group(c)]
    if len(groups) < 2:
        return False
    return len(set(groups)) == 1


def rhyme_report(tail_chars: list[str]) -> dict:
    """押韵点评：给出一组尾字的韵部信息"""
    reports = []
    for c in tail_chars:
        group = rhyme_group(c)
        reports.append({"char": c, "group": group or "?"})
    same = len({r["group"] for r in reports if r["group"] != "?"})
    ok = same == 1 and len(reports) >= 2
    return {"reports": reports, "ok": ok}


def verify_duilian(shanglian: str, xialian: str) -> dict:
    """对联点评：字数、平仄相对情况"""
    up = [c for c in shanglian if re.match(r"[\u4e00-\u9fff]", c)]
    down = [c for c in xialian if re.match(r"[\u4e00-\u9fff]", c)]
    notes: list[str] = []

    if not up or not down:
        return {"ok": False, "notes": ["内容过短，无法校验"]}

    if len(up) != len(down):
        notes.append(f"字数不等：上联 {len(up)} 字 / 下联 {len(down)} 字")
    else:
        notes.append(f"字数相对：{len(up)} 字")

    up_pz = [pingze(c) for c in up]
    down_pz = [pingze(c) for c in down]
    count = min(len(up), len(down))
    opposite = 0
    for i in range(count):
        if up_pz[i] != "?" and down_pz[i] != "?" and up_pz[i] != down_pz[i]:
            opposite += 1
    if count:
        ratio = opposite / count
        if ratio >= 0.5:
            notes.append(f"平仄相对良好（相对率 {ratio:.0%}）")
        else:
            notes.append(f"平仄相对一般（相对率 {ratio:.0%}）")

    # 上联尾字宜仄、下联尾字宜平
    if up and down:
        if up_pz[-1] == "仄":
            notes.append("上联尾字仄收，合律")
        elif up_pz[-1] == "平":
            notes.append("上联尾字平收，传统宜仄收")
        if down_pz[-1] == "平":
            notes.append("下联尾字平收，合律")
        elif down_pz[-1] == "仄":
            notes.append("下联尾字仄收，传统宜平收")

    return {"ok": True, "notes": notes}
