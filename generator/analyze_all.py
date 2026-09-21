# -*- coding: utf-8 -*-
"""五大联赛（英超/西甲/德甲/意甲/法甲）近 5 个赛季（2022-23 ~ 2026-27）平局统计。
- 赛果：openfootball/football.json
- 名次/积分：沿用「进球数」报告内嵌的当季最终积分榜（缺失时回退为按赛果计算）
- 升/降班马：用上/下赛季名单差集判定；下赛季名单缺失时退化为积分榜末 N 位
"""
import json, re, os, ast, statistics
from collections import Counter, defaultdict
from standings import (compute_table, club_core, canon_top, core_set, cores_match,
                       in_cores, deduct_map, TIE_RULE, GOALS_ALIAS, is_regular_match,
                       parse_score)

canon = canon_top

import os
WS = os.path.dirname(os.path.abspath(__file__))
D = f"{WS}/data"

LEAGUES = [
    {"code": "en", "cn": "英超", "file": "en.1", "name": "英格兰超级联赛"},
    {"code": "es", "cn": "西甲", "file": "es.1", "name": "西班牙甲级联赛"},
    {"code": "de", "cn": "德甲", "file": "de.1", "name": "德国甲级联赛"},
    {"code": "it", "cn": "意甲", "file": "it.1", "name": "意大利甲级联赛"},
    {"code": "fr", "cn": "法甲", "file": "fr.1", "name": "法国甲级联赛"},
]
SEASONS = ["2026-27", "2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]   # 新 → 旧；2026-27 仅作当前赛季展示
BASE_SEASON = "2020-21"     # 仅作 2021-22 的升班马基准
# 总览窗口排除进行中的 2026-27：五季=2021-22~2025-26，三季=2023-24~2025-26。
WINDOW_5 = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]
WINDOW_3 = ["2025-26", "2024-25", "2023-24"]
# 说明：2026-27 赛季正在进行中，只录入开季前几轮的真实赛果，按实际已赛场次统计，
# 绝不做外推或补齐（宁缺勿造）；报告中该赛季标注「进行中」。
CATS = ["0-0", "1-1", "2-2", "其他"]

# 各联赛同名次纠缠时的破同分规则（tie-break）：
#   h2h —— 先比相互交锋小联赛（积分→净胜球→进球），再回退总净胜球/总进球：西甲、意甲
#   gd  —— 先比总净胜球、总进球，再回退相互交锋：英超、德甲、法甲
# 旧版一律用「总净胜球」破同分，在 2025-26 西甲三队同积 42 分（莱万特/奥萨苏纳/马洛卡）时
# 把本该第 16 安全的莱万特误排到第 18；而一律用「相互交锋」又会破坏英超等以总净胜球优先的联赛
# （如 2025-26 英超切尔西/富勒姆同 52 分，应凭总净胜球 +6/-4 让切尔西列前）。
TIE_RULE = {"es": "h2h", "it": "h2h", "en": "gd", "de": "gd", "fr": "gd"}


def fpath(code, season):
    if code == "en" and season == "2025-26":
        return os.path.join(D, "en.1.2025_26.json")
    return os.path.join(D, f"{code}.1.{season}.json")


def load(code, season):
    return json.load(open(fpath(code, season), encoding="utf-8"))["matches"]


def load_meta(code, season):
    """读取赛季数据文件的顶层元信息（2026-27 用它判断轮次是否已采信官方编号）。"""
    try:
        return json.load(open(fpath(code, season), encoding="utf-8"))
    except Exception:
        return {}


# 升降级附加赛等非联赛场次不计入常规赛统计。
# 目前顶级联赛源没有混入附加赛，但保留显式过滤，避免数据源变更后污染场次。
PO_RE = re.compile(
    r"play[-\\s]?off|playout|aufstieg|relegation|semifinal|quarterfinal|\\bfinals?\\b|promotion",
    re.I)


def is_regular_match(m):
    if m.get("phase") == "po":
        return False
    return not PO_RE.search(str(m.get("round", "")))


def cat(h):
    return {0: "0-0", 1: "1-1", 2: "2-2"}.get(h, "其他")


# ---------- 内嵌积分榜 + 联赛 logo（来自「进球数」报告） ----------
html = open(os.path.join(WS, "football_big5_goals.html"),
            encoding="utf-8").read()
