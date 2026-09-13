#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「重新生成的三份报告 HTML」里的数据块同步进静态站点。

设计原则（对应最初的需求「千万不要改动数据内容」）：
  * 只搬数据，绝不碰站点的外壳：site.js / site.css / 页面 JS / 页面 CSS / 字体 一律不动。
  * 写入前先备份旧文件到 automation/backups/<时间戳>/。
  * 唯一的例外是进数球数据的「补全」步骤（见 enrich_goals）——它不 invent 数据，
    只是把平局报告里已有的官方轮次 / 主客场回填进进数球数据，并按轮次重排色带。
  * 写入前做体检，任何一条不通过就整批中止，一个字节都不写：
      1. 新旧顶层键集合必须一致
      2. 联赛数量、赛季（scope）键集合必须一致
      3. 历史赛季（非 2026-27）的场次必须一字不变 —— 防止误伤已完成赛季
      4. 2026-27 的场次只能增加不能减少 —— 进行中的赛季只会越赛越多
  * 序列化风格沿用目标文件现有的写法（draws 用带空格的默认风格，goals 用紧凑风格），
    避免每次运行产生无意义的整文件 diff。
"""

import json
import os
import re
import shutil
import sys
import time

WS = "/Users/santu/WorkBuddy AI/2026-09-02-02-18-19"
GOALS_WS = "/Users/santu/WorkBuddy AI/2026-08-24-11-07-48"
SITE = "/Users/santu/soccerdata/football-data-site"
AUTO = os.path.join(SITE, "tools")
BACKUP_DIR = os.path.join(AUTO, "backups")

CUR_SEASON = "2026-27"

JOBS = [
    {
        "name": "平局统计 · 五大联赛",
        "src": f"{WS}/football_big5_draws_report.html",
        "marker": "const DATA = ",
        "dst": f"{SITE}/assets/js/draws-big5-data.js",
        "kind": "draws",
        "role": "draws-big5",          # 进数球回填官方轮次 / 主客场的基准源
    },
    {
        "name": "平局统计 · 次级联赛",
        "src": f"{WS}/football_champ_draws_report.html",
        "marker": "const DATA = ",
        "dst": f"{SITE}/assets/js/draws-champ-data.js",
        "kind": "draws",
    },
    {
        "name": "进球数统计",
        "src": f"{GOALS_WS}/football_en_goals_buckets_report.html",
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
    """沿用目标文件现有的序列化风格：返回 json.dumps 的 separators 参数。"""
    i = text.find(marker)
    sample = text[i + len(marker): i + len(marker) + 4000]
    return None if '": ' in sample else (",", ":")


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
                    by_date[p[1]] = (p[2], p[0])
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
    """给进数球数据的 seq23Matches 补 ha / round，并把色带重排成轮次顺序。

    背景：进数球生成器只按日期贪心排列，且根本没输出主客场，于是
      · 色带顺序 = 日期序，遇到补赛 / 提前进行的轮次就与真实轮次错位
      · 悬浮框判不出主客，只能一律按「本队主场」渲染，客场比赛的比分方向是错的
    平局报告的 formDetail 带官方轮次与主客场，用它按（队名 + 日期）回填。

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
                        gm["ha"], gm["round"] = v[0], v[1]
                        hit += 1
                n_hit += hit
                # 只有「进行中的赛季」才重排：历史赛季官方轮次虽可信，但重排会改变
                # 已展示过的 gap/streak，违背本流水线「历史赛季绝不改动」的原则。
                if hit != len(live) or season != CUR_SEASON:
                    continue                      # 覆盖不全 / 历史赛季，不重排
                n_team += 1
                pairs = sorted(zip(sq, ms),
                               key=lambda p: (as_int(p[1].get("round")), p[1].get("date") or ""))
                t["seq23"] = [p[0] for p in pairs]
                t["seq23Matches"] = [p[1] for p in pairs]
                n_cell += len(pairs)
                seq = t["seq23"]
                for n in (2, 3):
                    t["gap%d" % n] = longest_run(seq, (lambda v, n=n: v != n))
                    t["streak%d" % n] = longest_run(seq, (lambda v, n=n: v == n))
                    t["count%d" % n] = sum(1 for v in seq if v == n)
    return n_hit, n_team, n_cell


def main():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    bdir = os.path.join(BACKUP_DIR, stamp)
    os.makedirs(bdir, exist_ok=True)

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
        if job["kind"] == "goals" and draws_obj is not None:
            n_hit, n_team, n_cell = enrich_goals(new, draws_obj)
            print(f"    回填主客场/轮次：命中 {n_hit} 场，"
                  f"按轮次重排 {n_team} 支球队 / {n_cell} 格（派生 gap/streak 已重算）")
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

        shutil.copy2(dst, os.path.join(bdir, os.path.basename(dst)))
        planned.append((job, new, cur_text, same))

    updatable = [p for p in planned if not p[3]]
    if not updatable:
        print("\n=== 三份数据均无变化，跳过写入 ===")
        print("SUMMARY|无变化")
        return

    print(f"\n=== 写入阶段（备份已存于 {bdir}）===")
    for job, new, cur_text, _ in updatable:
        # 「本页更新」= 本次真正把数据写进站点的时刻（与「数据源更新」解耦）
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
        # 取「数据源更新」里最新的一个（正常情况下三份一致）
        src_vals = [m.get("srcUpdated") for m in metas.values() if m.get("srcUpdated")]
        gen_vals = [m.get("generated") for m in metas.values() if m.get("generated")]
        payload = {
            "srcUpdated": max(src_vals) if src_vals else "",
            "generated": max(gen_vals) if gen_vals else "",
        }
        out = os.path.join(SITE, "assets/js/meta.js")
        text = "window.SITE_META = " + json.dumps(payload, ensure_ascii=False) + ";\n"
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"  [OK] 已写入 {out}（数据源 {payload['srcUpdated']} / 本页 {payload['generated']}）")
    except Exception as e:
        print(f"  [WARN] meta.js 生成失败，跳过：{e}")


if __name__ == "__main__":
    main()
