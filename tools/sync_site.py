#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「重新生成的三份报告 HTML」里的数据块同步进静态站点。

设计原则（对应最初的需求「千万不要改动数据内容」）：
  * 只搬数据，绝不碰站点的外壳：site.js / site.css / 页面 JS / 页面 CSS / 字体 一律不动。
  * （本地历史快照 tools/backups 已关闭：sync_site.py 不再写备份，线上数据即唯一真相。）
  * 唯一的例外是进数球数据的「补全」步骤（见 enrich_goals）——它不 invent 数据，
    只是把平局报告里已有的官方轮次 / 主客场回填进进数球数据，并按轮次重排色带。
  * 写入前做体检，任何一条不通过就整批中止，一个字节都不写：
      1. 新旧顶层键集合必须一致
      2. 联赛数量、赛季（scope）键集合必须一致
      3. 历史赛季（非 2026-27）的场次必须一字不变 —— 防止误伤已完成赛季
      4. 2026-27 的场次只能增加不能减少 —— 进行中的赛季只会越赛越多
  * 序列化统一用紧凑风格（separators=(",", ":")），缩小首屏下载体积；
    draws 文件首次重写会整文件变化（一次性大 diff），之后增量 diff 很小。
"""

import json
import os
import re
import sys
import time
import unicodedata

WS = "/Users/santu/WorkBuddy AI/2026-09-02-02-18-19"
if WS not in sys.path:
    sys.path.insert(0, WS)
from standings import compute_table, compute_goals, deduct_map, TIE_RULE
GOALS_WS = "/Users/santu/WorkBuddy AI/2026-08-24-11-07-48"
SITE = "/Users/santu/soccerdata/football-data-site"
AUTO = os.path.join(SITE, "tools")

# 进数球比分视角归一化：enrich 只覆盖平局数据里查得到的队，查不到的（升降级队）
# 会保持生成器的「球队视角」，与其余队的「主客视角」不一致，导致得失球在客场
# 场次整体颠倒。这里统一成主客视角，并用「总进球守恒」兜底校验。
if AUTO not in sys.path:
    sys.path.insert(0, AUTO)
from fix_goals_perspective import (  # noqa: E402
    normalize as normalize_goals_perspective,
    check_conservation as check_goals_conservation,
)

CUR_SEASON = "2026-27"

JOBS = [
    {
        "name": "平局统计 · 五大联赛",
        "src": f"{WS}/football_big5_draws.html",
        "marker": "const DATA = ",
        "dst": f"{SITE}/assets/js/draws-big5-data.js",
        "kind": "draws",
        "role": "draws-big5",          # 进数球回填官方轮次 / 主客场的基准源
    },
    {
        "name": "平局统计 · 次级联赛",
        "src": f"{WS}/football_champ_draws.html",
        "marker": "const DATA = ",
        "dst": f"{SITE}/assets/js/draws-champ-data.js",
        "kind": "draws",
    },
    {
        "name": "进球数统计",
        "src": f"{GOALS_WS}/football_big5_goals.html",
        "marker": "window.DATA = ",
        "dst": f"{SITE}/assets/js/goals-data.js",
        "kind": "goals",
    },
]


def die(msg):
    print(f"[FAIL] {msg}")
    sys.exit(1)


def extract(path, marker):
    """从报告 HTML 里取出 marker 后面的那个 JSON 对象。"""
    s = open(path, encoding="utf-8").read()
    i = s.find(marker)
    if i < 0:
        die(f"{os.path.basename(path)} 里找不到数据标记 {marker!r}")
    obj, _ = json.JSONDecoder().raw_decode(s[i + len(marker):])
    return obj


def detect_separators(text, marker):
    """统一用紧凑风格（separators=(",", ":")）序列化，缩小首屏下载体积。

    历史上 draws 用带空格的风格、goals 用紧凑风格，现统一紧凑：draws 文件会在
    首次重写时整文件变化（一次性的大 diff），之后增量 diff 很小，且体积显著下降。
    """
    return (",", ":")


def season_rows(obj, kind):
    """产出 [(标签, 赛季, 场次)]，供历史赛季一致性校验。"""
    rows = []
    for lg in obj["leagues"]:
        tag = lg.get("cn") or lg.get("code")
        if kind == "draws":
            for season, sd in lg["seasons"].items():
                rows.append((f"{tag} {season}", season, sd.get("totalMatches")))
        else:
            for season, sc in lg["scopes"].items():
                rows.append((f"{tag} {season}", season, sc.get("totalMatches")))
    return rows


def as_int(v, default=0):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return default


def build_ha_round_index(draws):
    """平局报告的 formDetail 是唯一带「官方轮次 + 主客场」的权威源。

    formDetail 元素格式：round|date|ha|opponentIndex|score（已按轮次升序）
    返回 {联赛code: {赛季: {队名: {日期: (ha, round)}}}}
    """
    idx = {}
    for lg in draws.get("leagues", []):
        per_season = {}
        for season, sd in (lg.get("seasons") or {}).items():
            per_team = {}
            for t in (sd.get("teams") or []):
                by_date = {}
                for raw in (t.get("formDetail") or []):
                    p = str(raw).split("|")
                    if len(p) < 3 or not p[1]:
                        continue
                    by_date[p[1]] = (p[2], p[0], p[4] if len(p) > 4 else "")
                per_team[t.get("name")] = by_date
            per_season[season] = per_team
        idx[lg.get("code")] = per_season
    return idx


def longest_run(seq, pred):
    best = cur = 0
    for v in seq:
        if pred(v):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def enrich_goals(goals, draws):
    """给进数球数据的 seq23Matches 补 ha / round，并把色带统一重排成日期顺序。

    背景：进数球生成器只按日期排列，且最初没输出主客场，于是
      · 悬浮框判不出主客，只能一律按「本队主场」渲染，客场比赛的比分方向是错的
    平局报告的 formDetail 带官方轮次、主客场和球队视角比分，用它按（队名 + 日期）
    回填，并把进球数页的比分统一成原始主客队视角（客场时翻转球队视角比分）。

    重排会改变 gap2/gap3/streak2/streak3（这几个字段依赖数组顺序），必须一并
    重算，算法与生成侧完全一致：gapN = 最长连续 != N，streakN = 最长连续 == N。

    覆盖率不足的球队（升降级队，该赛季在平局数据里查无此人）整队跳过、保持
    原状 —— 宁可不排，也不猜。
    """
    idx = build_ha_round_index(draws)
    n_hit = n_team = n_cell = 0
    for lg in goals.get("leagues", []):
        per_season = idx.get(lg.get("code"), {})
        for season, sc in (lg.get("scopes") or {}).items():
            per_team = per_season.get(season, {})
            for t in (sc.get("teams") or []):
                by_date = per_team.get(t.get("name"))
                if not by_date:
                    continue
                ms = t.get("seq23Matches") or []
                sq = t.get("seq23") or []
                live = [m for m in ms if m]
                if not live or len(ms) != len(sq):
                    continue
                hit = 0
                for gm in live:
                    v = by_date.get(gm.get("date"))
                    if v:
                        ha, rnd, team_score = v
                        gm["ha"], gm["round"] = ha, rnd
                        # formDetail 的比分是「该队-对手」视角；进球数页统一存
                        # 原始主客队视角，方便所有悬浮框用同一套渲染规则。
                        sp = str(team_score or "").split("-")
                        if len(sp) == 2 and all(x.strip().isdigit() for x in sp):
                            gm["score"] = (sp[0] + "-" + sp[1]) if ha == "H" else (sp[1] + "-" + sp[0])
                        hit += 1
                n_hit += hit
                # 覆盖不全（升降级队在平局数据里查无该赛季）的球队整队跳过，保持原状。
                if hit != len(live):
                    continue
                # 全季覆盖：按「比赛真实发生日期」重排色带，并同步重算依赖数组顺序的 gap/streak。
                # 用户确认：色块要反映球队数据的真实演变，日期序 = 真实比赛序，才是最准确的口径；
                # 轮次号可能不单调（补赛/提前进行的轮次会让日期与轮次错位），但这是可接受的代价，
                # gap/streak（最长连续未出/连出 N 球）必须跟着日期序一起重算。
                n_team += 1
                pairs = sorted(zip(sq, ms),
                               key=lambda p: (p[1].get("date") or "", as_int(p[1].get("round"))))
                t["seq23"] = [p[0] for p in pairs]
                t["seq23Matches"] = [p[1] for p in pairs]
                n_cell += len(pairs)
                seq = t["seq23"]
                for n in (2, 3):
                    t["gap%d" % n] = longest_run(seq, (lambda v, n=n: v != n))
                    t["streak%d" % n] = longest_run(seq, (lambda v, n=n: v == n))
                    t["count%d" % n] = sum(1 for v in seq if v == n)
    return n_hit, n_team, n_cell


def _standings_from_results(ms, code):
    """由赛果算 (积分榜, 总进球)。与 standings.compute_table 同款逻辑。"""
    ded = deduct_map(code, CUR_SEASON, "top")
    tbl = compute_table(ms, TIE_RULE.get(code, "gd"), ded)
    goals = compute_goals(ms)
    return tbl, goals

def verify_goals_standings(goals):
    """2026-27 内嵌积分榜/总进球必须与赛果实算值一致，否则整批中止。"""
    DATA = os.path.join(WS, "data")
    for lg in goals.get("leagues", []):
        code = lg.get("code")
        sc = (lg.get("scopes") or {}).get(CUR_SEASON)
        if not sc:
            continue
        src = os.path.join(DATA, f"{code}.1.2026-27.json")
        if not os.path.exists(src):
            continue
        ms = json.load(open(src, encoding="utf-8"))["matches"]
        reg = [m for m in ms if m.get("phase") != "po"]
        tbl, goals_map = _standings_from_results(reg, code)
        for t in (sc.get("teams") or []):
            name = t.get("name")
            c = tbl.get(name)
            if c is None:
                die(f"进球数校验失败 / {code} {CUR_SEASON}: {name} 不在赛果积分榜中")
            if (t.get("rank"), t.get("pts")) != c or t.get("total") != goals_map.get(name):
                die(f"进球数校验失败 / {code} {CUR_SEASON}: {name} "
                    f"内嵌=({t.get('rank')},{t.get('pts')},总进球{t.get('total')}) "
                    f"赛果=({c[0]},{c[1]},总进球{goals_map.get(name)}) —— 积分榜未随赛果刷新，已中止上线")

def main():
    planned = []          # [(job, new_text, summary_lines)]
    print("=== 体检阶段（此时尚未写入任何文件）===")

    # 进数球数据需要平局报告（五大联赛）来回填官方轮次 / 主客场
    draws_obj = None
    for job in JOBS:
        if job.get("role") == "draws-big5" and os.path.exists(job["src"]):
            draws_obj = extract(job["src"], job["marker"])
            break
    if draws_obj is None:
        print("  [WARN] 读不到平局报告，进数球数据本次跳过 ha/round 回填")

    for job in JOBS:
        src, dst, marker = job["src"], job["dst"], job["marker"]
        name = job["name"]
        if not os.path.exists(src):
            die(f"{name}: 源报告不存在 {src}")
        if not os.path.exists(dst):
            die(f"{name}: 站点数据文件不存在 {dst}")

        new = extract(src, marker)
        if job["kind"] == "goals":
            verify_goals_standings(new)   # 部署前最后一道闸：2026-27 积分榜必须与赛果一致
            if draws_obj is not None:
                n_hit, n_team, n_cell = enrich_goals(new, draws_obj)
                print(f"    回填主客场/轮次：命中 {n_hit} 场，"
                      f"按日期重排 {n_team} 支球队 / {n_cell} 格（派生 gap/streak 已重算）")
                # 统一比分视角（主客视角=主队在前），否则得失球统计会在客场场次整体颠倒
                fixed = normalize_goals_perspective(new)
                if fixed:
                    head = "、".join(f"{lg} {s} {cn}" for lg, s, cn, _ in fixed[:5])
                    print(f"    统一比分视角：修复 {len(fixed)} 支球队（{head}"
                          f"{' …' if len(fixed) > 5 else ''}）")
                bad = check_goals_conservation(new)
                if bad:
                    detail = "; ".join(f"{lg} {s} 进球{gf}≠失球{ga} 差{d}"
                                       for lg, s, gf, ga, d in bad)
                    die(f"{name}: 总进球不守恒（比分视角仍不一致）：{detail}")
        cur_text = open(dst, encoding="utf-8").read()
        old = extract(dst, marker)

        # 0) meta 是站点侧的账本（数据源时间 / 本页更新时间），不是报告里的数据。
        #    进数球报告本身不带 meta，这里把站点上已有的 meta 接过来，避免把它
        #    误判成「顶层键变化」而整批中止（曾导致自动同步静默停摆）。
        if isinstance(old.get("meta"), dict):
            m = dict(old["meta"])
            m.update(new.get("meta") or {})
            new["meta"] = m

        # 1) 顶层键一致（meta 单独处理，不参与比较）
        if set(new) - {"meta"} != set(old) - {"meta"}:
            die(f"{name}: 顶层键变化 {sorted((set(old) ^ set(new)) - {'meta'})}")

        # 2) 联赛数量一致
        if len(new.get("leagues", [])) != len(old.get("leagues", [])):
            die(f"{name}: 联赛数量变化 {len(old['leagues'])} -> {len(new['leagues'])}")

        # 2b) 赛季键一致
        key = "seasons" if job["kind"] == "draws" else "scopes"
        for a, b in zip(new["leagues"], old["leagues"]):
            if set(a[key]) != set(b[key]):
                die(f"{name} / {a.get('cn')}: 赛季键变化 {sorted(set(b[key]) ^ set(a[key]))}")

        # 3) 历史赛季必须一字不变  4) 2026-27 场次只能增不能减
        old_rows = dict((t, n) for t, s, n in season_rows(old, job["kind"]))
        changed = []
        for tag, season, n in season_rows(new, job["kind"]):
            o = old_rows.get(tag)
            if season == CUR_SEASON:
                if n is None or o is None:
                    continue
                if n < o:
                    die(f"{name} / {tag}: 场次倒退 {o} -> {n}")
                if n != o:
                    changed.append(f"    · {tag}: {o} -> {n} 场")
            else:
                if n != o:
                    die(f"{name} / {tag}: 历史赛季被改动 {o} -> {n}（禁止）")

        seps = detect_separators(cur_text, marker)
        body = marker + json.dumps(new, ensure_ascii=False, separators=seps) + ";"
        new_text = body + "\n" if cur_text.endswith("\n") else body

        same = new_text == cur_text
        print(f"  {name}: {'无变化' if same else '有更新'} "
              f"({os.path.getsize(dst):,} -> {len(new_text.encode('utf-8')):,} 字节)")
        for line in changed:
            print(line)

        planned.append((job, new, cur_text, same))

    updatable = [p for p in planned if not p[3]]
    if not updatable:
        print("\n=== 三份数据均无变化，跳过写入 ===")
        print("SUMMARY|无变化")
        return

    # 本地历史快照（tools/backups）已按用户要求彻底关闭：sync_site.py 不再写入任何
    # 备份文件，每天生成的线上数据即唯一真相，回滚需求由 git 历史 / GitHub 承担。

    print("\n=== 写入阶段 ===")
    for job, new, cur_text, _ in updatable:
        # 「本页更新」= 本次真正把数据写进站点的时刻
        if isinstance(new.get("meta"), dict):
            new["meta"]["generated"] = time.strftime("%Y-%m-%d %H:%M")
        seps = detect_separators(cur_text, job["marker"])
        body = job["marker"] + json.dumps(new, ensure_ascii=False, separators=seps) + ";"
        new_text = body + "\n" if cur_text.endswith("\n") else body
        with open(job["dst"], "w", encoding="utf-8") as f:
            f.write(new_text)
        print(f"  [OK] 已写入 {job['dst']}")

    # 回读校验：确保写进去的东西还能被解析
    print("\n=== 回读校验 ===")
    for job, _, _, _ in updatable:
        obj = extract(job["dst"], job["marker"])
        n = len(obj.get("leagues", []))
        print(f"  [OK] {job['name']}: 解析成功，{n} 个联赛")

    cur_total = []
    for job in JOBS:
        obj = extract(job["dst"], job["marker"])
        for tag, season, n in season_rows(obj, job["kind"]):
            if season == CUR_SEASON:
                cur_total.append(f"{tag} {n}")

    # 额外产出 assets/js/meta.js：给「更多」页显示两个时间戳用。
    # 单独一个小文件（几百字节）即可，避免为了两个时间戳去加载 4MB 数据脚本。
    write_meta_js()

    print("SUMMARY|2026-27 已赛场次：" + "，".join(cur_total))


def write_meta_js():
    """从三份数据文件里抽出 meta，写成极小的 assets/js/meta.js。

    任何一份读不到就整体跳过（保持上一版），绝不写半截文件。
    """
    try:
        metas = {}
        for job in JOBS:
            obj = extract(job["dst"], job["marker"])
            m = obj.get("meta") if isinstance(obj.get("meta"), dict) else {}
            metas[job["dst"].split("/")[-1]] = m
        # 「本页更新」= 本次真正把数据同步进站点的时刻（= now），不要取各数据文件里
        # 内嵌 generated 的 max —— 当某份数据「无变化」未被重写时，其内嵌 generated 会
        # 停留在旧值，max 会把整站时间拉回过去，造成「进球数页比平局页旧」这类不一致。
        # 统一以 sync_site.py 的运行时刻为准；纯代码提交的 generated 则由 pre-commit
        # 钩子（bump_meta.py）刷新，二者都是「最近一次部署时间」，方向永远向前。
        # 注：站点已不再展示「数据源更新时间」，meta.js 只保留 generated 一个键。
        payload = {
            "generated": time.strftime("%Y-%m-%d %H:%M"),
        }
        out = os.path.join(SITE, "assets/js/meta.js")
        text = "window.SITE_META = " + json.dumps(payload, ensure_ascii=False) + ";\n"
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  [OK] 已写入 {out}（本页更新 {payload['generated']}）")
    except Exception as e:
        print(f"  [WARN] meta.js 生成失败，跳过：{e}")


if __name__ == "__main__":
    main()
