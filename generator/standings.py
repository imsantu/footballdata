# -*- coding: utf-8 -*-
"""积分榜与队名归一的共享逻辑（顶级/次级联赛与进球数同步脚本共用，消除重复实现）。

唯一真相来源：compute_table / compute_goals / club_core / canon_top / deduct_map /
parse_score / is_regular_match / core_set / cores_match / in_cores。
改积分算法只改这里，四个脚本同步生效。
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DEDUCTIONS_PATH = os.path.join(HERE, "assets", "deductions.json")

# 各联赛同名分纠缠时的破同分规则（tie-break）：
#   h2h —— 先比相互交锋小联赛，再回退总净胜球/总进球：西甲、意甲
#   gd  —— 先比总净胜球、总进球，再回退相互交锋：英超、德甲、法甲
TIE_RULE = {"es": "h2h", "it": "h2h", "en": "gd", "de": "gd", "fr": "gd"}

# 法甲 6 队在 openfootball 简称与官方全名不一致，统一归一到官方全名（队徽/积分榜）。
GOALS_ALIAS = {
    "Paris Saint-Germain": "Paris Saint-Germain FC",
    "RC Lens": "Racing Club de Lens",
    "Olympique Marseille": "Olympique de Marseille",
    "Stade Rennais": "Stade Rennais FC 1901",
    "AS Monaco": "AS Monaco FC",
    "RC Strasbourg": "RC Strasbourg Alsace",
}

def canon_top(name):
    return GOALS_ALIAS.get(name, name)

def canon_identity(name):
    return name

# 跨文件队名归一：抽掉成立年份（纯数字）与法律/冠词类通用词，用「核心名」比对。
# 预备队（… B / II）尾部标记保留，不会被并入一队。
LEGAL_TOK = {"fc", "cf", "sc", "sv", "vfl", "vfb", "tsv", "spvgg", "ssv", "sg", "rb", "tsg",
             "us", "as", "ss", "ac", "uc", "rc", "rcd", "cd", "sd", "ud", "ad", "sad",
             "usl", "afc", "real", "club",
             "deportivo", "calcio", "a", "the", "de", "del", "la", "le", "les", "du", "des",
             "da", "do", "di", "der", "dem", "den"}
_TRANS = {"\u00df": "ss", "\u00f8": "o", "\u00d8": "o", "\u0142": "l", "\u0131": "i",
          "\u00e6": "ae", "\u0153": "oe", "\u00fe": "th", "\u00f0": "d"}
_MARK_RE = re.compile(r"[\u0300-\u036f]")

def _strip_accents(s):
    return _MARK_RE.sub("", unicodedata.normalize("NFD", s))

def club_core(name):
    s = str(name).lower()
    for a, b in _TRANS.items():
        s = s.replace(a, b)
    s = _strip_accents(s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b\d+\b", " ", s)
    return " ".join(t for t in s.split() if t and t not in LEGAL_TOK)

def core_set(names):
    return {c for c in (club_core(n) for n in names) if c}

# 容错匹配：首词必须相同、一方词集合是另一方子集、短的一方≥2 词、预备队尾标一致。
_RESERVE = {"b", "ii", "iii", "u19", "u20", "u21", "u23"}

def cores_match(a, b):
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    if ta[0] != tb[0]:
        return False
    sa, sb = set(ta), set(tb)
    if (sa & _RESERVE) != (sb & _RESERVE):
        return False
    sa, sb = sa - _RESERVE, sb - _RESERVE
    if min(len(sa), len(sb)) < 2:
        return False
    return sa <= sb or sb <= sa

def in_cores(core, cores):
    if core in cores:
        return True
    return any(cores_match(core, c) for c in cores)

PO_RE = re.compile(
    r"play[-\s]?off|playout|aufstieg|relegation|semifinal|quarterfinal|\bfinals?\b|promotion",
    re.I)

def is_regular_match(m):
    if m.get("phase") == "po":
        return False
    return not PO_RE.search(str(m.get("round", "")))

def parse_score(m):
    s = m.get("score")
    if s is None:
        return None
    if isinstance(s, list):
        return tuple((list(s) + [None, None])[:2])
    if isinstance(s, dict):
        ft = s.get("ft")
        return tuple(ft[:2]) if ft else None
    return None

def load_deductions():
    return json.load(open(DEDUCTIONS_PATH, encoding="utf-8"))

def deduct_map(code, season, grp="top", deductions=None):
    """{核心名: 扣分}；空字典表示无扣分，扣分逻辑自然退化。"""
    if deductions is None:
        deductions = load_deductions()
    node = (deductions.get(grp) or {}).get(code, {}).get(season) or []
    return {club_core(x["en"]): int(x["deduct"]) for x in node if x.get("en")}

def compute_table(ms, rule="gd", deduct=None, canon=canon_top):
    """由赛果算积分榜（名次, 积分）。同分时按 rule 破同分：
    h2h —— 西甲/意甲相互交锋优先；gd —— 英超/德甲/法甲总净胜球/总进球优先。
    相互交锋记录必须【累加】主客两回合；队名走 canon 避免别名劈队。"""
    tb = {}
    for m in ms:
        p = parse_score(m)
        if not p or None in p:
            continue
        h, a = p
        t1, t2 = canon(m["team1"]), canon(m["team2"])
        for t in (t1, t2):
            if t not in tb:
                tb[t] = {"W": 0, "D": 0, "L": 0, "gf": 0, "ga": 0, "pts": 0, "h2h": {}}
        tb[t1]["gf"] += h; tb[t1]["ga"] += a
        tb[t2]["gf"] += a; tb[t2]["ga"] += h
        if h > a:
            tb[t1]["W"] += 1; tb[t2]["L"] += 1
        elif a > h:
            tb[t2]["W"] += 1; tb[t1]["L"] += 1
        else:
            tb[t1]["D"] += 1; tb[t2]["D"] += 1
    for r in tb.values():
        r["pts"] = r["W"] * 3 + r["D"]
    if deduct:
        for t, r in tb.items():
            r["pts"] -= deduct.get(club_core(t), 0)
    for m in ms:
        p = parse_score(m)
        if not p or None in p:
            continue
        h, a = p
        t1, t2 = canon(m["team1"]), canon(m["team2"])
        if t1 not in tb or t2 not in tb:
            continue
        if h > a:
            p1, gf1, ga1, p2, gf2, ga2 = 3, h, a, 0, a, h
        elif a > h:
            p1, gf1, ga1, p2, gf2, ga2 = 0, h, a, 3, a, h
        else:
            p1, gf1, ga1, p2, gf2, ga2 = 1, h, a, 1, a, h
        e1 = tb[t1]["h2h"].setdefault(t2, [0, 0, 0]); e1[0] += p1; e1[1] += gf1; e1[2] += ga1
        e2 = tb[t2]["h2h"].setdefault(t1, [0, 0, 0]); e2[0] += p2; e2[1] += gf2; e2[2] += ga2
    by_pts = {}
    for t, r in tb.items():
        by_pts.setdefault(r["pts"], []).append(t)
    final = []
    for pts in sorted(by_pts, reverse=True):
        grp = by_pts[pts]
        if len(grp) == 1:
            final.append(grp[0]); continue
        sub = {t: {"pts": 0, "gd": 0, "gf": 0} for t in grp}
        for t in grp:
            for o in grp:
                if o == t:
                    continue
                hv = tb[t]["h2h"].get(o)
                if hv:
                    sub[t]["pts"] += hv[0]; sub[t]["gd"] += hv[1] - hv[2]; sub[t]["gf"] += hv[1]
        if rule == "h2h":
            key = lambda t: (-sub[t]["pts"], -sub[t]["gd"], -sub[t]["gf"],
                             -(tb[t]["gf"] - tb[t]["ga"]), -tb[t]["gf"])
        else:
            key = lambda t: (-(tb[t]["gf"] - tb[t]["ga"]), -tb[t]["gf"],
                             -sub[t]["pts"], -sub[t]["gd"], -sub[t]["gf"])
        final.extend(sorted(grp, key=key))
    return {t: (i + 1, tb[t]["pts"]) for i, t in enumerate(final)}

def compute_goals(ms, canon=canon_top):
    """每队总进球（主客两场都算）。"""
    g = {}
    for m in ms:
        p = parse_score(m)
        if not p or None in p:
            continue
        t1, t2 = canon(m["team1"]), canon(m["team2"])
        g[t1] = g.get(t1, 0) + p[0]
        g[t2] = g.get(t2, 0) + p[1]
    return g
