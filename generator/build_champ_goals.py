# -*- coding: utf-8 -*-
"""生成五大次级联赛（英冠/西乙/德乙/法乙/意乙）的「进球数统计」种子报告。

产物：generator/football_champ_goals.html，内含 window.DATA = {...}，
schema 与 football_big5_goals.html 对齐（leagues/scopes/teams/buckets/seq23...），
供 tools/sync_site.py 抽取并拆成 assets/js/data/goals-champ/ chunk。

数据来源（离线、完整、与平局页同源）：
  assets/js/data/draws-champ/<code>/<season>.js —— 次级联赛平局报告的分块，
  其每队 formDetail 含每场「轮次|日期|主客|对手序号|比分(本队视角)」，足以重建进球数。
积分/进球：generator/standings.py 的 compute_table / compute_goals（与站点同步脚本共用同一真相源）。
队徽/联赛 logo：generator/assets/crests_champ.json / league_logos_champ.json。

关键约定（与 big5 进球页一致）：
  * seq23 = 该队每场比赛的「总进球数」（主队进球+客队进球，即 r.gf+r.ga），按比赛日期升序。
    **不封顶**（与 big5 一致：实测 big5 seq23 值域 0..10，`7+` 只体现在 b 的归并桶里）。
    **同一场比赛的主客双方值相同**。
  * seq23Matches.score = 主客视角（主队在前），与本队 ha(H/A) 配合；opponent 为对手队名。
  * b = 该队所参加比赛的「总进球数」分布（0..6 / 7+），sum(b) == 该队场次。
  * gapN / streakN / countN = seq23 里「连续未出 N / 连续出 N / 出 N 的次数」；gap23 = 连续未出 2 且未出 3。
  * total = 该队自己的总进球（**与 seq23 口径不同**，勿混用）。
  * moveFinal（scope 级）+ upTop / releg / demoted / fromTop / promo（队级）：
    **原样搬运自 draws-champ**，供页面渲染升降 icon 与队名红/绿。绝不要在页面里用
    「上/下赛季名单差集」去推断（那样算错——2026-09-23 修）。
  * rank/pts 优先取平局分块自带（与平局页一致），缺失时回退 compute_table。
"""
import json
import os
import re
from collections import defaultdict

WS = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.dirname(WS)                       # football-data-site 仓库根
DRAW_SRC = os.path.join(SITE, "assets", "js", "data", "draws-champ")
ASSETS = os.path.join(WS, "assets")
CRESTS = json.load(open(os.path.join(ASSETS, "crests_champ.json"), encoding="utf-8"))
LEAGUE_LOGOS = json.load(open(os.path.join(ASSETS, "league_logos_champ.json"), encoding="utf-8"))


def load_draw_crests():
    """从已上线的 draws-champ 壳读取 crestByTeam（203 键，外置 JPG 相对 URL），
    作为进球数页队徽的唯一真相源——覆盖度与平局页完全一致。

    进球数页此前只按 crests_champ.json（136 键）做精确键匹配，导致大量队名
    （含「UD Las Palmas」等）取不到队徽。draws-champ 的 crestByTeam 用合并后的
    CRESTS（crests.json ∪ crests_champ.json）构建，覆盖完整且已验证可显示。
    """
    p = os.path.join(DRAW_SRC, "shell.js")
    if not os.path.exists(p):
        return {}
    txt = open(p, encoding="utf-8").read()
    i = txt.find('"crestByTeam"')
    if i < 0:
        return {}
    b = txt.find("{", i)
    depth = 0
    for k in range(b, len(txt)):
        if txt[k] == "{":
            depth += 1
        elif txt[k] == "}":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    try:
        return json.loads(txt[b:end])
    except Exception:
        return {}


from standings import compute_table, compute_goals, canon_top, deduct_map, TIE_RULE

from season import SEASON as CUR_SEASON  # noqa: E402  （赛季唯一来源）


def _prev_season(s):
    """'2026-27' → '2025-26'"""
    a = int(s[:4]) - 1
    return "%d-%02d" % (a, (a + 1) % 100)


SEASON_COUNT = 6                                 # 报告覆盖的赛季数（当季 + 近五季）
SEASONS = []                                     # 旧 → 新（由当季倒推，不再手写清单）
_s = CUR_SEASON
for _ in range(SEASON_COUNT):
    SEASONS.append(_s)
    _s = _prev_season(_s)
SEASONS.reverse()
ORDER = list(reversed(SEASONS))                  # 最新季在前
CHAMP = [("en", "英冠"), ("es", "西乙"), ("de", "德乙"), ("it", "意乙"), ("fr", "法乙")]

