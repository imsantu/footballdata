#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""draws 数据集拆分器（流水线步骤，由 sync_site.py 调用）。

把 sync_site.py 抽取后的内存数据对象拆成：
   assets/js/data/<group>/shell.js          —— 壳（赛季仅留 stub，cross/cross3 已移出）
   assets/js/data/<group>/<season>.js       —— 每季一个 chunk（自合并进 window.DATA）
   assets/js/data/<group>/cross.js          —— 跨赛季聚合（cross/cross3），按需懒加载
   并把 base64 队徽 / 联赛 logo 解码成真实 PNG 文件，
   crestByTeam / logoByCode 的值改为相对 URL。

pages 只首屏加载 shell.js + 2026-27.js，其余季 / cross 懒加载，
首屏 JS 体积从数 MB 降到 ~60KB（队徽外置后浏览器仅按需拉取可见 PNG）。

支持的 group（结构与 big5 完全一致：leagues[].seasons[<season>] + cross/cross3 +
crestByTeam + logoByCode）：
   draws-big5   —— 五大联赛平局
   draws-champ  —— 次级联赛平局

由 sync_site.py 在抽取+健康校验通过后直传内存对象调用，保证 chunk 始终由校验过的数据派生。
"""
import os, re, sys, json, base64, unicodedata, argparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREST_DIR = os.path.join(ROOT, "assets/img/crests")
LOGO_DIR = os.path.join(ROOT, "assets/img/leaguelogos")
# 次级联赛 logo 文件名加 "2" 后缀（en2/es2/...），与五大联赛的 en/es/... 区分。
# 原因：两套数据集共享 code 命名空间（en=英超/英冠、es=西甲/西乙 等），
# 若同名会互相覆盖，导致一个页面看到另一个联赛的 logo。run() 按 group 设置。
LOGO_SUFFIX = ""

# 赛季对象里的「重数组」键：壳里用 stub 替代，chunk 再填真实数据
HEAVY_KEYS = ("overall", "perRound", "teams")

# 当前进行中的赛季（首屏必加载，其余季懒加载）。big5 / champ 共用同一套赛季序。
# 唯一来源 = generator/season.py；优先用流水线统一的 FD_GENERATOR_DIR。
_GEN = os.environ.get("FD_GENERATOR_DIR") or os.path.join(ROOT, "generator")
if _GEN not in sys.path:
    sys.path.insert(0, _GEN)
from season import SEASON as CURRENT_SEASON  # noqa: E402


def slugify(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "team"


def decode_uri_to_file(uri, out_dir, slug, suffix=""):
    """data:image/...;base64,xxxx -> 写出文件，返回相对 URL（相对页面 pages/）。"""
    if not uri.startswith("data:"):
        return uri  # 已经是 URL，原样返回
    mm = re.match(r"^data:image/(\w+);base64,(.+)$", uri, re.S)
    if not mm:
        return uri
    ext = mm.group(1)
    if ext == "jpeg":
        ext = "jpg"
    raw = base64.b64decode(mm.group(2))
    base = slug + suffix
    path = os.path.join(out_dir, base + "." + ext)
    # draws-big5 / draws-champ 共用 assets/img/crests；同一队徽再次生成时直接复用，
    # 避免因每次运行的 used 集合不同而产生大量 slug2、slug3 重复文件。
    if os.path.exists(path):
        try:
            if open(path, "rb").read() == raw:
                return path
        except OSError:
            pass
    n = 2
    while os.path.exists(path):
        path = os.path.join(out_dir, base + str(n) + "." + ext)
        n += 1
    with open(path, "wb") as f:
        f.write(raw)
    return path


def season_stub(sd):
    """保留标量字段，去掉重数组，作为壳里的占位（供赛季 tab 计数 / 规模说明使用）。"""
    if not isinstance(sd, dict):
        return sd
    stub = {}
    for k, v in sd.items():
        if k in HEAVY_KEYS:
            continue
        stub[k] = v
    return stub


def run(group, obj=None, only_current=True):
    """把 draws 数据拆成按联赛+赛季的 chunk。

    obj 为 None 时回退到读取旧单体 <group>-data.js（手动一次性全量重建用）；
    日常由 sync_site.py 直传内存对象调用。only_current=True 只写 2026-27，
    历史赛季 chunk 保持冻结（已在 git 中），False 用于全量重建。
    """
    # 次级联赛 logo 文件名加 "2" 后缀，避免与五大联赛的 en/es/... 撞名互相覆盖。
    global LOGO_SUFFIX
    LOGO_SUFFIX = "2" if group == "draws-champ" else ""

    DATA_DIR = os.path.join(ROOT, "assets/js/data", group)
    SRC = os.path.join(ROOT, "assets/js", group + "-data.js")  # 仅手动回放旧单体时用
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CREST_DIR, exist_ok=True)
    os.makedirs(LOGO_DIR, exist_ok=True)

    if obj is None:
        if not os.path.exists(SRC):
            print("[SKIP] 源文件不存在，跳过 %s: %s" % (group, SRC))
            return
        text = open(SRC, encoding="utf-8").read()
        i = text.find("const DATA = ")
        if i < 0:
            raise SystemExit("[FAIL] %s 未找到 'const DATA = '，数据结构可能已变" % group)
        obj = json.loads(text[i + len("const DATA = "):].rstrip().rstrip(";"))

    season_order = obj["seasonOrder"]

    # ---- 1) 队徽 / 联赛 logo 解码为文件，值改为相对 URL ----
    crest = obj.get("crestByTeam", {})
    url_map = {}
    used = set()
    for name, uri in crest.items():
        if not uri.startswith("data:"):
            url_map[name] = uri
            continue
        base = slugify(name)
        slug = base
        n = 1
        while slug in used:
            n += 1
            slug = "%s-%d" % (base, n)
        used.add(slug)
        out = decode_uri_to_file(uri, CREST_DIR, slug)
        url_map[name] = "../assets/img/crests/" + os.path.basename(out)
    # 不回写 obj：调用方（sync_site.py）的 new 需保持原始形态（data URI），否则审计哈希
    # 在写入前后不一致，导致「无变化」判定永久误报。仅把 URL 映射用于写出。

    logo = obj.get("logoByCode", {})
    logo_map = {}
    for code, uri in logo.items():
        if not uri.startswith("data:"):
            logo_map[code] = uri
            continue
        # 五大联赛顶级 logo 已由站点统一维护（330px），不要被旧单体数据里的
        # 低清/过期 data URI 覆盖；次级联赛使用独立的 en2/es2/... 文件。
        existing = os.path.join(LOGO_DIR, code + LOGO_SUFFIX + ".png")
        if LOGO_SUFFIX == "" and os.path.exists(existing):
            logo_map[code] = "../assets/img/leaguelogos/" + os.path.basename(existing)
            continue
        out = decode_uri_to_file(uri, LOGO_DIR, code, LOGO_SUFFIX)
        logo_map[code] = "../assets/img/leaguelogos/" + os.path.basename(out)
    # 不回写 obj（理由同上：保留调用方 new 的原始形态）。

    # ---- 2) 壳：leagues 只留 meta + 每季 stub；cross/cross3 移出到 cross.js ----
    leagues_shell = []
    for lg in obj["leagues"]:
        seasons_stub = {}
        for sk, sd in (lg.get("seasons") or {}).items():
            seasons_stub[sk] = season_stub(sd)
        leagues_shell.append({
            "code": lg.get("code"),
            "cn": lg.get("cn"),
            "name": lg.get("name"),
            "seasons": seasons_stub,  # 占位 stub，chunk 填充真实数据
        })
    shell = {
        "seasonOrder": obj["seasonOrder"],
        "cats": obj["cats"],
        "meta": obj.get("meta"),
        "compare": obj.get("compare"),
        "compare3": obj.get("compare3"),
        "crestByTeam": url_map,
        "logoByCode": logo_map,
        "leagues": leagues_shell,
    }
    shell_js = "window.DATA = " + json.dumps(shell, ensure_ascii=False, separators=(",", ":")) + ";\n"
    with open(os.path.join(DATA_DIR, "shell.js"), "w", encoding="utf-8") as f:
        f.write(shell_js)
    print("[%s] shell.js:" % group, len(shell_js.encode("utf-8")), "bytes")

    # ---- 3) cross.js：跨赛季聚合（cross/cross3）单独成块，按需懒加载 ----
    C = {}
    for lg in obj["leagues"]:
        code = lg["code"]
        C[code] = {"cross": lg.get("cross"), "cross3": lg.get("cross3")}
    cross_js = (
        "(function(){var D=window.DATA;if(!D||!D.leagues)return;"
        "var M=" + json.dumps(C, ensure_ascii=False, separators=(",", ":")) + ";"
        "for(var i=0;i<D.leagues.length;i++){var L=D.leagues[i],c=M[L.code];"
        "if(c){L.cross=c.cross;L.cross3=c.cross3;}}})();\n"
    )
    with open(os.path.join(DATA_DIR, "cross.js"), "w", encoding="utf-8") as f:
        f.write(cross_js)
    print("[%s] cross.js:" % group, len(cross_js.encode("utf-8")), "bytes")

    # ---- 4) 每个联赛 / 每季一个 chunk（弱网下单次只取一个联赛）
    # 文件形如 data/draws-big5/en/2025-26.js；cross.js 仍为跨赛季汇总数据。
    for lg in obj["leagues"]:
        code = lg["code"]
        out_dir = os.path.join(DATA_DIR, code)
        os.makedirs(out_dir, exist_ok=True)
        for season in season_order:
            if only_current and season != CURRENT_SEASON:
                continue
            sd = lg.get("seasons", {}).get(season)
            if sd is None:
                continue
            chunk = (
                "(function(){var D=window.DATA;if(!D||!D.leagues)return;"
                "var s=" + json.dumps(sd, ensure_ascii=False, separators=(",", ":")) + ";"
                "for(var i=0;i<D.leagues.length;i++){var L=D.leagues[i];"
                "if(L.code===\"" + code + "\"){if(!L.seasons)L.seasons={};"
                "L.seasons[\"" + season + "\"]=Object.assign(L.seasons[\"" + season + "\"]||{},s);break;}}})();\n"
            )
            with open(os.path.join(out_dir, season + ".js"), "w", encoding="utf-8") as f:
                f.write(chunk)
            print("  [%s] %s/%s.js:" % (group, code, season), len(chunk.encode("utf-8")), "bytes")

    # ---- 5) 体积统计 ----
    total = len(shell_js.encode("utf-8"))
    for lg in obj["leagues"]:
        for season in season_order:
            p = os.path.join(DATA_DIR, lg["code"], season + ".js")
            if os.path.exists(p):
                total += os.path.getsize(p)
    n_crest = len([f for f in os.listdir(CREST_DIR) if not f.startswith(".")])
    n_logo = len([f for f in os.listdir(LOGO_DIR) if not f.startswith(".")])
    print("\n[%s] 首屏需下载(壳+当前季, 无压缩文本；GitHub Pages 会 gzip):" % group)
    first = len(shell_js.encode("utf-8"))
    for lg in obj["leagues"]:
        p = os.path.join(DATA_DIR, lg["code"], CURRENT_SEASON + ".js")
        if os.path.exists(p):
            first += os.path.getsize(p)
    print("  shell.js + 各联赛 %s.js =" % CURRENT_SEASON, first, "bytes")
    print("  其余季 + cross.js 在首屏后空闲时懒加载，零散按需")
    print("  队徽 PNG 总数:", n_crest, " 联赛 logo:", n_logo)
    if os.path.exists(SRC):
        print("[%s] 原单体 %s:" % (group, os.path.basename(SRC)), os.path.getsize(SRC), "bytes")
    else:
        print("[%s] 单体文件已废弃（数据由 sync_site.py 直传，不再落盘）" % group)
    print("[%s] 全部 chunk 文本合计:" % group, total, "bytes（含已外置的队徽，不再内联）")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="draws 数据集按季拆 chunk + 队徽外置")
    ap.add_argument("group", nargs="?", default="draws-big5",
                    choices=["draws-big5", "draws-champ"],
                    help="数据集组名（默认 draws-big5）")
    args = ap.parse_args()
    run(args.group, only_current=False)
