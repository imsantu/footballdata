#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""goals 数据集拆分器（流水线步骤，由 sync_site.py 调用）。

把 sync_site.py 抽取并 enrich 后的内存数据对象拆成：
   assets/js/data/goals/shell.js          —— 壳（各季 scope 仅留标量 stub，teams/buckets 已移出）
   assets/js/data/goals/<season>.js       —— 每季一个 chunk（自合并进 window.DATA.leagues[i].scopes[season]）
   并把 base64 队徽解码成真实 PNG 文件，crests 的值改为相对 URL。

goals 与 draws 结构不同：
   - 顶层键是 buckets/labels/leagues/crests/meta（无 seasonOrder/cross/compare）
   - 联赛用 lg.order（季序）与 lg.scopes[season]（每季数据，含 teams/buckets 重数组），
     没有 draws 的 seasons/cross/cross3
   - 队徽键名是 crests（不是 crestByTeam），联赛 logo 也走 assets/img/leaguelogos/<code>.png
     （与 draws 同一份外置 PNG，体积小、首屏快，避免壳里内嵌 data URI）
   - 队徽外置到 assets/img/crests/（与 draws 共用同一份，不再单独建 goals-crests）

pages 只首屏加载 shell.js + 2026-27.js，其余季懒加载，
首屏 JS 体积从 ~4.35MB 降到 ~数十 KB（队徽 / 联赛 logo 外置后浏览器按需拉取可见 PNG）。
"""
import os, re, json, base64, unicodedata

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "assets/js", "goals-data.js")  # 仅手动回放旧单体时用

# scope 对象里的「重数组」键：壳里用 stub 替代，chunk 再填真实数据
HEAVY_KEYS = ("teams", "buckets")
CURRENT_SEASON = "2026-27"

# 次级联赛 logo 文件名加 "2" 后缀（en2/es2/...），与五大联赛的 en/es/... 区分。
# 原因：两套数据集共享 code 命名空间（en=英超/英冠、es=西甲/西乙 等），
# 若同名会互相覆盖，导致一个页面看到另一个联赛的 logo。generate() 按 group 设置。
LOGO_SUFFIX = ""


def slugify(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "team"


def decode_uri_to_file(uri, out_dir, slug):
    """data:image/...;base64,xxxx -> 写出文件，返回路径。

    与 draws 共用 assets/img/crests/：**内容相同则复用既有文件**，不覆盖、不产生副本。
    这一点很重要 —— 该目录被 draws-big5 / draws-champ / goals / goals-champ 四套数据共用，
    若无条件覆盖，goals 侧一张略有差异的同名图就会悄悄改掉平局页的队徽。
    """
    if not uri.startswith("data:"):
        return uri
    mm = re.match(r"^data:image/(\w+);base64,(.+)$", uri, re.S)
    if not mm:
        return uri
    ext = mm.group(1)
    if ext == "jpeg":
        ext = "jpg"
    raw = base64.b64decode(mm.group(2))
    path = os.path.join(out_dir, slug + "." + ext)
    if os.path.exists(path):
        try:
            if open(path, "rb").read() == raw:
                return path
        except OSError:
            pass
    n = 2
    while os.path.exists(path):
        path = os.path.join(out_dir, slug + str(n) + "." + ext)
        n += 1
    with open(path, "wb") as f:
        f.write(raw)
    return path


def scope_stub(sc):
    """保留标量字段，去掉重数组 teams/buckets，作为壳里的占位。"""
    if not isinstance(sc, dict):
        return sc
    stub = {}
    for k, v in sc.items():
        if k in HEAVY_KEYS:
            continue
        stub[k] = v
    return stub


def generate(obj, only_current=True, group="goals"):
    """把内存里的 goals 数据对象拆成按联赛+赛季的 chunk。

    group="goals"      —— 五大联赛进球数（DATA_DIR=assets/js/data/goals，logo 无后缀）
    group="goals-champ"—— 次级联赛进球数（DATA_DIR=assets/js/data/goals-champ，logo 加 2 后缀）

    队徽两组合用 assets/img/crests/（与 draws 也是同一份）：四套数据集的 slugify 规则
    完全一致，同名即同图，共用后省掉一份 2.1MB 的完全重复目录。

    only_current=True 时只写 CURRENT_SEASON（2026-27）的 chunk，历史赛季的 chunk
    保持不动（已在 git 中冻结，日常同步只动当前进行中的赛季）；False 用于新赛季
    开局 / 结构性调整时的一次性全量重建。日常由 sync_site.py 直传内存对象调用。
    """
    # 次级联赛：数据目录 / 队徽目录加 champ 区分；联赛 logo 文件名加 "2" 后缀。
    global LOGO_SUFFIX
    LOGO_SUFFIX = "2" if group == "goals-champ" else ""
    DATA_DIR = os.path.join(ROOT, "assets/js/data", group)
    # 队徽目录：四套数据集共用 assets/img/crests/（同名同图，不再按 group 分目录）
    CREST_DIR = os.path.join(ROOT, "assets/img/crests")
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CREST_DIR, exist_ok=True)

    season_order = []
    for lg in obj["leagues"]:
        for k in lg.get("order", []):
            if k not in season_order:
                season_order.append(k)

    # ---- 1) 队徽解码为文件，值改为相对 URL ----
    crests = obj.get("crests", {})
    url_map = {}
    used = set()
    for name, uri in crests.items():
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
        url_map[name] = "../assets/img/%s/" % os.path.basename(CREST_DIR) + os.path.basename(out)
    # 不回写 obj：调用方（sync_site.py）的 new 需要保持抽取时的原始形态（data URI），
    # 否则审计哈希在写入前后不一致，导致「无变化」判定永久误报。仅把 URL 映射用于写出。

    # ---- 2) 壳：leagues 只留标量 meta + 每季 scope stub；logo 走外置 PNG ----
    # 与 draws 统一：联赛 logo 用 assets/img/leaguelogos/<code>.png，
    # PNG 不存在时才回退到内联 data URI（兼容历史数据）。
    leagues_shell = []
    for lg in obj["leagues"]:
        scopes_stub = {}
        for sk, sc in (lg.get("scopes") or {}).items():
            scopes_stub[sk] = scope_stub(sc)
        code = lg.get("code")
        logo_png = os.path.join(ROOT, "assets/img/leaguelogos", (code or "") + LOGO_SUFFIX + ".png")
        if code and os.path.exists(logo_png):
            logo_val = "../assets/img/leaguelogos/" + code + LOGO_SUFFIX + ".png"
        else:
            logo_val = lg.get("logo")          # 兜底：内联 data URI
        leagues_shell.append({
            "code": code,
            "cn": lg.get("cn"),
            "logo": logo_val,
            "order": lg.get("order"),
            "scopes": scopes_stub,
        })
    shell = {
        "buckets": obj["buckets"],
        "labels": obj["labels"],
        "meta": obj.get("meta"),
        "crests": url_map,
        "leagues": leagues_shell,
    }
    shell_js = "window.DATA = " + json.dumps(shell, ensure_ascii=False, separators=(",", ":")) + ";\n"
    with open(os.path.join(DATA_DIR, "shell.js"), "w", encoding="utf-8") as f:
        f.write(shell_js)
    print("[%s] shell.js:" % group, len(shell_js.encode("utf-8")), "bytes")

    # ---- 3) 每个联赛 / 每季一个 chunk（弱网下单次只取几十 KB）
    # 文件形如 data/goals/en/2025-26.js；shell 只保留各赛季标量 stub。
    for lg in obj["leagues"]:
        code = lg["code"]
        out_dir = os.path.join(DATA_DIR, code)
        os.makedirs(out_dir, exist_ok=True)
        for season in season_order:
            if only_current and season != CURRENT_SEASON:
                continue
            sc = lg.get("scopes", {}).get(season)
            if sc is None:
                continue
            chunk = (
                "(function(){var D=window.DATA;if(!D||!D.leagues)return;"
                "var s=" + json.dumps(sc, ensure_ascii=False, separators=(",", ":")) + ";"
                "for(var i=0;i<D.leagues.length;i++){var L=D.leagues[i];"
                "if(L.code===\"" + code + "\"){if(!L.scopes)L.scopes={};"
                "L.scopes[\"" + season + "\"]=Object.assign(L.scopes[\"" + season + "\"]||{},s);break;}}})();\n"
            )
            with open(os.path.join(out_dir, season + ".js"), "w", encoding="utf-8") as f:
                f.write(chunk)
            print("  [%s] %s/%s.js:" % (group, code, season), len(chunk.encode("utf-8")), "bytes")

    # ---- 4) 体积统计 ----
    total = len(shell_js.encode("utf-8"))
    for lg in obj["leagues"]:
        for season in season_order:
            p = os.path.join(DATA_DIR, lg["code"], season + ".js")
            if os.path.exists(p):
                total += os.path.getsize(p)
    n_crest = len([f for f in os.listdir(CREST_DIR) if not f.startswith(".")])
    print("\n[%s] 首屏需下载(壳+当前季, 无压缩文本；GitHub Pages 会 gzip):" % group)
    first = len(shell_js.encode("utf-8"))
    for lg in obj["leagues"]:
        p = os.path.join(DATA_DIR, lg["code"], CURRENT_SEASON + ".js")
        if os.path.exists(p):
            first += os.path.getsize(p)
    print("  shell.js + 各联赛 %s.js =" % CURRENT_SEASON, first, "bytes")
    print("  其余季在首屏后空闲时懒加载，零散按需")
    print("  队徽 PNG 总数:", n_crest)
    if os.path.exists(SRC):
        print("[%s] 旧单体 goals-data.js:" % group, os.path.getsize(SRC), "bytes")
    else:
        print("[%s] 单体文件已废弃（数据由 sync_site.py 直传，不再落盘）" % group)
    print("[%s] 全部 chunk 文本合计:" % group, total, "bytes（含已外置的队徽，不再内联）")


def main():
    """CLI：从单体/源文件全量拆分（仅手动一次性全量重建时用；日常由 sync_site.py 直传）。

    日常同步请走 sync_site.py（它会把抽取并 enrich 后的内存对象直接传给 generate）。
    这里保留 CLI 以便需要手动回放某个数据文件时全量重建所有赛季 chunk。
    """
    import argparse
    ap = argparse.ArgumentParser(description="goals 数据集按季拆 chunk + 队徽外置")
    ap.add_argument("--src", help="数据文件（默认读取旧单体 goals-data.js）")
    args = ap.parse_args()
    src = args.src or SRC
    if not os.path.exists(src):
        raise SystemExit("[FAIL] 源数据不存在：%s（日常运行请走 sync_site.py）" % src)
    text = open(src, encoding="utf-8").read()
    i = text.find("window.DATA = ")
    prefix_len = len("window.DATA = ")
    if i < 0:
        i = text.find("const DATA = ")
        prefix_len = len("const DATA = ")
    if i < 0:
        raise SystemExit("[FAIL] 未找到 DATA 赋值语句")
    obj = json.loads(text[i + prefix_len:].rstrip().rstrip(";"))
    generate(obj, only_current=False)


if __name__ == "__main__":
    main()
