#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建 2026-27 赛季「赛程表」数据集（fixtures）。

数据源与 build_2026_27.py 完全相同 —— 因为 titan007 那份文件**本来就是全季赛程**：
  https://zq.titan007.com/jsData/matchResult/2026-2027/s{SclassID}[_{SubSclassID}].js
实测（2026-09-24）英超 s36 共 380 场 = 已完赛 50（status=-1）+ 未开赛 330（status=0，
ft 为空但开球时间已定到 2027-05-30）；意甲 380 = 50+330；英冠 552 = 95+457。
build_2026_27.py 只取已完赛（赛果用途），本脚本换个过滤条件把未开赛也留下，即得赛程表。
→ 零新增数据源、零新增网络请求（优先复用步骤 1 刚抓的 /tmp 缓存）、零新增队名映射链路。

更新语义（应对赛程调整 / 补赛）：
  每次全量覆盖。官方改期 / 补赛重排会改写该场的开球时间与轮次，覆盖即生效；
  「未开赛 → 已完赛」只是同一场 state 由 SCH 变 FT 并补上比分，故一张表即可，
  无需拆「赛程表 + 赛果表」两张。

幂等：
  新解析出的 matches 与盘上旧 chunk 完全一致时**整份不写**（shell 亦不写），
  避免每天产生无谓 diff；字段 updated 记的是「赛程内容最后变更时间」而非抓取时间。

失败策略：
  赛程是次要数据且无兜底源（赛果有 ESPN 兜底，赛程没有）。故单个联赛失败时**保留旧
  chunk 不动**并打 GHA 警告，绝不 exit 1 —— 不能因为赛程抓不到而拖垮当天赛果更新。

产物：
  assets/js/data/fixtures/shell.js          壳：联赛索引 + schema 说明
  assets/js/data/fixtures/<lg>/2026-27.js   每联赛一个 chunk
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from build_2026_27 import (  # noqa: E402
    ESPN_MAP, LEAGUES, TITAN_CN_ALIAS, TITAN_LEAGUES, TITAN_SEASON, TITAN_URL,
)
from season import SEASON as CUR_SEASON  # noqa: E402  （赛季唯一来源）

SITE = os.environ.get("FD_SITE_DIR") or os.path.dirname(HERE)
OUT_DIR = os.path.join(SITE, "assets", "js", "data", "fixtures")
CACHE_MAX_AGE = 30 * 60          # /tmp 缓存有效期（秒）：步骤 1 刚抓过就直接复用
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

SCHEMA = {
    "match": ["round", "kickoff", "home", "away", "state", "score"],
    "state": {"FT": "已完赛", "SCH": "未开赛"},
    "note": ("kickoff=北京时间 YYYY-MM-DD HH:MM（titan007 原始）；home/away=规范英文队名"
             "（与 draws/goals 同一套，可用 cn_map 反查中文）；score=主客视角 'H-A'，"
             "未开赛为空串；round=官方轮次"),
}


def warn(msg):
    """GHA 里显示为黄色注解，本机日志里也是醒目的 [WARN]。"""
    print(f"::warning title=赛程数据::{msg}")
    print(f"  [WARN] {msg}")


