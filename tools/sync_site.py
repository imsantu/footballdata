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

数据落盘方式（2026-09-19 重构）：
  * 不再产出单体 *-data.js（既占 ~13MB、又冗余于已拆分的 chunk）。抽取并 enrich
    后的数据对象只在内存里传给两个拆分器（gen_goals_chunks / gen_draws_big5_chunks），
    由它们直接写出 assets/js/data/<group>/<league>/<season>.js。
  * 健康校验的「旧基线」改存为 git 忽略的 tools/.cache/<group>-audit.json
    （仅记录结构摘要：顶层键 / 联赛数 / 各联赛赛季键 / 各赛季场次 / 数据哈希 / meta），
    体积仅 KB 级，不是那 4MB 单体。
  * 日常只重写当前进行中的赛季（2026-27）的 chunk；历史赛季 chunk 已在 git 冻结，
    不再触碰。新赛季开局或结构性调整时设环境变量 FD_FULL_REGEN=1 走全量重建。
"""

import hashlib
import json
import os
import re
import sys
import time
import unicodedata

WS = os.environ.get("FD_GENERATOR_DIR", "/Users/santu/WorkBuddy AI/2026-09-02-02-18-19")
if WS not in sys.path:
    sys.path.insert(0, WS)
from standings import compute_table, compute_goals, deduct_map, TIE_RULE
# 进球数报告（football_big5_goals.html / football_mobile.html）所在目录。
#   本机：报告与脚本**不在同一目录**（脚本 09-02，报告 08-24）；
#   云端/同仓：两者同在 generator/，即 WS 自身。
# 判定顺序：① FD_GOALS_WS 显式给出 → 用它；② 给了 FD_GENERATOR_DIR（云端 / 显式覆盖）
#           → 报告就在同一目录，跟随 WS；③ 都没给（本机裸跑）→ 用本机报告目录。
# 历史事故：本机默认写成 WS → 找不到源报告 → 「[FAIL] 进球数统计: 源报告不存在」→
#           整条流水线中止、站点当天不更新（2026-09-22 两次）。改默认值时务必保留 ②，
#           否则云端 runner 会去找一个不存在的 macOS 路径。
GOALS_WS = (os.environ.get("FD_GOALS_WS")
            or (WS if os.environ.get("FD_GENERATOR_DIR")
                else "/Users/santu/WorkBuddy AI/2026-08-24-11-07-48"))
SITE = os.environ.get("FD_SITE_DIR", "/Users/santu/footballdata/football-data-site")
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
# 拆分器：sync_site 抽取+校验后直传内存对象给它们写出 chunk（不再经单体落盘）
import gen_goals_chunks   # noqa: E402
import gen_draws_big5_chunks  # noqa: E402

# 赛季唯一来源：generator/season.py（$WS 已在上方加入 sys.path）
from season import SEASON as CUR_SEASON  # noqa: E402

JOBS = [
    {
        "name": "平局统计 · 五大联赛",
        "src": f"{WS}/football_big5_draws.html",
        "marker": "const DATA = ",
        "group": "draws-big5",
        "kind": "draws",
        "role": "draws-big5",          # 进数球回填官方轮次 / 主客场的基准源
    },
    {
        "name": "平局统计 · 次级联赛",
        "src": f"{WS}/football_champ_draws.html",
        "marker": "const DATA = ",
        "group": "draws-champ",
        "kind": "draws",
    },
    {
        "name": "进球数统计",
        "src": f"{GOALS_WS}/football_big5_goals.html",
        "marker": "window.DATA = ",
        "group": "goals",
        "kind": "goals",
    },
    {
        "name": "进球数统计 · 次级联赛",
        # 该种子由 generator/build_champ_goals.py 生成，随仓库走（不在 $WS）；
        # 云端模式 FD_GENERATOR_DIR 就是 $SITE/generator，两种模式此路径都成立。
        "src": f"{SITE}/generator/football_champ_goals.html",
        "marker": "window.DATA = ",
        "group": "goals-champ",
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
            for season, sd in (lg.get("seasons") or {}).items():
                rows.append((f"{tag} {season}", season, sd.get("totalMatches")))
        else:
            for season, sc in (lg.get("scopes") or {}).items():
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
        src = os.path.join(DATA, f"{code}.1.{CUR_SEASON}.json")
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


# ── 审计基线（替代原单体作为健康校验的「旧」参照；git 忽略，仅本地） ──
CACHE = os.path.join(AUTO, ".cache")


def inject_promotion(goals, draws):
    """把 draws-big5 的升降级权威字段搬进 goals 数据（仅五大联赛用）。

    为什么必须搬而不是推断
    ----------------------
    goals 页面原先靠「上/下赛季名单差集 + 积分榜末 N 位」推断升降级，是全站**唯一**的
    推断式实现，且实测有 14 处漏标 —— 根因是它天然依赖「相邻赛季的名单」：

      · 最早赛季（2021-22）没有上赛季可比 → 该季 5 个联赛的升班马**全部漏标**（13 处）；
      · fr 2022-23 欧塞尔：下赛季名单不完整、本赛季又未满足「已完赛」条件 → 漏标降级。

    搬过来之后与次级联赛（build_champ_goals.py 从 draws-champ 搬运）走同一条路子：
    直接读字段，不做任何推断。字段定义见 draws 数据本身，语义与平局页同源。

    搬运字段
    --------
      team.promo     —— 本季升班马（季初从下一级升入）
      team.releg     —— 本季结束后降出本联赛
      scope.moveFinal—— 该赛季是否已结束（False = 尚在进行、下季升降名单未定 → 不标 icon）

    匹配规则
    --------
    先按英文 name 匹配，失败回退中文 cn。两套数据集的队名口径不同：
    draws-big5 用完整官方名（VfL Bochum 1848 / SpVgg Greuther Fürth 1903），
    goals 用短名（VfL Bochum / SpVgg Greuther Fürth）—— 实测 580 条里只有这 5 条需要回退。

    返回 (命中队数, 未命中队数, 覆盖赛季数)，供调用方打印体检信息。
    """
    # 建索引：code -> season -> 队对象（name 与 cn 两个键）
    idx = {}
    for lg in draws.get("leagues") or []:
        code = lg.get("code")
        for season, sc in (lg.get("seasons") or {}).items():
            m = {}
            for t in sc.get("teams") or []:
                if t.get("name"):
                    m[t["name"]] = t
                if t.get("cn"):
                    m.setdefault("cn:" + t["cn"], t)
            idx[(code, season)] = (m, sc)

    hit = miss = n_scope = 0
    for lg in goals.get("leagues") or []:
        code = lg.get("code")
        for season, sc in (lg.get("scopes") or {}).items():
            got = idx.get((code, season))
            if got is None:
                continue
            m, dsc = got
            n_scope += 1
            # 与平局页的 `s.moveFinal !== false` 完全一致：缺字段时按「可判定」处理。
            sc["moveFinal"] = dsc.get("moveFinal") is not False
            for t in sc.get("teams") or []:
                dt = m.get(t.get("name"))
                if dt is None and t.get("cn"):
                    dt = m.get("cn:" + t["cn"])
                if dt is None:
                    miss += 1
                    continue
                t["promo"] = bool(dt.get("promo"))
                t["releg"] = bool(dt.get("releg"))
                hit += 1
    return hit, miss, n_scope


def audit_path(job):
    return os.path.join(CACHE, job["group"] + "-audit.json")


def load_audit(path):
    if not os.path.exists(path):
        return None
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return None


def content_hash(obj):
    """整份数据的稳定哈希（忽略易变的 meta），用于「内容是否变化」的快速判定。"""
    o = dict(obj)
    o.pop("meta", None)
    return hashlib.sha256(
        json.dumps(o, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def save_audit(path, obj, kind):
    """把结构摘要写入审计基线（替代原单体作为健康校验的「旧」参照）。"""
    season_keys = {}
    for lg in obj.get("leagues", []):
        key = "seasons" if kind == "draws" else "scopes"
        season_keys[lg.get("code")] = sorted((lg.get(key) or {}).keys())
    rows = {}
    key = "seasons" if kind == "draws" else "scopes"
    for lg in obj.get("leagues", []):
        code = lg.get("code")
        for season, sd in (lg.get(key) or {}).items():
            rows["%s|%s" % (code, season)] = sd.get("totalMatches")
    audit = {
        "top_keys": sorted(obj.keys()),
        "n_leagues": len(obj.get("leagues", [])),
        "season_keys": season_keys,
        "rows": rows,
        "meta": obj.get("meta") if isinstance(obj.get("meta"), dict) else {},
        "hash": content_hash(obj),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(audit, f, ensure_ascii=False, separators=(",", ":"))


def health_check(new, old, job):
    """new 相对审计基线 old 的结构一致性校验（替代原单体对比）。"""
    kind = job["kind"]
    # 1) 顶层键一致（meta 单独处理，不参与比较）
    if set(new) - {"meta"} != set(old["top_keys"]) - {"meta"}:
        die(f"{job['name']}: 顶层键变化 {sorted((set(old['top_keys']) ^ set(new)) - {'meta'})}")
    # 2) 联赛数量一致
    if len(new.get("leagues", [])) != old["n_leagues"]:
        die(f"{job['name']}: 联赛数量变化 {old['n_leagues']} -> {len(new['leagues'])}")
    # 2b) 赛季键一致（按 code 匹配，避免位置错位）
    key = "seasons" if kind == "draws" else "scopes"
    new_by_code = {lg.get("code"): lg for lg in new["leagues"]}
    for code, old_keys in old["season_keys"].items():
        a = new_by_code.get(code)
        if a is None:
            die(f"{job['name']} / {code}: 联赛缺失")
        if set((a.get(key) or {}).keys()) != set(old_keys):
            die(f"{job['name']} / {code}: 赛季键变化 "
                f"{sorted(set(old_keys) ^ set((a.get(key) or {}).keys()))}")
    # 3) 历史赛季必须一字不变  4) 2026-27 场次只能增不能减
    key = "seasons" if kind == "draws" else "scopes"
    new_rows = {}
    for lg in new.get("leagues", []):
        code = lg.get("code")
        for season, sd in (lg.get(key) or {}).items():
            new_rows["%s|%s" % (code, season)] = sd.get("totalMatches")
    for rkey, o in old["rows"].items():
        code, season = rkey.split("|")
        n = new_rows.get(rkey)
        if n is None:
            die(f"{job['name']} / {code} {season}: 数据缺失")
        if season == CUR_SEASON:
            if n < o:
                die(f"{job['name']} / {code} {season}: 场次倒退 {o} -> {n}")
        else:
            if n != o:
                die(f"{job['name']} / {code} {season}: 历史赛季被改动 {o} -> {n}（禁止）")


def main():
    os.makedirs(CACHE, exist_ok=True)
    planned = []          # (job, new, changed)
    print("=== 体检阶段（此时尚未写入任何文件）===")

    # 进数球数据需要平局报告（五大联赛）来回填官方轮次 / 主客场
    draws_obj = None
    for job in JOBS:
        if job.get("group") == "draws-big5" and os.path.exists(job["src"]):
            draws_obj = extract(job["src"], job["marker"])
            break
    if draws_obj is None:
        print("  [WARN] 读不到平局报告，进数球数据本次跳过 ha/round 回填")

    for job in JOBS:
        src, marker = job["src"], job["marker"]
        name = job["name"]
        if not os.path.exists(src):
            die(f"{name}: 源报告不存在 {src}")
        new = extract(src, marker)
        if job["kind"] == "goals":
            is_champ = job["group"] == "goals-champ"
            # 仅五大联赛需 verify_goals_standings：次级联赛的 rank/pts/ha/round 已在
            # build_champ_goals.py 里直接由 draws-champ（同源）回填，无需再用 big5 赛果对账。
            if not is_champ:
                verify_goals_standings(new)   # 部署前最后一道闸：2026-27 积分榜须与赛果一致
            # 五大联赛：用 draws-big5 回填官方轮次/主客场（次级联赛已在生成器同源回填，跳过）。
            if not is_champ and draws_obj is not None:
                n_hit, n_team, n_cell = enrich_goals(new, draws_obj)
                print(f"    回填主客场/轮次：命中 {n_hit} 场，"
                      f"按日期重排 {n_team} 支球队 / {n_cell} 格（派生 gap/streak 已重算）")
                # 升降级权威字段：原样搬运 draws-big5 的 promo/releg/moveFinal，
                # 取代页面里那套「名单差集推断」（全站唯一的推断式实现，实测漏标 14 处）。
                n_inj, n_miss, n_scope = inject_promotion(new, draws_obj)
                print(f"    搬运升降级字段：{n_inj} 支球队（promo/releg）/ {n_scope} 个赛季（moveFinal）"
                      + (f"，{n_miss} 支未匹配" if n_miss else ""))
            # 统一比分视角（主客视角=主队在前）+ 总进球守恒校验：big5 / champ 通用，
            # 作用于 goals 对象本身，对次级联赛是最后一道一致性兜底。
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

        old = load_audit(audit_path(job))
        if old is None:
            print(f"  {name}: [首跑] 无历史基线，建立审计基线（本次不比较）")
            planned.append((job, new, True))
            continue
        health_check(new, old, job)
        # meta 合并：把站点侧 meta 接过来，避免被误判为「顶层键变化」
        if isinstance(new.get("meta"), dict) and isinstance(old.get("meta"), dict):
            m = dict(old["meta"])
            m.update(new.get("meta") or {})
            new["meta"] = m
        is_changed = content_hash(new) != old.get("hash")
        planned.append((job, new, is_changed))
        if is_changed:
            print(f"  {name}: 有更新")
        else:
            print(f"  {name}: 无变化")

    if not any(c for _, _, c in planned):
        print("\n=== 三份数据均无变化，跳过写入 ===")
        print("SUMMARY|无变化")
        return

    # 本地历史快照（tools/backups）已按用户要求彻底关闭：sync_site.py 不再写入任何
    # 备份文件，每天生成的线上数据即唯一真相，回滚需求由 git 历史 / GitHub 承担。

    print(f"\n=== 写入阶段：生成按季 chunk（仅 {CUR_SEASON}）+ 队徽外置 ===")
    only_current = not os.environ.get("FD_FULL_REGEN")
    print("  模式:", "全量(含历史)" if not only_current else f"仅 {CUR_SEASON}")
    for job, new, is_changed in planned:
        if not is_changed:
            continue
        if job["group"] in ("goals", "goals-champ"):
            gen_goals_chunks.generate(new, only_current=only_current, group=job["group"])
        else:
            gen_draws_big5_chunks.run(job["group"], obj=new, only_current=only_current)

    # 更新审计基线（所有数据集；未变化的 hash 不变，重写无副作用）
    for job, new, _ in planned:
        save_audit(audit_path(job), new, job["kind"])

    # 额外产出 assets/js/meta.js：给「更多」页显示「本页更新」时间戳用。
    # 单独一个小文件（几百字节）即可，避免为了一个时间戳去加载 4MB 数据脚本。
    write_meta_js()

    cur_total = []
    for job, new, _ in planned:
        for tag, season, n in season_rows(new, job["kind"]):
            if season == CUR_SEASON:
                cur_total.append(f"{tag} {n}")
    print(f"SUMMARY|{CUR_SEASON} 已赛场次：" + "，".join(cur_total))


def write_meta_js():
    """写 assets/js/meta.js：仅含「本页更新」时间戳。

    「本页更新」= 本次真正把数据同步进站点的时刻（= now），不要取各数据文件里
    内嵌 generated 的 max —— 当某份数据「无变化」未被重写时，其内嵌 generated 会
    停留在旧值，max 会把整站时间拉回过去，造成「进球数页比平局页旧」这类不一致。
    统一以 sync_site.py 的运行时刻为准；纯代码提交的 generated 则由 pre-commit
    钩子（bump_meta.py）刷新，二者都是「最近一次部署时间」，方向永远向前。
    注：站点已不再展示「数据源更新时间」，meta.js 只保留 generated 一个键。
    """
    try:
        payload = {"generated": time.strftime("%Y-%m-%d %H:%M")}
        out = os.path.join(SITE, "assets/js/meta.js")
        text = "window.SITE_META = " + json.dumps(payload, ensure_ascii=False) + ";\n"
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  [OK] 已写入 {out}（本页更新 {payload['generated']}）")
    except Exception as e:
        print(f"  [WARN] meta.js 生成失败，跳过：{e}")


if __name__ == "__main__":
    main()