i = html.find("window.DATA"); seg = html[i:]; eq = seg.find("="); rest = seg[eq + 1:].lstrip()
depth = 0; instr = False; esc = False; end = None
for idx, ch in enumerate(rest):
    if esc: esc = False; continue
    if ch == "\\": esc = True; continue
    if ch == '"': instr = not instr; continue
    if instr: continue
    if ch == "{": depth += 1
    elif ch == "}":
        depth -= 1
        if depth == 0: end = idx + 1; break
EMB = json.loads(rest[:end])
EMB_LG = {lg["code"]: lg for lg in EMB["leagues"]}

CN = json.load(open(f"{WS}/assets/cn_map.json", encoding="utf-8"))

# deduct_map 来自 standings（顶级联赛用 "top" 分组台账）。


def apply_deduct(tbl, deduct):
    """内嵌积分榜（赛果不全时的回退路径）同样要扣掉罚分并重排名次。"""
    if not deduct:
        return tbl
    new = {n: pts - deduct.get(club_core(n), 0) for n, (_, pts) in tbl.items()}
    order = sorted(new, key=lambda n: (-new[n], tbl.get(n, (0, 0))[0]))
    return {n: (i + 1, new[n]) for i, n in enumerate(order)}
CRESTS = json.load(open(f"{WS}/assets/crests.json", encoding="utf-8"))

# 队名别名桥接（仅法甲 6 队）：openfootball 简称 ↔ 队徽/积分榜官方全名。
ALIAS = GOALS_ALIAS

def lookup(dic, name, default=""):
    return dic.get(name) or dic.get(ALIAS.get(name, ""), default)
    return dic.get(name) or dic.get(ALIAS.get(name, ""), default)


def embedded_table(code, season):
    lg = EMB_LG.get(code)
    sc = (lg or {}).get("scopes", {}).get(season)
    if not sc:
        return {}
    tt = sc["teams"]
    if isinstance(tt, str):
        tt = ast.literal_eval(tt)
    return {t["name"]: (int(t["rank"]), int(t["pts"])) for t in tt}


def teams_of(code, season):
    return {canon(t) for m in load(code, season) for t in (m["team1"], m["team2"])}


def emb_teams(code, season):
    """内嵌积分榜里的某赛季名单（用于 2025-26 的降级判定：新赛季已开踢，名单是真实的）"""
    lg = EMB_LG.get(code)
    sc = (lg or {}).get("scopes", {}).get(season)
    if not sc:
        return set()
    tt = sc["teams"]
    if isinstance(tt, str):
        tt = ast.literal_eval(tt)
    return {canon(t["name"]) for t in tt}


def rel_n(nteams):
    """直接降级名额（用于「下赛季名单缺失」的回退判定）"""
    return 3 if nteams >= 20 else 2


