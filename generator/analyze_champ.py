# -*- coding: utf-8 -*-
"""五大次级联赛（英冠/西乙/德乙/法乙/意乙）近 5 个赛季（2022-23 ~ 2026-27）平局统计。
数据来源：openfootball
  - 英冠 / 德乙：football.json 仓库的 JSON（en.2 / de.2）
  - 西乙 / 意乙 / 法乙：football.json 只对部分赛季收录 JSON（2024-25 / 2025-26 有），
    2021-22 ~ 2023-24 只有 82 字节的空占位文件，必须回退到各国仓库的 TXT
    （espana 2-liga2 / italy 2-serieb / france *_fr2）补齐。
  - load() 统一策略：先试 JSON（解析成功且有比赛就用），否则回退 TXT。
    两种格式规范化为相同结构的赛果记录，下游分析逻辑与顶级联赛完全一致。
列标题/名次/积分：由赛果直接计算（compute_table），不依赖外部积分榜；升/降班马用上下赛季名单差集判定。
"""
import json, re, os, statistics, urllib.parse
from collections import Counter, defaultdict
from standings import (compute_table, club_core, canon_identity, core_set,
                       cores_match, in_cores, deduct_map, TIE_RULE,
                       parse_score, is_regular_match)
canon = canon_identity

import os
WS = os.path.dirname(os.path.abspath(__file__))
D = f"{WS}/data"