def js_dump(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def load_cn_maps():
    cn = {}
    for f in ("cn_map.json", "cn_map_champ.json"):
        p = os.path.join(HERE, "assets", f)
        if os.path.exists(p):
            try:
                cn.update(json.load(open(p, encoding="utf-8")))
            except Exception:
                pass
    return cn


def reverse_map(code, cn):
    """titan007 简体中文名 -> 规范英文名。

    限定在本联赛的 canonical 集合内（ESPN_MAP[code] 的值），规避跨联赛重名
    （如「谢菲尔德联」在英超/英冠都可能出现）。与 build_2026_27.fetch_titan_season
    里的 rev 构建方式保持一致。
    """
    rev = {}
    for canon in ESPN_MAP.get(code, {}).values():
        cv = cn.get(canon)
        if cv:
            rev.setdefault(cv, canon)
    return rev


def fetch_file(code, sc, sub):
    """取得 titan007 赛季文件：优先复用 /tmp 缓存（30 分钟内），否则自行下载。

    返回 (路径, 来源) 或 (None, None)。下载写 .part 再 rename —— 避免使用 os.remove
    （沙箱有「每轮删除配额」，超限后删除会静默失败）。
    """
    p = f"/tmp/titan_{code}_{sc}.js"
    if os.path.exists(p) and (time.time() - os.path.getmtime(p)) < CACHE_MAX_AGE:
        return p, "cache"
    url = TITAN_URL.format(season=TITAN_SEASON, SclassID=sc,
                           sub=("_" + str(sub)) if sub else "")
    tmp = p + ".part"
    for _ in range(3):
        try:
            subprocess.run(["curl", "-sSL", "--retry", "1", "--max-time", "35",
                            "-A", UA, "-H", "Referer: https://zq.titan007.com/",
                            "-o", tmp, url], check=True, capture_output=True)
        except Exception:
            pass
        try:
            head = open(tmp, encoding="utf-8", errors="replace").read(200)
        except Exception:
            head = ""
        if head and "<!DOCTYPE" not in head and "<html" not in head:
            os.replace(tmp, p)
            return p, "net"
        time.sleep(1)
    return None, None


def parse_season(path):
    """解析 titan007 赛季文件，返回 (arrLeague, id2cn, rows)。

    与 build_2026_27.parse_titan_file 的唯一区别：**保留未开赛场次**。
    单条记录 [matchId, SclassID, status, 'YYYY-MM-DD HH:MM', homeId, awayId, FT, HT, ...]
    """
    s = open(path, encoding="utf-8", errors="replace").read()
    id2cn = {}
    m = re.search(r"var arrTeam\s*=\s*(\[.*?\]);", s, re.S)
    if m:
        inner = m.group(1).strip()
        if inner.startswith("["):
            inner = inner[1:-1]
        for part in re.findall(r"\[[^\]]*\]", inner):
            cells = part[1:-1].split(",")
            if len(cells) >= 2:
                try:
                    id2cn[int(cells[0].strip())] = cells[1].strip().strip("'\"")
                except Exception:
                    pass
    lg = []
    m = re.search(r"var arrLeague\s*=\s*\[(.*?)\];", s, re.S)
    if m:
        lg = [c.strip().strip("'\"") for c in m.group(1).split(",")]
    rows = []
    for rm in re.finditer(r'jh\["R_(\d+)"\]\s*=\s*\[(.*?)\];', s, re.S):
        rn = int(rm.group(1))
        for rec in re.findall(r'\[([^\]]*)\]', rm.group(2)):
            cells = [c.strip() for c in rec.split(",")]
            if len(cells) < 7:
                continue
            try:
                hid, aid = int(cells[4]), int(cells[5])
            except Exception:
                continue
            ft = cells[6].strip().strip("'\"")
            status = cells[2].strip().strip("'\"")
            finished = (status == "-1") or bool(re.match(r"^\d+-\d+$", ft or ""))
            rows.append({
                "round": rn,
                "kickoff": cells[3].strip().strip("'\"")[:16],
                "home_cn": id2cn.get(hid, str(hid)),
                "away_cn": id2cn.get(aid, str(aid)),
                "state": "FT" if finished else "SCH",
                "score": ft if finished else "",
                "status": status,
            })
    return lg, id2cn, rows


def health(name, nteams, rows, round_declared):
    """赛程体检：双循环守恒 + 主客各半 + 无重复对阵 + 轮次吻合。

    返回 (errors, warns)。errors 非空即拒绝写入该联赛（保留旧 chunk）。
    """
    errs, warns = [], []
    total = len(rows)
    exp = nteams * (nteams - 1)
    if total != exp:
        errs.append(f"总场次 {total} != nteams*(nteams-1) = {exp}")
    hc, ac = Counter(), Counter()
    for r in rows:
        hc[r["home_cn"]] += 1
        ac[r["away_cn"]] += 1
    teams = set(hc) | set(ac)
    if len(teams) != nteams:
        errs.append(f"出现队数 {len(teams)} != {nteams}")
    bad = [t for t in teams if hc[t] != nteams - 1 or ac[t] != nteams - 1]
    if bad:
        errs.append(f"{len(bad)} 支球队主/客场次不等于 {nteams - 1}，如 {bad[:3]}")
    dup = [k for k, v in Counter((r["home_cn"], r["away_cn"]) for r in rows).items() if v > 1]
    if dup:
        errs.append(f"重复对阵 {len(dup)} 组，如 {dup[:2]}")
    mx = max(r["round"] for r in rows) if rows else 0
    if round_declared and mx != round_declared:
        warns.append(f"最大轮次 {mx} != arrLeague 声明 {round_declared}")
    odd = sorted({r["status"] for r in rows} - {"-1", "0"})
    if odd:
        warns.append(f"出现非 -1/0 的 status：{odd}")
    return errs, warns


def read_old_chunk(path):
    """从盘上旧 chunk 里取出数据对象（用于幂等比对）。不存在/解析失败返回 None。"""
    if not os.path.exists(path):
        return None
    try:
        s = open(path, encoding="utf-8").read()
        i = s.find("var s=")
        if i < 0:
            return None
        obj, _ = json.JSONDecoder().raw_decode(s[i + len("var s="):])
        return obj
    except Exception:
        return None


def read_old_shell():
    p = os.path.join(OUT_DIR, "shell.js")
    if not os.path.exists(p):
        return None
    try:
        s = open(p, encoding="utf-8").read()
        i = s.find("window.DATA = ")
        if i < 0:
            return None
        obj, _ = json.JSONDecoder().raw_decode(s[i + len("window.DATA = "):])
        return obj
    except Exception:
        return None


def write_chunk(lg, obj):
    d = os.path.join(OUT_DIR, lg)
    os.makedirs(d, exist_ok=True)
    body = ("(function(){var D=window.DATA;if(!D||!D.leagues)return;var s="
            + js_dump(obj) + ";for(var i=0;i<D.leagues.length;i++){var L=D.leagues[i];"
            'if(L.code==="' + lg + '"){if(!L.seasons)L.seasons={};'
            'L.seasons["' + CUR_SEASON + '"]=s;break;}}})();\n')
    with open(os.path.join(d, CUR_SEASON + ".js"), "w", encoding="utf-8") as f:
        f.write(body)
    return len(body.encode("utf-8"))


def write_shell(leagues):
    os.makedirs(OUT_DIR, exist_ok=True)
    obj = {
        "schema": SCHEMA,
        "seasonOrder": [CUR_SEASON],
        "leagues": leagues,
        "meta": {"src": "titan007", "srcUrl": "https://zq.titan007.com/",
                 "generated": time.strftime("%Y-%m-%d %H:%M")},
    }
    with open(os.path.join(OUT_DIR, "shell.js"), "w", encoding="utf-8") as f:
        f.write("window.DATA = " + js_dump(obj) + ";\n")


def main():
    if "/Desktop/" in OUT_DIR or OUT_DIR.endswith("/Desktop"):
        print("[FAIL] 输出目录位于桌面，已中止")
        sys.exit(1)

    cn = load_cn_maps()
    old_shell = read_old_shell() or {}
    old_leagues = {l.get("code"): l for l in (old_shell.get("leagues") or [])}
    now = time.strftime("%Y-%m-%d %H:%M")

    print("════════ 构建 2026-27 赛程表（fixtures）════════")
    leagues_out, changed, failed, skipped = [], [], [], []

    for code, cn_short, lg, div in LEAGUES:
        sc, sub = TITAN_LEAGUES[code]
        # 五大联赛与次级联赛同处一个 group，必须用不同 code 区分，否则英超/英冠
        # 都会写成 en/2026-27.js、互相覆盖（且幂等永久失效）。站内既有约定是次级
        # 联赛加 "2" 后缀（en2/es2/de2/it2/fr2），与 gen_app_data.js 的命名一致。
        lcode = lg + ("2" if div == 2 else "")
        prev = old_leagues.get(lcode) or {}
        meta = {
            "code": lcode,
            "cn": cn_short,
            "name": prev.get("name", ""),
            "en": prev.get("en", ""),
            "tier": "big5" if div == 1 else "champ",
            "titan": [sc, sub],
            "seasons": prev.get("seasons") or {},
        }
        path = os.path.join(OUT_DIR, lcode, CUR_SEASON + ".js")

        src_file, how = fetch_file(code, sc, sub)
        if not src_file:
            failed.append(f"{cn_short}({code}) 抓取失败")
            warn(f"{cn_short}({code}) titan007 抓取失败，保留旧赛程数据")
            leagues_out.append(meta)
            continue

        lg_arr, id2cn, rows = parse_season(src_file)
        if lg_arr and len(lg_arr) > 1:
            meta["name"] = str(lg_arr[1]).strip()
        if lg_arr and len(lg_arr) > 3:
            meta["en"] = str(lg_arr[3]).strip()
        round_declared = 0
        if lg_arr and len(lg_arr) > 7:
            try:
                round_declared = int(str(lg_arr[7]).strip())
            except Exception:
                round_declared = 0

        rev = reverse_map(code, cn)
        if not rev:
            failed.append(f"{cn_short}({code}) 无反向映射表")
            warn(f"{cn_short}({code}) 无队名反向映射表，保留旧赛程数据")
            leagues_out.append(meta)
            continue

        nteams = len(id2cn)
        matches, unmapped = [], set()
        for r in rows:
            h = rev.get(r["home_cn"]) or rev.get(TITAN_CN_ALIAS.get(r["home_cn"], ""))
            a = rev.get(r["away_cn"]) or rev.get(TITAN_CN_ALIAS.get(r["away_cn"], ""))
            if not h or not a:
                unmapped.add(r["home_cn"])
                unmapped.add(r["away_cn"])
                continue
            matches.append([r["round"], r["kickoff"], h, a, r["state"], r["score"]])

        if unmapped:
            warn(f"{cn_short} 有未映射队名 {sorted(unmapped)}，相关场次已跳过")
        if not matches:
            failed.append(f"{cn_short}({code}) 无可用场次")
            warn(f"{cn_short}({code}) 无可用场次，保留旧赛程数据")
            leagues_out.append(meta)
            continue

        errs, warns = health(cn_short, nteams, rows, round_declared)
        for w in warns:
            warn(f"{cn_short} {w}")
        if errs:
            failed.append(f"{cn_short}({code}) 体检未通过")
            for e in errs:
                warn(f"{cn_short} 体检：{e}")
            warn(f"{cn_short}({code}) 体检未通过，保留旧赛程数据")
            leagues_out.append(meta)
            continue

        matches.sort(key=lambda m: (m[0], m[1], m[2]))
        byround = defaultdict(list)
        for m in matches:
            byround[m[0]].append(m[1][:10])
        played = sum(1 for m in matches if m[4] == "FT")
        obj = {
            "season": CUR_SEASON,
            "nteams": nteams,
            "roundMax": max(byround),
            "total": len(matches),
            "played": played,
            "remaining": len(matches) - played,
            "first": min(m[1] for m in matches)[:10],
            "last": max(m[1] for m in matches)[:10],
            "rounds": [{"round": k, "from": min(v), "to": max(v), "n": len(v)}
                       for k, v in sorted(byround.items())],
            "matches": matches,
        }

        old = read_old_chunk(path)
        if old and old.get("matches") == matches:
            skipped.append(f"{cn_short}({code})")
            meta["seasons"][CUR_SEASON] = {"season": CUR_SEASON, "nteams": nteams,
                                           "roundMax": obj["roundMax"], "total": obj["total"],
                                           "played": played, "remaining": obj["remaining"],
                                           "updated": old.get("updated", "")}
            leagues_out.append(meta)
            print(f"  [=] {cn_short}({code}) 赛程无变化 {obj['total']} 场"
                  f"（已完赛 {played} / 未开赛 {obj['remaining']}）")
        else:
            obj["updated"] = now
            size = write_chunk(lcode, obj)
            changed.append(cn_short)
            meta["seasons"][CUR_SEASON] = {"season": CUR_SEASON, "nteams": nteams,
                                           "roundMax": obj["roundMax"], "total": obj["total"],
                                           "played": played, "remaining": obj["remaining"],
                                           "updated": now}
            leagues_out.append(meta)
            print(f"  [+] {cn_short}({code}) 赛程 {obj['total']} 场"
                  f"（已完赛 {played} / 未开赛 {obj['remaining']}，"
                  f"{obj['roundMax']} 轮，{obj['first']}~{obj['last']}，"
                  f"{size / 1024:.0f} KB，来源 {how}）")

    # shell：leagues 索引有变化（或首次）才写，避免无谓 diff
    old_leagues_json = js_dump(old_shell.get("leagues") or [])
    if old_leagues_json != js_dump(leagues_out):
        write_shell(leagues_out)
        print(f"  [shell] 联赛索引已更新（{len(leagues_out)} 个联赛）")
    else:
        print("  [shell] 联赛索引无变化，跳过")

    print()
    print(f"  变化 {len(changed)} 个：{('、'.join(changed)) or '无'}")
    print(f"  无变化 {len(skipped)} 个：{('、'.join(skipped)) or '无'}")
    if failed:
        print(f"  [WARN] 失败 {len(failed)} 个：{'；'.join(failed)}")
        print("  [WARN] 失败联赛保留旧赛程数据，本次不阻塞主流水线")
    print(f"════════ 赛程表构建完成 {time.strftime('%F %T')} ════════")


if __name__ == "__main__":
    main()