def assign_rounds(recs, nteams):
    """由赛果本身推导真实轮次，返回与 recs 等长的轮次号列表（从 1 连续编号）。

    为什么不直接用 openfootball 的 round 字段：进行中的赛季里它并不可靠 —— 会跳号、
    同一队两场被标成同一轮（西甲 2026-27 巴塞罗那前两场都写作 "2. Round"），
    甚至整段沿用上赛季编号，于是第 1 场比赛在悬浮层里显示成「第 5 轮 / 第 7 轮」。
    这里改成按日期贪心分轮：每轮最多 nteams//2 场，且同一队在同一轮只能出现一次，
    补赛自然被推到后面的轮次，从根本上保证「每队每轮恰好一场、轮次连续」。"""
    per = max(1, nteams // 2)
    order = sorted(range(len(recs)),
                   key=lambda i: (recs[i]["date"] or "9999-99-99", recs[i]["idx"]))
    out = [1] * len(recs)
    cur, used, cnt = 1, set(), 0
    for i in order:
        r = recs[i]
        if cnt >= per or r["t1"] in used or r["t2"] in used:
            cur += 1
            used, cnt = set(), 0
        out[i] = cur
        used.add(r["t1"]); used.add(r["t2"]); cnt += 1
    return out


def rounds_sane(recs, nteams):
    """判断数据源自带的 round 字段是否可信。

    已结束的完整赛季里，轮次是官方编号，直接采信（补赛、改期都已被编号吸收，
    任何重排都会把 38 轮撑成 40+ 轮）。只有出现下列任一情况才认为不可信、
    交给 assign_rounds() 兜底：
      · round 为空 / 非数字
      · 轮次越界（<1 或 > (队数-1)*2）
      · 同一支队在同一轮出现两次（西甲 2026-27 巴塞罗那前两场都写作 "2. Round"）
      · 轮次集合不是从 1 起的连续整数
      · 最大轮次超出「已赛场次」能支撑的范围（例如只打了 3 轮却出现第 7 轮）
    """
    per = max(1, nteams // 2)
    exp_r = (nteams - 1) * 2
    per_team, vals = {}, set()
    for r in recs:
        rn = re.sub(r"\D", "", str(r.get("round", "")))
        if not rn:
            return False
        n = int(rn)
        if n < 1 or n > exp_r:
            return False
        vals.add(n)
        for t in (r["t1"], r["t2"]):
            s = per_team.setdefault(t, set())
            if n in s:
                return False
            s.add(n)
    if not vals or min(vals) != 1:
        return False
    if sorted(vals) != list(range(1, len(vals) + 1)):
        return False
    if max(vals) > -(-len(recs) // per) + 1:
        return False
    return True


def build_cross(league_seasons, win=None):
    """跨赛季汇总：谁在连续稳定地输出平局。
    win —— 赛季窗口（新 → 旧）；默认使用不含进行中 2026-27 的五季窗口。"""
    WIN = win or WINDOW_5
    OLD2NEW = WIN[::-1]
    # 各季每队场次：20 队 → 38 场；18 队 → 34 场（法甲 2023-24 起缩编）
    MPER = {s: 2 * (league_seasons[s]["nteams"] - 1) for s in OLD2NEW}
    agg = {}
    for s in OLD2NEW:
        for t in league_seasons[s]["teams"]:
            r = agg.setdefault(t["name"], {"cn": t["cn"], "per": {}, "maxStreak": -1, "gap": -1,
                                           "streakSeason": None, "gapSeason": None,
                                           "d00": 0, "d11": 0, "d22": 0, "dother": 0,
                                           "formSeq": [], "formBySeason": [], "formCounts": {"W": 0, "D": 0, "L": 0}, "formMatches": 0})
            r["per"][s] = t["draws"]
            r["formBySeason"].append({"season": s, "seq": t.get("formSeq", []), "matches": t.get("formMatches", 0)})
            r["formSeq"].extend(t.get("formSeq", []))
            r["formMatches"] += t.get("formMatches", 0)
            for fk in ("W", "D", "L"):
                r["formCounts"][fk] += t.get("formCounts", {}).get(fk, 0)
            # 跨赛季取各季最长连平 / 最长无平局间隔，并记录发生在哪个赛季（≥ 取最新季）
            if t["streak"] >= r["maxStreak"]:
                r["maxStreak"] = t["streak"]; r["streakSeason"] = s
            if t["gap"] >= r["gap"]:
                r["gap"] = t["gap"]; r["gapSeason"] = s
            for k in ("d00", "d11", "d22", "dother"):
                r[k] += t[k]
    cross = []
    for name, r in agg.items():
        per = [r["per"].get(s) for s in OLD2NEW]
        v = [x for x in per if x is not None]
        k = len(v)
        # 实际参赛场次（法甲跨 38 轮 / 34 轮两种赛制，不能用 38×k 估算）
        matches = sum(MPER[s] for i, s in enumerate(OLD2NEW) if per[i] is not None)
        cross.append({
            "name": name, "cn": r["cn"], "seasons": k, "per": per, "matches": matches,
            "total": sum(v), "avgSeason": round(sum(v) / k, 1),
            "rate": round(sum(v) / matches * 100, 2),
            "every": round(matches / sum(v), 2) if sum(v) else None,
            "min": min(v), "max": max(v), "range": max(v) - min(v),
            "sd": round(statistics.pstdev(v), 2) if k > 1 else 0.0,
            "maxStreak": r["maxStreak"],
            "streakSeason": r["streakSeason"],
            "gap": r["gap"],
            "gapSeason": r["gapSeason"],
            "d00": r["d00"], "d11": r["d11"], "d22": r["d22"], "dother": r["dother"],
            "formSeq": r["formSeq"], "formBySeason": r["formBySeason"], "formCounts": r["formCounts"], "formMatches": r["formMatches"],
        })
    cross.sort(key=lambda x: (-x["total"], x["cn"]))
    for i, c in enumerate(cross, 1):
        c["rank"] = i
    full = [c for c in cross if c["seasons"] == len(OLD2NEW)]
    # 「稳定输出」的门槛随联赛规模缩放：每季 38 场 → 8 场；德甲/法甲每季 34 场 → 7 场
    s0 = league_seasons[WIN[0]]
    per_season_matches = 2 * s0["totalMatches"] // s0["nteams"]   # 每队每季场次：38 或 34
    th = 8 if per_season_matches >= 38 else 7
    th10 = 10 if per_season_matches >= 38 else 9
    stable = [c for c in full if c["min"] >= th]
    stable_hi = [c for c in full if c["min"] >= th10]
    steady = sorted(full, key=lambda c: c["sd"])[:3]
    top = cross[0]
    return {
        "seasonSeq": OLD2NEW, "teams": cross,
        "meta": {
            "nTeams": len(cross), "nFull": len(full), "th": th, "thHi": th10,
            "stable": [c["cn"] for c in stable],
            "stableHi": [c["cn"] for c in stable_hi],
            "topTotal": {"cn": top["cn"], "total": top["total"], "per": top["per"],
                         "min": min(x for x in top["per"] if x is not None)},
            "steady": [{"cn": c["cn"], "sd": c["sd"], "range": c["range"]} for c in steady],
        },
    }


out = {"leagues": [], "seasonOrder": SEASONS, "cats": CATS,
       "logoByCode": {}, "crestByTeam": {}}
summary = []

for LG in LEAGUES:
    code, cn_name = LG["code"], LG["cn"]
    out["logoByCode"][code] = EMB_LG[code]["logo"]

    # 预取名单（含基准年）
    lists = {BASE_SEASON: teams_of(code, BASE_SEASON)}
    for s in SEASONS:
        lists[s] = teams_of(code, s)
    PREV = {SEASONS[k]: lists[SEASONS[k + 1]] if k + 1 < len(SEASONS) else lists[BASE_SEASON]
            for k in range(len(SEASONS))}
    NEXT = {SEASONS[k]: lists[SEASONS[k - 1]] if k - 1 >= 0 else None for k in range(len(SEASONS))}
    PREV_C = {k: core_set(v) for k, v in PREV.items()}
    NEXT_C = {k: core_set(v) for k, v in NEXT.items() if v}
    # 最新赛季（现为 2026-27）的下赛季名单：赛季正在进行、下季名单还不存在，
    # 内嵌榜里也查不到（emb_teams 返回空集），因此保持 None —— 降级回退到
    # 「积分榜末 N 位推断」并在页面标注，绝不用预测名单充数。
    _y1, _y2 = SEASONS[0].split("-")
    nxt = emb_teams(code, f"{int(_y1) + 1}-{int(_y2) + 1}")
    if nxt and len(nxt) >= len(lists[SEASONS[0]]):
        NEXT[SEASONS[0]] = nxt

    seasons = {}
    for season in SEASONS:
        ms = load(code, season)
        recs = []
        for idx, m in enumerate(ms):
            if not is_regular_match(m):
                continue
            p = parse_score(m)
            if not p or None in p:
                continue
            recs.append({"date": m.get("date", ""), "round": m.get("round", ""), "idx": idx,
                         "t1": canon(m["team1"]), "t2": canon(m["team2"]), "h": p[0], "a": p[1]})
        # 轮次：优先采信数据源官方编号；只有 rounds_sane() 判定不可信时才由赛果兜底推导
        _nteams_rd = len({r["t1"] for r in recs} | {r["t2"] for r in recs})
        _full_rd = _nteams_rd * (_nteams_rd - 1)          # 完整赛季总场次
        _incomplete = not _full_rd or len(recs) < 0.9 * _full_rd
        # 官方轮次（2026-27 由 build_2026_27.py 从 openfootball 赛程对齐写入）一律可信，
        # 禁止任何重排：它天然允许「第 6 轮提前踢、第 1 轮推迟到二周后」这类非连续编号。
        _official = load_meta(code, season).get("roundSource") == "official"
        # 只对「进行中赛季」重排：已结束赛季即使标签偶有瑕疵，官方轮次编号的整体结构
        # （38/34 轮）是重排算法还原不出来的，硬排会把 38 轮撑成 40+ 轮。
        if not _official and _incomplete and not rounds_sane(recs, _nteams_rd):
            print("    [轮次] %s %s 数据源轮次不可信（跳号/重复/越界），已按赛果重排 %d 场"
                  % (cn_name, season, len(recs)))
            for r, n in zip(recs, assign_rounds(recs, _nteams_rd)):
                r["round"] = str(n)
        total = len(recs)
        draws = [r for r in recs if r["h"] == r["a"]]
        td = len(draws)

        dist = Counter(cat(r["h"]) for r in draws)
        overall = [{"score": c, "n": dist.get(c, 0),
                    "pct": round(dist.get(c, 0) / td * 100, 2) if td else 0,
                    "pctMatch": round(dist.get(c, 0) / total * 100, 2)} for c in CATS]

        rounds = sorted({r["round"] for r in recs}, key=lambda x: int(re.sub(r"\D", "", x) or 0))
        rd = defaultdict(int)
        rdraws = defaultdict(list)          # 每轮平局明细（队名+比分），供「各轮走势」悬浮框展示
        for r in recs:
            if r["h"] == r["a"]:
                rd[r["round"]] += 1
                rdraws[r["round"]].append((r["t1"], r["t2"], r["h"], r["a"], r.get("date", "")))
        per_round = []
        for rn in rounds:
            # 同轮多场平局按比赛日期升序，悬浮框里阅读更自然
            dl = sorted(rdraws.get(rn, []), key=lambda x: (x[4] or "9999-99-99"))
            per_round.append({
                "round": rn, "n": rd.get(rn, 0),
                "draws": [{"h": lookup(CN, t1, t1), "a": lookup(CN, t2, t2),
                           "hs": int(h), "as": int(a)} for (t1, t2, h, a, _) in dl],
            })

        tm = defaultdict(list)
        for r in recs:
            tm[r["t1"]].append(r)
            tm[r["t2"]].append(r)

        emb = embedded_table(code, season)
        ded = deduct_map(code, season)
        comp = compute_table([m for m in ms if is_regular_match(m)], TIE_RULE.get(code, "gd"), ded)
        nteams = len(tm)

        prevSet, nextSet = PREV.get(season), NEXT.get(season)
        # 五大联赛规模只有 18 或 20 队，所以「下赛季名单 ≥ 18 队」即可认为是完整名单。
        # 不能用 >= nteams：法甲 2022-23(20队) → 2023-24(18队) 缩编，
        # 真实名单 18 队反被当成不完整，导致本该 4 队降级被误推断成末 3 位。
        nextFull = nextSet is not None and len(nextSet) >= 18
        curComplete = total >= nteams * (nteams - 1)
        relegN = rel_n(nteams)

        # 赛果覆盖到全部队伍（当前赛季多数轮次已开踢）时，也以「由赛果计算的积分榜」为准。
        # 内嵌积分榜是人工维护、更新滞后，进行中赛季很容易和真实赛果脱节
        # （如曼城已 3 连胜却仍显示 6 分）——这是 2026-27「轮次对、积分榜没更新」的根因。
        # 仅当赛果残缺到队伍都不齐（如赛季刚开局个别队尚未出场）时，才回退内嵌积分榜，避免名次错乱。
        coverage_complete = len(comp) >= nteams
        src = comp if (curComplete or coverage_complete) else apply_deduct(emb, ded)
        # 逐场明细里的对手用「本季球队数组下标」表示 —— 下标即 teams 按排名排序后的位置，
        # 前端可直接 teams[i].cn 取到中文名，避免在每条明细里重复存队名、把 JSON 撑大。
        # sorted / list.sort 同为稳定排序且输入顺序都是 tm 的插入顺序，两边下标严格一一对应。
        idx_of = {n: i for i, n in enumerate(sorted(tm.keys(), key=lambda n: src.get(n, (0, 0))))}

        teams = []
        for name, ml in tm.items():
            # 所有赛季（含进行中的 2026-27）统一按「日期顺序」展示：色块要反映球队数据的
            # 真实演变过程，日期序 = 比赛真实发生顺序，这才是最准确的口径。轮次号因此可能
            # 不单调（补赛/提前进行的轮次会让日期与轮次错位），但这是可接受的代价。
            # 若按轮次排，反而会把「最长连平 / 最长无平局间隔」算在错误的序列上
            # （轮次序 ≠ 真实比赛序）。streak/gap 与色带用同一份 ml，跟随日期序重算。
            ml.sort(key=lambda r: (r["date"] or "9999-99-99",
                                   int(re.sub(r"\D", "", r["round"]) or 0), r["idx"]))
            dc = Counter(cat(r["h"]) for r in ml if r["h"] == r["a"])
            dtot = sum(dc.values())
            form_seq = []
            form_detail = []
            form_counts = {"W": 0, "D": 0, "L": 0}
            for r in ml:
                if r["h"] == r["a"]:
                    result = "D"
                elif (r["t1"] == name and r["h"] > r["a"]) or (r["t2"] == name and r["a"] > r["h"]):
                    result = "W"
                else:
                    result = "L"
                form_seq.append(result)
                form_counts[result] += 1
                # 明细格式：轮次|日期|主客|对手下标|本队进球-对手进球
                _ha = "H" if r["t1"] == name else "A"
                _opp = r["t2"] if _ha == "H" else r["t1"]
                _gf, _ga = (r["h"], r["a"]) if _ha == "H" else (r["a"], r["h"])
                _rn = re.sub(r"\D", "", str(r.get("round", ""))) or "0"
                form_detail.append("|".join([_rn, str(r.get("date", "")), _ha,
                                             str(idx_of.get(_opp, -1)), f"{_gf}-{_ga}"]))
            maxd = cur = maxg = curg = 0
            for r in ml:
                if r["h"] == r["a"]:
                    cur += 1; maxd = max(maxd, cur); maxg = max(maxg, curg); curg = 0
                else:
                    cur = 0; curg += 1
            maxg = max(maxg, curg)

            rank, pts = src.get(name, (0, 0))
            _core = club_core(name)
            _ded = ded.get(_core, 0)
            promo = (prevSet is not None) and (not in_cores(_core, PREV_C.get(season, set())))
            if nextFull:
                releg = not in_cores(_core, NEXT_C.get(season, set()))
            elif curComplete:
                releg = rank > nteams - relegN
            else:
                releg = False

            # 平均几轮出一次平局 = 赛季轮数 ÷ 平局场次（数值越小＝越容易出平局）
            # 全季 0 平局时为 None，页面显示「—」，排序时按无穷大处理
            every = round(len(rounds) / dtot, 2) if dtot else None
            teams.append({"name": name, "cn": lookup(CN, name, name), "rank": rank, "pts": pts, "deduct": _ded,
                          "draws": dtot, "d00": dc.get("0-0", 0), "d11": dc.get("1-1", 0),
                          "d22": dc.get("2-2", 0), "dother": dc.get("其他", 0),
                          "streak": maxd, "gap": maxg, "every": every,
                          "formSeq": form_seq, "formCounts": form_counts, "formMatches": len(form_seq),
                          "formDetail": form_detail,
                          "promo": promo, "releg": releg})
        teams.sort(key=lambda x: x["rank"])

        note = "" if nextFull else f"降级按积分榜末 {relegN} 位推断（{SEASONS[0]} 赛季尚在进行，下季名单未定）"
        seasons[season] = {
            "season": season, "totalMatches": total, "totalDraws": td,
            "drawRate": round(td / total * 100, 2), "nteams": nteams,
            "perRoundCount": nteams // 2, "rounds": len(per_round),
            # 最大轮次号：进行中赛季可能出现「第 6 轮提前踢」导致的跳号，横轴/文案用它
            "roundMax": max([int(re.sub(r"\D", "", r) or 0) for r in rounds] or [len(per_round)]),
            "overall": overall, "perRound": per_round, "teams": teams, "note": note,
            # 升降级标记是否来自「已裁定的下赛季名单」：进行中的赛季下季名单未定，不显示升降 icon
            "moveFinal": bool(nextFull),
        }
        for t in teams:
            out["crestByTeam"][t["name"]] = lookup(CRESTS, t["name"], "")

    cross = build_cross(seasons)                       # 近 5 季
    cross3 = build_cross(seasons, WINDOW_3)            # 近 3 季（不含进行中的 2026-27）
    out["leagues"].append({
        "code": code, "cn": cn_name, "name": LG["name"], "seasons": seasons,
        "cross": cross, "cross3": cross3,
    })

    # 控制台校验
    line = []
    for s in SEASONS:
        sc = seasons[s]
        line.append(f"{s}: {sc['totalMatches']}场/{sc['totalDraws']}平({sc['drawRate']}%)")
    npromo = sum(1 for t in seasons[SEASONS[0]]["teams"] if t["promo"])
    nreleg = sum(1 for t in seasons[SEASONS[0]]["teams"] if t["releg"])
    summary.append((cn_name, line, len(cross["teams"]), cross["meta"]["nFull"],
                    cross["meta"]["stable"], npromo, nreleg))

# ---------- 五大联赛对照 ----------
def build_compare(win):
    """五大联赛横向对照。win = 赛季窗口（新 → 旧），同时决定用 cross 还是 cross3"""
    key = "cross" if list(win) == WINDOW_5 else "cross3"
    rows = []
    for LG in out["leagues"]:
        ss = [LG["seasons"][s] for s in win]
        tm = sum(x["totalMatches"] for x in ss)
        td = sum(x["totalDraws"] for x in ss)
        bk = {c: sum(next(o["n"] for o in x["overall"] if o["score"] == c) for x in ss) for c in CATS}
        cx = LG[key]
        rows.append({
            "code": LG["code"], "cn": LG["cn"], "name": LG["name"],
            "totalMatches": tm, "totalDraws": td, "drawRate": round(td / tm * 100, 2),
            "rates": [x["drawRate"] for x in reversed(ss)],          # 老 → 新
            "buckets": [bk[c] for c in CATS],
            "bucketPct": [round(bk[c] / td * 100, 2) for c in CATS],
            "nTeams": cx["meta"]["nTeams"], "nFull": cx["meta"]["nFull"],
            "stable": cx["meta"]["stable"],
            "top": {"cn": cx["teams"][0]["cn"], "total": cx["teams"][0]["total"]},
        })
    rows.sort(key=lambda r: -r["drawRate"])
    return {"rows": rows, "seasonSeq": win[::-1]}


cmp_rows = build_compare(WINDOW_5)["rows"]
out["compare"] = build_compare(WINDOW_5)          # 近 5 季（不含进行中的 2026-27）
out["compare3"] = build_compare(WINDOW_3)         # 近 3 季（不含进行中的 2026-27）

# ---------- 元信息（页脚展示）----------
# 数据源更新时间：优先用「抓取步骤」显式落盘的时间戳文件（data/_fetch_stamp.txt），
# 并取其与原始赛果 JSON 最大 mtime 的较大者 —— 这样它反映真实的「数据最近一次抓取/更新」时刻，
# 而不是被后续构建步骤的文件 mtime 覆盖，从而避免与「本页更新(generated)」撞成同一个时间。
# 2026-27 等可能被单独更新的数据源，靠 max mtime 兜底，避免把时间「拉旧」。
import time as _time
_src_ts = 0
for _f in os.listdir(D):
    if _f.endswith(".json") and re.match(r"^[a-z]{2}\.1\.\d{4}[-_]\d{2}\.json$", _f):
        _src_ts = max(_src_ts, int(os.path.getmtime(os.path.join(D, _f))))
_stamp_p = os.path.join(D, "_fetch_stamp.txt")
_src_txt = open(_stamp_p, encoding="utf-8").read().strip() if os.path.exists(_stamp_p) else ""
out["meta"] = {
    "srcUpdated": _src_txt or (_time.strftime("%Y-%m-%d %H:%M", _time.localtime(_src_ts)) if _src_ts else ""),
    "generated": _time.strftime("%Y-%m-%d %H:%M", _time.localtime()),
    "windows": [5, 3],
}

json.dump(out, open(f"{WS}/data/report_all.json", "w"), ensure_ascii=False, indent=1)

print("=== 各联赛逐季（场次/平局数(平局率)）===")
for cn_name, line, nt, nf, st, np_, nr in summary:
    print(f"\n【{cn_name}】球队 {nt} 支 / 五季全勤 {nf} 支 / 稳定输出 {len(st)} 支 {st} / {SEASONS[0]} 升{np_} 降{nr}")
    for x in line:
        print("   ", x)
print("\n=== 五大联赛五年合计（按平局率排序）===")
print(f"{'联赛':6s} {'场次':>5s} {'平局':>5s} {'平局率':>7s}  0-0/1-1/2-2/其他")
for r in cmp_rows:
    print(f"{r['cn']:6s} {r['totalMatches']:5d} {r['totalDraws']:5d} {r['drawRate']:6.2f}%  {r['buckets']}  五年平局最多：{r['top']['cn']} {r['top']['total']}")
print("\nwritten:", f"{WS}/data/report_all.json")