LEAGUES = [
    {"code": "en", "cn": "英冠", "src": "json", "name": "英格兰冠军联赛", "color": "#c8102e"},
    {"code": "es", "cn": "西乙", "src": "txt",  "name": "西班牙乙级联赛", "color": "#e07b00"},
    {"code": "de", "cn": "德乙", "src": "json", "name": "德国乙级联赛", "color": "#1a1a1a"},
    {"code": "it", "cn": "意乙", "src": "txt",  "name": "意大利乙级联赛", "color": "#0072b9"},
    {"code": "fr", "cn": "法乙", "src": "txt",  "name": "法国乙级联赛", "color": "#0b1f3a"},
]
SEASONS = ["2026-27", "2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]   # 新 → 旧；2026-27 仅作当前赛季展示
BASE_SEASON = "2020-21"     # 仅作窗口内最老赛季（2021-22）的升班马基准
# 总览窗口排除进行中的 2026-27：五季=2021-22~2025-26，三季=2023-24~2025-26。
WINDOW_5 = ["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"]
WINDOW_3 = ["2025-26", "2024-25", "2023-24"]
# 说明：2026-27 赛季正在进行中，只录入了开季前几轮的真实赛果（五大次级联赛分别约
# 20~48 场），场次/平局数均按实际已赛场次统计，绝不做外推或补齐（宁缺勿造）。
# 报告里该赛季会标注「进行中」，读者据此理解其平局率仍不稳定。
# 注：2025-26 的 openfootball 源只录入了部分场次比分（赛程齐全但后段无 score），
# 已用 football-data.co.uk 同赛季完整赛果回填（见 patch_2025_26.py，按主客队配对，共补 798 场，
# 冲突场次一律保留原值、绝不编造）。回填后 2025-26 完整度：
#   英冠 557/557、西乙 462/462、德乙 306/306、意乙 380/380、法乙 305/306
# 法乙缺的 1 场在权威源亦无结果，故留空不补（宁缺勿造）。
CATS = ["0-0", "1-1", "2-2", "其他"]


# 译名：先取次级联赛专有表 cn_map_champ.json（覆盖绝大多数二级球队），
# 再用顶级联赛的公共表 cn_map.json 兜底（降级队如莱斯特城等已在公共表里）。
CN = {}
if os.path.exists(f"{WS}/assets/cn_map.json"):
    CN.update(json.load(open(f"{WS}/assets/cn_map.json", encoding="utf-8")))
if os.path.exists(f"{WS}/assets/cn_map_champ.json"):
    CN.update(json.load(open(f"{WS}/assets/cn_map_champ.json", encoding="utf-8")))

# ---------------------------------------------------------------------------
# 联赛扣分（罚分）台账。openfootball 原始数据只有赛果，不含纪律 / 财务扣罚，
# 因此这里单独维护：积分榜 = 赛果积分 - 扣分，名次按罚后积分重排。
# 次级联赛扣分比顶级更常见，典型例子：
#   英冠 2021-22 德比郡 -21（进入托管 -12 + 违反 PSR -9，55 → 34，名次 17 → 23）、雷丁 -6；
#   英冠 2025-26 谢菲尔德星期三 -18、莱斯特城 -6、西布罗姆维奇 -2；
#   意乙 2022-23 热那亚 -1 / 帕尔马 -1 / 雷吉纳 -5；法乙 2022-23 圣埃蒂安 -3。
# 匹配走 club_core() 归一化，避免「Reggina 1914 / Reggina」这类写法差异漏配。
# 行政降级 / 注册除名（非竞技原因离队）：见 assets/demotions.json。这类队不在降级区，
# 不能标成竞技降班马，单独给一个「行政降级」标记。
DEMOTE_ALL = json.load(open(f"{WS}/assets/demotions.json", encoding="utf-8"))


def demote_map(code, season):
    """{核心名: {cn/en/to/reason}} —— 行政降级 / 除名，空字典表示该赛季无。"""
    node = (DEMOTE_ALL.get(code) or {}).get(season) or []
    return {club_core(i["en"]): i for i in node if i.get("en")}
# 队徽：先加载顶级联赛队徽库作兜底（升降级球队同名同队可直接复用），
# 再用次级联赛专用表覆盖——后者是本次专门抓取的二级球队队徽，优先命中。
CRESTS = {}
if os.path.exists(f"{WS}/assets/crests.json"):
    CRESTS.update(json.load(open(f"{WS}/assets/crests.json", encoding="utf-8")))
if os.path.exists(f"{WS}/assets/crests_champ.json"):
    CRESTS.update(json.load(open(f"{WS}/assets/crests_champ.json", encoding="utf-8")))
# 联赛 logo：真实徽标图片（en.2/es.2/de.2/it.2/fr.2），抓不到时才回落生成的色块徽
LGLOGOS = {}
_p = f"{WS}/assets/league_logos_champ.json"
if os.path.exists(_p):
    LGLOGOS.update(json.load(open(_p, encoding="utf-8")))
EMB_LG = {}   # 次级联赛无内嵌顶级积分榜可复用，置空即可（embedded_table/emb_teams 会安全返回空）


def fpath_json(code, season):
    if code == "en" and season == "2025-26":
        return os.path.join(D, "en.2.2025_26.json")
    return os.path.join(D, f"{code}.2.{season}.json")


def fpath_txt(code, season):
    return os.path.join(D, f"{code}.2.{season}.txt")


def load_meta(code, season):
    """读取赛季数据文件的顶层元信息（2026-27 用它判断轮次是否已采信官方编号）。"""
    p = fpath_json(code, season)
    if not os.path.exists(p):
        return {}
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return {}


# ---------- openfootball TXT 解析（西乙/意乙/法乙） ----------
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def parse_txt(text, season):
    """把 openfootball 各国 TXT 规范化为与 football.json JSON 相同结构的赛果记录列表。
    记录字段：date(str YYYY-MM-DD) / round(str, 含数字) / team1 / team2 / score([h,a])。"""
    matches = []
    cur_round = None
    cur_phase = "reg"          # reg=常规赛 / po=升降级附加赛
    last_num = 0
    start_year = None
    cur_year = None
    cur_mon = None
    cur_day = None
    lines = text.split("\n")
    for raw in lines:
        s = raw.rstrip("\n")
        if not s.strip():
            continue
        if s.startswith("="):
            yrs = re.findall(r"(\d{4})", s)
            if yrs:
                start_year = int(yrs[0][:4])
            continue
        if s.startswith("#"):
            continue
        if s.startswith("▪"):
            head = s[1:].strip()
            nm = re.search(r"(\d+)", s)
            # 只有「Matchday N」/ 纯数字段落算常规赛。
            # 「Round 1」「Semifinals」「Final」「Playoff, ...」「Playout, ...」等一律是
            # 升降级附加赛——注意不能只看数字：「▪ Round 1」含数字 1，旧逻辑会误判成
            # 第 1 轮常规赛，导致意乙每个赛季多算 2 场（380 → 382）。
            if re.search(r"matchday", head, re.I) or re.fullmatch(r"\d+", head):
                cur_phase = "reg"
                if nm:
                    cur_round = int(nm.group(1))
                    last_num = max(last_num, cur_round)
                else:
                    last_num += 1
                    cur_round = last_num
            else:
                cur_phase = "po"
                last_num += 1
                cur_round = last_num   # 附加赛段落：排在常规赛季之后
            continue
        # 日期行：Fri Aug 13 或  Sat Jul 24 2021（法乙带年份）
        dm = re.match(r"\s*([A-Za-z]{3})\s+([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?", s)
        if dm:
            cur_mon = _MONTHS.get(dm.group(2)[:3])
            cur_day = int(dm.group(3))
            yr = dm.group(4)
            if yr:
                cur_year = int(yr)
            elif start_year is not None and cur_mon is not None:
                cur_year = start_year if cur_mon >= 8 else start_year + 1
            continue
        # 比赛行：可选的 HH:MM + 队1 + 比分 + 队2（法乙在队1/队2 间有 ' v '）
        noht = re.sub(r"\([^)]*\)", "", s)            # 去掉半场比分 (x-y)
        noht = re.sub(r"\[[^\]]*\]", "", noht)        # 去掉 [awarded] 之类注记
        sm = re.search(r"(\d+)-(\d+)", noht)
        if not sm:
            continue
        # 去掉行首的 HH:MM（它位于比分之前，不能算进队名）
        noht = re.sub(r"^\s*\d{1,2}:\d{2}\s+", "", noht).strip()
        # 去掉行首的加时/点球注记（意乙季后赛 TXT 写作 "a.e.t. / pen."），否则会被吞进队名
        noht = re.sub(r"^\s*(?:a\.?e\.?t\.?|pen\.?|pens|after extra time)\s*", "", noht, flags=re.I)
        sm = re.search(r"(\d+)-(\d+)", noht)
        if not sm:
            continue
        before = noht[:sm.start()].strip()
        after = noht[sm.end():].strip()
        h, a = int(sm.group(1)), int(sm.group(2))
        if re.search(r"\sv\s", before, re.I):          # 法乙：Team1 v Team2 Score
            parts = re.split(r"\sv\s", before, maxsplit=1, flags=re.I)
            t1 = parts[0].strip()
            t2 = parts[1].strip() if len(parts) > 1 else ""
        else:
            t1 = before.strip()
            t2 = after.strip()
        t1 = re.sub(r"\s+", " ", t1).strip()           # 合并多余空白
        t2 = re.sub(r"\s+", " ", t2).strip()
        if not t1 or not t2:
            continue
        date_str = f"{cur_year:04d}-{cur_mon:02d}-{cur_day:02d}" if (cur_year and cur_mon and cur_day) else ""
        matches.append({"date": date_str, "round": str(cur_round) if cur_round else "0",
                        "phase": cur_phase,
                        "team1": t1, "team2": t2, "score": [h, a]})
    return matches


def clean_team(n):
    """统一清洗队名：去掉加时/点球注记、方括号注记，合并多余空白。
    意乙 TXT 里注记写在比分之后（"... 4-2 a.e.t. (2-2, 1-1)  Brescia Calcio"），
    会被误当作队名的一部分，必须在两条解析路径上统一清理。"""
    n = re.sub(r"\[[^\]]*\]", " ", str(n))                       # [awarded] 等
    n = re.sub(r"\s*\ba\.?\s?e\.?\s?t\.?\s*", " ", n, flags=re.I)  # a.e.t. / aet
    n = re.sub(r"\s*\bpen(?:s|\.)?\b\s*", " ", n, flags=re.I)      # pen. / pens
    return re.sub(r"\s+", " ", n).strip()


# 升降级附加赛段落识别：TXT 段落名 / JSON round 名命中即视为附加赛，不计入常规赛统计。
# 不能只靠「数字是否 ≤ 常规赛轮次」判断——"Playoff, Round 1" 里的 1 会被误当成第 1 轮。


def load(code, season):
    """优先使用 football.json 的 JSON；若该赛季 JSON 缺失或是空占位（西/意/法的
    2021-22 ~ 2023-24），则回退到各国仓库的 TXT。两条路径统一做队名清洗。"""
    pj = fpath_json(code, season)
    if os.path.exists(pj):
        try:
            ms = json.load(open(pj, encoding="utf-8")).get("matches") or []
            if ms:
                return _norm(ms)
        except Exception:
            pass                      # 空占位 / 解析失败 → 落到 TXT
    pt = fpath_txt(code, season)
    if os.path.exists(pt):
        return _norm(parse_txt(open(pt, encoding="utf-8").read(), season))
    raise FileNotFoundError(f"no data for {code} {season}")


def _norm(ms):
    for m in ms:
        m["team1"] = clean_team(m.get("team1", ""))
        m["team2"] = clean_team(m.get("team2", ""))
    return ms


LEAGUES_dict = {L["code"]: L for L in LEAGUES}


def cat(h):
    return {0: "0-0", 1: "1-1", 2: "2-2"}.get(h, "其他")



# ---------------------------------------------------------------------------
# 跨文件队名归一：openfootball 各赛季 / 各级别文件里同一支队的写法并不一致，例如
#   「FC St. Pauli」↔「FC St. Pauli 1910」、「CD Alavés」↔「Deportivo Alavés」、
#   「Pisa SC」↔「AC Pisa 1909」、「Werder Bremen」↔「SV Werder Bremen」。
# 直接做字符串比对，会把「上季从顶级降入」误判成「上季从次次级升入」。
# 这里抽掉成立年份（纯数字）与法律/冠词类通用词，用剩下的「核心名」做跨级别比对。
# 预备队（… B / II）的队名尾部标记会被保留，因此不会被并入一队。
# ---------------------------------------------------------------------------
def lookup(dic, name, default=""):
    return dic.get(name, default)


def embedded_table(code, season):
    return {}


def teams_of(code, season):
    return {canon(t) for m in load(code, season) for t in (m["team1"], m["team2"])}


def div_teams(code, div, season):
    """取某联赛某赛季（div=1 顶级 / 2 次级）的参赛队集合，用于判定跨级别流动。"""
    cands = [f"{D}/{code}.{div}.{season}.json",
             f"{D}/{code}.{div}.{season.replace('-', '_')}.json"]
    if code == "en" and season == "2025-26":
        cands = [f"{D}/{code}.{div}.2025_26.json"] + cands
    for pj in cands:
        if os.path.exists(pj):
            try:
                ms = json.load(open(pj, encoding="utf-8")).get("matches") or []
                if ms:
                    ms = _norm(ms)
                    return {canon(m["team1"]) for m in ms} | {canon(m["team2"]) for m in ms}
            except Exception:
                pass
    pt = f"{D}/{code}.{div}.{season}.txt"
    if os.path.exists(pt):
        ms = parse_txt(open(pt, encoding="utf-8").read(), season)
        return {canon(m["team1"]) for m in ms} | {canon(m["team2"]) for m in ms}
    return set()


def emb_teams(code, season):
    return set()


def rel_n(nteams):
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
    """数据源的 round 字段是否可信。

    可信的判据：每队在同一轮最多出场一次、轮次从 1 开始且连续不跳号、
    不超过该联赛的理论轮数、且不会明显超过已赛场次能支撑的轮数。
    完整赛季的官方轮次都满足；进行中的赛季一旦出现跳号（第 1 场却写着第 5 轮）
    或重复（同一队两场都写第 2 轮），就判定不可信、改用 assign_rounds() 推导。"""
    per = max(1, nteams // 2)
    exp_r = (nteams - 1) * 2            # 双循环联赛的理论轮数
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
            if n in s:                   # 同一队在同一轮出现两次 → 编号不可信
                return False
            s.add(n)
    if not vals or min(vals) != 1:
        return False
    if sorted(vals) != list(range(1, len(vals) + 1)):   # 跳号
        return False
    if max(vals) > -(-len(recs) // per) + 1:            # 超出已赛场次能支撑的轮数
        return False
    return True


def build_cross(league_seasons, win=None):
    WIN = win or WINDOW_5
    OLD2NEW = WIN[::-1]
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
        matches = sum(MPER[s] for i, s in enumerate(OLD2NEW) if per[i] is not None)
        cross.append({
            "name": name, "cn": r["cn"], "seasons": k, "per": per, "matches": matches,
            "total": sum(v), "avgSeason": round(sum(v) / k, 1),
            "rate": round(sum(v) / matches * 100, 2) if matches else 0,
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
    s0 = league_seasons[WIN[0]]
    per_season_matches = 2 * s0["totalMatches"] // s0["nteams"]
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


def league_badge(cn, color):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="42" height="26">'
           f'<rect width="42" height="26" rx="5" fill="{color}"/>'
           f'<text x="21" y="18" font-size="13" font-family="PingFang SC,Microsoft YaHei,sans-serif" '
           f'fill="#fff" text-anchor="middle" font-weight="700">{cn}</text></svg>')
    return 'data:image/svg+xml,' + urllib.parse.quote(svg)


out = {"leagues": [], "seasonOrder": SEASONS, "cats": CATS,
       "logoByCode": {}, "crestByTeam": {}}
summary = []

for LG in LEAGUES:
    code, cn_name = LG["code"], LG["cn"]
    out["logoByCode"][code] = LGLOGOS.get(code) or league_badge(cn_name, LG["color"])

    lists = {BASE_SEASON: teams_of(code, BASE_SEASON)}
    for s in SEASONS:
        lists[s] = teams_of(code, s)
    PREV = {SEASONS[k]: lists[SEASONS[k + 1]] if k + 1 < len(SEASONS) else lists[BASE_SEASON]
            for k in range(len(SEASONS))}
    NEXT = {SEASONS[k]: lists[SEASONS[k - 1]] if k - 1 >= 0 else None for k in range(len(SEASONS))}
    PREV_C = {k: core_set(v) for k, v in PREV.items()}
    NEXT_C = {k: core_set(v) for k, v in NEXT.items() if v}
    nxt = emb_teams(code, "2026-27")
    if nxt and len(nxt) >= len(lists[SEASONS[0]]):
        NEXT[SEASONS[0]] = nxt

    seasons = {}
    # 上一赛季顶级联赛（div=1）参赛队核心名集合：用于判定"从顶级联赛降级过来"的球队
    top_prev = {}
    for i, s in enumerate(SEASONS):
        ps = SEASONS[i + 1] if i + 1 < len(SEASONS) else BASE_SEASON
        top_prev[s] = core_set(div_teams(code, 1, ps))
    # 下一赛季顶级联赛（div=1）参赛队核心名集合：用于把"升上顶级"与"真降级"区分开
    top_next = {}
    for i, s in enumerate(SEASONS):
        ns = SEASONS[i - 1] if i - 1 >= 0 else None
        top_next[s] = core_set(div_teams(code, 1, ns)) if ns else set()
    for season in SEASONS:
        ms = load(code, season)
        # 剔除升降级附加赛（playoff）场次：round 为非数字（如 "Playoffs"/""）或数字超过
        # 2*(队数-1) 的比赛均视为附加赛，不计入联赛常规统计。
        _teams = set()
        for m in ms:
            p = parse_score(m)
            if p and None not in p:
                _teams.add(canon(m["team1"])); _teams.add(canon(m["team2"]))
        _nteams = len(_teams)
        _thr = 2 * (_nteams - 1) if _nteams else 10 ** 9
        def _is_reg(m):
            if not is_regular_match(m):
                return False
            num = re.sub(r"\D", "", str(m.get("round", "")))
            n = int(num) if num else 0
            return 0 < n <= _thr
        ms = [m for m in ms if _is_reg(m)]
        recs = []
        for idx, m in enumerate(ms):
            p = parse_score(m)
            if not p or None in p:
                continue
            recs.append({"date": m.get("date", ""), "round": m.get("round", ""), "idx": idx,
                         "t1": canon(m["team1"]), "t2": canon(m["team2"]), "h": p[0], "a": p[1]})
        # 数据源 round 不可信时（进行中赛季常见：跳号、重复、沿用上赛季编号），
        # 改由赛果推导真实轮次，保证 1..N 连续、每队每轮一场。
        _nteams_rd = len({r["t1"] for r in recs} | {r["t2"] for r in recs})
        _full_rd = _nteams_rd * (_nteams_rd - 1)          # 完整赛季总场次
        _incomplete = not _full_rd or len(recs) < 0.9 * _full_rd
        # 官方轮次（2026-27 由 build_2026_27.py 从 openfootball 赛程对齐写入）一律可信，
        # 禁止任何重排：它天然允许「第 6 轮提前踢、第 1 轮推迟到二周后」这类非连续编号。
        _official = load_meta(code, season).get("roundSource") == "official"
        # 只对「进行中赛季」重排：已结束赛季即使标签偶有瑕疵，官方轮次编号的整体结构
        # （46/42/38/34 轮）是重排算法还原不出来的，硬排会把 46 轮撑成 50+ 轮。
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

        ded = deduct_map(code, season, "champ")
        dmt = demote_map(code, season)
        comp = compute_table(ms, TIE_RULE.get(code, "gd"), ded, canon_identity)
        nteams = len(tm)

        prevSet, nextSet = PREV.get(season), NEXT.get(season)
        nextFull = nextSet is not None and len(nextSet) >= 18
        curComplete = total >= nteams * (nteams - 1)
        relegN = rel_n(nteams)
        # 下赛季顶级联赛名单：次级联赛里「升上顶级」不等于降级，必须先把这类队排除掉，
        # 否则「不在本联赛下季名单」会被误判成降班马（如考文垂这类升级队被标红）。
        topNextSet = top_next.get(season, set())

        # 逐场明细里的对手用「本季球队数组下标」表示 —— 下标即 teams 按排名排序后的位置，
        # 前端可直接 teams[i].cn 取到中文名，避免在每条明细里重复存队名、把 JSON 撑大。
        # sorted / list.sort 同为稳定排序且输入顺序都是 tm 的插入顺序，两边下标严格一一对应。
        idx_of = {n: i for i, n in enumerate(sorted(tm.keys(), key=lambda n: comp.get(n, (0, 0))))}

        teams = []
        for name, ml in tm.items():
            # 所有赛季（含进行中的 2026-27）统一按「日期顺序」展示：色块要反映球队数据的
            # 真实演变，日期序 = 比赛真实发生顺序，才是最准确的口径；轮次号可能不单调，
            # 但这是可接受的代价（按轮次排会把「最长连平 / 最长无平局间隔」算错）。
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

            src = comp   # 次级联赛无内嵌积分榜，直接以赛果计算的积分为准
            rank, pts = src.get(name, (0, 0))
            # 先区分“从顶级联赛降入”，再判定“从下一级升入”；降级队不能同时被标成升班马。
            _core = club_core(name)
            _ded = ded.get(_core, 0)
            fromTop = in_cores(_core, top_prev.get(season, set()))
            promo = (prevSet is not None) and (not in_cores(_core, PREV_C.get(season, set()))) \
                and not fromTop
            # 升上顶级的队不在此联赛下季名单里，属「升级离队」，不是降级
            upTop = bool(topNextSet) and in_cores(_core, topNextSet)
            # 行政降级 / 除名：赛季末被联盟勒令降级（财务、注册原因），并非竞技排名降级，
            # 单独记录，不与下面的竞技降级混用。
            demote = dmt.get(_core) if _core in dmt else next(
                (v for k, v in dmt.items() if cores_match(_core, k)), None)
            if nextFull:
                left = not in_cores(_core, NEXT_C.get(season, set()))
                releg = left and not upTop and not demote
            elif curComplete:
                releg = rank > nteams - relegN
            else:
                releg = False
            every = round(len(rounds) / dtot, 2) if dtot else None
            teams.append({"name": name, "cn": lookup(CN, name, name), "rank": rank, "pts": pts, "deduct": _ded,
                          "draws": dtot, "d00": dc.get("0-0", 0), "d11": dc.get("1-1", 0),
                          "d22": dc.get("2-2", 0), "dother": dc.get("其他", 0),
                          "streak": maxd, "gap": maxg, "every": every,
                          "formSeq": form_seq, "formCounts": form_counts, "formMatches": len(form_seq),
                          "formDetail": form_detail,
                          "promo": promo, "releg": releg, "fromTop": fromTop, "upTop": upTop,
                          "demoted": bool(demote),
                          "demoteWhy": (demote or {}).get("reason", ""),
                          "demoteTo": (demote or {}).get("to", "")})
        teams.sort(key=lambda x: x["rank"])

        note = "" if nextFull else f"降级按积分榜末 {relegN} 位推断（{SEASONS[0]} 赛季尚在进行，下季名单未定）"
        seasons[season] = {
            "season": season, "totalMatches": total, "totalDraws": td,
            "drawRate": round(td / total * 100, 2) if total else 0, "nteams": nteams,
            "perRoundCount": nteams // 2, "rounds": len(per_round),
            # 最大轮次号：进行中赛季可能出现「第 N 轮提前踢」导致的跳号，横轴/文案用它
            "roundMax": max([int(re.sub(r"\D", "", r) or 0) for r in rounds] or [len(per_round)]),
            "overall": overall, "perRound": per_round, "teams": teams, "note": note,
            # 升降级标记是否来自「已裁定的下赛季名单」：进行中的赛季下季名单未定，不显示升降 icon
            "moveFinal": bool(nextFull),
        }
        for t in teams:
            out["crestByTeam"][t["name"]] = lookup(CRESTS, t["name"], "")

    cross = build_cross(seasons)
    cross3 = build_cross(seasons, WINDOW_3)
    out["leagues"].append({
        "code": code, "cn": cn_name, "name": LG["name"], "seasons": seasons,
        "cross": cross, "cross3": cross3,
    })

    line = []
    for s in SEASONS:
        sc = seasons[s]
        line.append(f"{s}: {sc['totalMatches']}场/{sc['totalDraws']}平({sc['drawRate']}%)")
    npromo = sum(1 for t in seasons[SEASONS[0]]["teams"] if t["promo"])
    nreleg = sum(1 for t in seasons[SEASONS[0]]["teams"] if t["releg"])
    summary.append((cn_name, line, len(cross["teams"]), cross["meta"]["nFull"],
                    cross["meta"]["stable"], npromo, nreleg))

# ---------- 五大次级联赛对照 ----------
def build_compare(win):
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
            "totalMatches": tm, "totalDraws": td, "drawRate": round(td / tm * 100, 2) if tm else 0,
            "rates": [x["drawRate"] for x in reversed(ss)],
            "buckets": [bk[c] for c in CATS],
            "bucketPct": [round(bk[c] / td * 100, 2) for c in CATS] if td else [0, 0, 0, 0],
            "nTeams": cx["meta"]["nTeams"], "nFull": cx["meta"]["nFull"],
            "stable": cx["meta"]["stable"],
            "top": {"cn": cx["teams"][0]["cn"], "total": cx["teams"][0]["total"]},
        })
    rows.sort(key=lambda r: -r["drawRate"])
    return {"rows": rows, "seasonSeq": win[::-1]}


out["compare"] = build_compare(WINDOW_5)
out["compare3"] = build_compare(WINDOW_3)

# ---------- 元信息（页脚展示）----------
import time as _time
_src_ts = 0
for _f in os.listdir(D):
    if re.match(r"^[a-z]{2}\.2\.\d{4}[-_]\d{2}\.(json|txt)$", _f):
        _src_ts = max(_src_ts, int(os.path.getmtime(os.path.join(D, _f))))
_stamp_p = os.path.join(D, "_fetch_stamp.txt")
_src_txt = open(_stamp_p, encoding="utf-8").read().strip() if os.path.exists(_stamp_p) else ""
out["meta"] = {
    "srcUpdated": _src_txt or (_time.strftime("%Y-%m-%d %H:%M", _time.localtime(_src_ts)) if _src_ts else ""),
    "generated": _time.strftime("%Y-%m-%d %H:%M", _time.localtime()),
    "windows": [5, 3],
}

json.dump(out, open(f"{WS}/data/report_champ.json", "w"), ensure_ascii=False, indent=1)

print("=== 各联赛逐季（场次/平局数(平局率)）===")
for cn_name, line, nt, nf, st, np_, nr in summary:
    print(f"\n【{cn_name}】球队 {nt} 支 / 四季全勤 {nf} 支 / 稳定输出 {len(st)} 支 {st} / {SEASONS[0]} 升{np_} 降{nr}")
    for x in line:
        print("   ", x)
print("\n=== 五大次级联赛四年合计（按平局率排序）===")
print(f"{'联赛':6s} {'场次':>5s} {'平局':>5s} {'平局率':>7s}  0-0/1-1/2-2/其他")
for r in out["compare"]["rows"]:
    print(f"{r['cn']:6s} {r['totalMatches']:5d} {r['totalDraws']:5d} {r['drawRate']:6.2f}%  {r['buckets']}  四年平局最多：{r['top']['cn']} {r['top']['total']}")
print("\nwritten:", f"{WS}/data/report_champ.json")