BUCKET_KEYS = ["0", "1", "2", "3", "4", "5", "6", "7+"]
BUCKETS = [0, 1, 2, 3, 4, 5, 6, "7+"]
LABELS = ["0 球", "1 球", "2 球", "3 球", "4 球", "5 球", "6 球", "7+ 球"]


def longest_run(seq, pred):
    best = cur = 0
    for v in seq:
        if pred(v):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def round_no(rnd):
    if isinstance(rnd, (int, float)):
        return int(rnd)
    if isinstance(rnd, str):
        m = re.match(r"^\s*(\d+)", rnd)
        if m:
            return int(m.group(1))
    return None


def load_scope(code, season):
    """读取 draws-champ 分块（IIFE 注入 window.DATA.leagues[i].scopes[season]），抽出 scope 对象。"""
    p = os.path.join(DRAW_SRC, code, season + ".js")
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8").read()
    i = txt.rfind("var s=")
    if i < 0:
        return None
    s = txt[i + len("var s="):]
    beg = s.find("{")
    depth = 0
    end = None
    for k in range(beg, len(s)):
        if s[k] == "{":
            depth += 1
        elif s[k] == "}":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    return json.loads(s[beg:end])


def main():
    all_crests = load_draw_crests()          # 203 键，外置 JPG；与平局页同源
    leagues_out = []
    for code, cn in CHAMP:
        scopes = {}
        for season in SEASONS:
            sc = load_scope(code, season)
            if sc is None:
                print("[WARN] 缺 draws-champ 分块:", code, season)
                continue
            teams_in = sc.get("teams", [])
            # 解析每队 formDetail -> 本队每场记录（gf/ga 为本队视角）
            recs = defaultdict(list)
            for t in teams_in:
                name = t.get("name")
                for raw in (t.get("formDetail") or []):
                    parts = str(raw).split("|")
                    if len(parts) < 5:
                        continue
                    rnd, date, ha, opp_idx_s, score = parts[0], parts[1], parts[2], parts[3], parts[4]
                    try:
                        opp_idx = int(opp_idx_s)
                    except ValueError:
                        continue
                    sp = score.split("-")
                    if len(sp) != 2 or not all(x.strip().isdigit() for x in sp):
                        continue
                    gf, ga = int(sp[0]), int(sp[1])
                    opp = teams_in[opp_idx].get("name") if 0 <= opp_idx < len(teams_in) else None
                    recs[name].append({"date": date, "ha": ha, "opp": opp,
                                       "gf": gf, "ga": ga, "round": round_no(rnd)})

            # 用同批比分重建赛果，算积分榜（保证与平局页同源）。
            # 注意：recs 是「每队视角」，同一场会被主客双方各记一次，必须按
            # (日期, {主,客}) 去重成唯一一场，否则场次/进球会被双算。
            uniq = {}
            for name, rs in recs.items():
                for r in rs:
                    opp = r["opp"]
                    if not opp:
                        continue
                    key = (r["date"], frozenset([name, opp]))
                    if r["ha"] == "H":
                        uniq[key] = {"team1": name, "team2": opp, "score": {"ft": [r["gf"], r["ga"]]}}
                    else:
                        uniq[key] = {"team1": opp, "team2": name, "score": {"ft": [r["ga"], r["gf"]]}}
            matches = list(uniq.values())
            tbl = compute_table(matches, TIE_RULE.get(code, "gd"), deduct_map(code, season, "champ"))

            teams = []
            for t in teams_in:
                name = t.get("name")
                rs = sorted(recs.get(name, []),
                            key=lambda r: (r["date"] or "", r["round"] if r["round"] is not None else 0))
                if not rs:
                    continue
                # ⚠️ 口径铁律（与 update_seq23_2627.py 的五大联赛实现完全一致）：
                # seq23 / b 记的是「该场比赛的**总进球数**」（主队进球+客队进球），
                # 不是本队自己进的球！同一场比赛的主客双方拿到同一个值。
                # 依据：页面文案「每条色带按时间顺序显示该队逐场**总进球**」+
                #       表头「不出2球/连续2球」= 该队所参加比赛总进球为 2 的连续场次。
                # 历史 bug：曾误取 r["gf"]（本队进球），导致色块整体错位。
                # 注意 total（该队总进球）仍取本队自己的 gf，两者口径不同、不可混用。
                seq = [r["gf"] + r["ga"] for r in rs]
                b = {k: 0 for k in BUCKET_KEYS}
                for v in seq:
                    # 与 big5 一致：b[str(tot) if tot<=6 else '7+']（注意是 >=7，不是 ==7，
                    # 否则总进球 8/9/10 会 KeyError——曾因此让生成器静默失败）
                    b["7+" if v >= 7 else str(v)] += 1
                seq23m = []
                for r in rs:
                    if r["ha"] == "H":
                        score = "%d-%d" % (r["gf"], r["ga"])
                    else:
                        score = "%d-%d" % (r["ga"], r["gf"])
                    seq23m.append({"date": r["date"], "score": score,
                                   "opponent": r["opp"], "ha": r["ha"], "round": r["round"]})
                rp = tbl.get(canon_top(name))
                total = sum(r["gf"] for r in rs)
                teams.append({
                    "name": name,
                    "cn": t.get("cn", name),
                    "rank": t.get("rank") if t.get("rank") is not None else (rp[0] if rp else None),
                    "pts": t.get("pts") if t.get("pts") is not None else (rp[1] if rp else None),
                    "total": total,
                    "b": b,
                    "gap2": longest_run(seq, lambda v: v != 2),
                    "gap3": longest_run(seq, lambda v: v != 3),
                    "count2": sum(1 for v in seq if v == 2),
                    "count3": sum(1 for v in seq if v == 3),
                    "streak2": longest_run(seq, lambda v: v == 2),
                    "streak3": longest_run(seq, lambda v: v == 3),
                    "gap23": longest_run(seq, lambda v: v != 2 and v != 3),
                    "seq23": seq,
                    "seq23Matches": seq23m,
                    # ↓ 升降级标记 + 队名配色，原样搬运自 draws-champ（与平局页同源同语义）。
                    #   不要用「上/下赛季名单差集」去推断——那正是这里曾经算错的原因。
                    #   upTop/releg/demoted = 本季最终去向（升入顶级 / 竞技降级 / 行政降级）；
                    #   fromTop = 上季从顶级降入（队名标红）；promo = 上季从次次级升入（队名标绿）。
                    "upTop": bool(t.get("upTop")),
                    "releg": bool(t.get("releg")),
                    "demoted": bool(t.get("demoted")),
                    "fromTop": bool(t.get("fromTop")),
                    "promo": bool(t.get("promo")),
                })
                if name not in all_crests and name in CRESTS:
                    all_crests[name] = CRESTS[name]   # crestByTeam 兜底

            team_count = len(teams)
            total_entries = sum(len(v) for v in recs.values())
            total_matches = total_entries // 2 if total_entries else 0
            expected = team_count * (team_count - 1) if team_count else 0
            # 联赛 buckets = 每场「总进球数」分布（与 big5 种子一致：sum == totalMatches），
            # 不是「每队每场进球」分布。avgGoals = 场均总进球。
            lg_buckets = {k: 0 for k in BUCKET_KEYS}
            total_goals = 0
            for m in matches:
                ft = m["score"]["ft"]
                tot = ft[0] + ft[1]
                total_goals += tot
                lg_buckets[str(tot) if tot <= 6 else "7+"] += 1
            avg = round(total_goals / total_matches, 2) if total_matches else 0
            scopes[season] = {
                "totalMatches": total_matches,
                "expected": expected,
                "teamCount": team_count,
                "inProgress": total_matches < expected,
                "note": "",
                "avgGoals": avg,
                "buckets": lg_buckets,
                # 与 draws-champ 同源：False = 本季尚在进行、下季升降名单未定 → 不标任何升降 icon。
                # 缺字段时按 True（可判定）处理，与平局页的 `s.moveFinal !== false` 一致。
                "moveFinal": sc.get("moveFinal") is not False,
                "teams": teams,
            }
            print("  %s %s: %d 队 / %d 场 / 场均 %.2f 球" % (cn, season, team_count, total_matches, avg))
        leagues_out.append({
            "code": code, "cn": cn,
            "logo": LEAGUE_LOGOS.get(code, ""),
            "order": ORDER,
            "scopes": scopes,
        })

    obj = {"buckets": BUCKETS, "labels": LABELS, "leagues": leagues_out, "crests": all_crests}
    DATA_JS = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    HTML = ("<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head><meta charset=\"UTF-8\">"
            "<title>叕中啦 · 五大次级联赛进球数统计（种子）</title></head>\n<body>\n"
            "<script>window.DATA = " + DATA_JS + ";</script>\n</body>\n</html>\n")
    out = os.path.join(WS, "football_champ_goals.html")
    open(out, "w", encoding="utf-8").write(HTML)
    print("[OK] 写入", out, "—", len(DATA_JS.encode("utf-8")), "bytes；",
          len(leagues_out), "联赛；", len(all_crests), "队徽")


if __name__ == "__main__":
    main()
