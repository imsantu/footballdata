#!/usr/bin/env python3
"""静态引用闸门（两道）—— 渲染快照抓不到的那些「全量字符串表」与「页面接线」。

闸门 ①：数据/逻辑 JS 里引用的 assets/img/** 必须真实存在且已被 git 跟踪。
  为什么需要它（2026-09-26 真实事故）：
    渲染黄金快照只能覆盖「用例里那几十个容器 + 那几个赛季」，抓不到**队徽映射**这类
    全量字符串表的变化 —— 涉事球队（CD Leganés / UD Las Palmas）根本不在任何被覆盖的
    赛季里。于是「shell 引用了一个未被 git 跟踪的新文件」这件事，快照门禁完全无感，
    而线上表现是 404 / 错图。
    这次的触发链：本机旧报告（08-24 工作区）给这两支队的 base64 是**城市照片**（120×60）
    而不是队徽；生成器把 ext 取自 MIME，于是写出 cd-leganes.jpg（既有的 cd-leganes.png
    变成孤儿），shell 立刻改指 .jpg —— 该 .jpg 默认未被 git 跟踪，提交时极易漏掉。

闸门 ②：页面接线与 assets/js/manifest.js 的 PAGES 表必须一致（P2-② 之后新增）。
  manifest.js 是「页面身份」的唯一真相源：site.js 由它派生页头下拉与首页卡片，
  draws.js / goals.js 由它拿到 DRAWS_CFG / GOALS_CFG。三件事必须同时成立：
    ②a 任何加载 site.js 的页面，都必须在 site.js **之前**同步加载 manifest.js
        （漏了 → site.js 抛错 → 整页导航与首页卡片全空）
    ②b PAGES 里登记的 file 必须在 pages/ 下真实存在（否则导航点到 404）
    ②c pages/ 下每个加载 site.js 的页面都必须在 PAGES 里登记
        （漏登记 → 该页 CFG 为 undefined → draws.js / goals.js 抛错 → 整页白屏）
  这三条正是「加一个页面忘了改另一处」的典型形态，而快照用例是按现有页面写的，
  新页面没登记时快照里根本没有它的用例，一样会全绿。

用法：
  python3 tools/check_asset_refs.py            # 检查，失败 exit 1
  python3 tools/check_asset_refs.py --list     # 只列 assets/img 引用，不做判定
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 闸门 ① ----
# 引用形如 "../assets/img/crests/xxx.png"（相对 pages/）或 "assets/img/..."（相对根）
REF_RE = re.compile(r"[\"'(](\.\./)*assets/img/[A-Za-z0-9._/@-]+[\"')]")
SCAN_DIRS = ["assets/js", "pages", "index.html"]

# ---- 闸门 ② ----
MANIFEST = os.path.join("assets", "js", "manifest.js")
# 加载 site.js 但**故意**不在导航里登记的独立页（如占位页）
ALLOW_UNREGISTERED = {"more.html"}
# manifest.js 里 PAGES 的一条记录：  'id': { ... file: 'x.html' ... }
PAGE_ENTRY_RE = re.compile(
    r"^\s*'([A-Za-z0-9._-]+)'\s*:\s*\{(.*?)^\s*\},?\s*$", re.M | re.S)
PAGE_FILE_RE = re.compile(r"\bfile\s*:\s*'([^']+)'")
# ⚠️ 必须匹配真正的 <script src="…">，不能裸找子串 —— 这些页面的注释里大量出现
#    「由 site.js 的三态主题接管」这类说法，裸子串会命中注释造成误报。
SCRIPT_TAG_RE = r"<script[^>]*\bsrc\s*=\s*[\"'][^\"']*%s[\"']"


def script_pos(txt, name):
    m = re.search(SCRIPT_TAG_RE % re.escape(name), txt, re.I)
    return m.start() if m else -1


def iter_files():
    for rel in SCAN_DIRS:
        p = os.path.join(ROOT, rel)
        if os.path.isfile(p):
            yield p
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
            for fn in filenames:
                if fn.endswith((".js", ".html", ".css")):
                    yield os.path.join(dirpath, fn)


def tracked_set():
    out = subprocess.run(["git", "ls-files", "assets/img"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return set(out.split())


def check_asset_refs():
    """闸门 ①：返回 (ok, 输出行列表)。"""
    lines = []
    tracked = tracked_set()
    refs = {}   # relpath(仓库根) -> set(来源文件)
    for f in iter_files():
        try:
            txt = open(f, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for m in REF_RE.finditer(txt):
            raw = m.group(0).strip("\"'()")
            rel = raw
            while rel.startswith("../"):
                rel = rel[3:]
            rel = rel.lstrip("/")
            refs.setdefault(rel, set()).add(os.path.relpath(f, ROOT))

    missing, untracked = [], []
    for rel in sorted(refs):
        if not os.path.exists(os.path.join(ROOT, rel)):
            missing.append(rel)
        elif rel not in tracked:
            untracked.append(rel)

    lines.append("扫描到 %d 个不同的 assets/img 引用" % len(refs))
    if missing:
        lines.append("\n❌ 引用了**磁盘上不存在**的文件（线上 404）：")
        for rel in missing:
            lines.append("   %s   <- %s" % (rel, ", ".join(sorted(refs[rel]))))
    if untracked:
        lines.append("\n❌ 引用了**未被 git 跟踪**的文件（提交时极易漏掉，线上 404）：")
        for rel in untracked:
            lines.append("   %s   <- %s" % (rel, ", ".join(sorted(refs[rel]))))
    if not missing and not untracked:
        lines.append("✅ 全部引用都存在且已被 git 跟踪")
    return (not missing and not untracked), lines


def manifest_pages():
    """从 manifest.js 的 PAGES 表里取出 {页面 id: file}。"""
    p = os.path.join(ROOT, MANIFEST)
    if not os.path.exists(p):
        return None
    txt = open(p, encoding="utf-8").read()
    m = re.search(r"var\s+PAGES\s*=\s*\{(.*?)\n\s*\};", txt, re.S)
    if not m:
        return None
    out = {}
    for mm in PAGE_ENTRY_RE.finditer(m.group(1)):
        fid = PAGE_FILE_RE.search(mm.group(2))
        if fid:
            out[mm.group(1)] = fid.group(1)
    return out


def html_pages():
    """返回 {pages/ 下的文件名: 该页全文}。"""
    d = os.path.join(ROOT, "pages")
    out = {}
    if os.path.isdir(d):
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".html"):
                out[fn] = open(os.path.join(d, fn), encoding="utf-8").read()
    return out


def check_manifest_wiring():
    """闸门 ②：返回 (ok, 输出行列表)。"""
    lines = []
    pages = manifest_pages()
    if pages is None:
        return False, ["❌ 读不到 %s 的 PAGES 表（闸门 ② 无法执行）" % MANIFEST]

    ok = True
    htmls = html_pages()

    # ②a 加载 site.js 的页面必须在它之前加载 manifest.js
    bad_order = []
    for fn, txt in sorted(htmls.items()):
        if fn in ALLOW_UNREGISTERED:
            continue
        i_site = script_pos(txt, "site.js")
        if i_site < 0:
            continue
        i_man = script_pos(txt, "manifest.js")
        if i_man < 0:
            bad_order.append((fn, "完全没有引用 manifest.js"))
        elif i_man > i_site:
            bad_order.append((fn, "manifest.js 排在 site.js 之后"))
    # 首页（index.html）同样适用
    idx = os.path.join(ROOT, "index.html")
    if os.path.exists(idx):
        txt = open(idx, encoding="utf-8").read()
        i_site, i_man = script_pos(txt, "site.js"), script_pos(txt, "manifest.js")
        if i_site >= 0 and (i_man < 0 or i_man > i_site):
            bad_order.append(("index.html", "manifest.js 缺失或排在 site.js 之后"))

    if bad_order:
        ok = False
        lines.append("\n❌ 页面没有在 site.js 之前同步加载 manifest.js"
                     "（会导致 site.js 抛错 → 页头导航与首页卡片全空）：")
        for fn, why in bad_order:
            where = fn if fn == "index.html" else "pages/" + fn
            lines.append("   %s   %s" % (where, why))

    # ②b PAGES 里的 file 必须真实存在
    gone = [pid for pid, f in pages.items()
            if not os.path.exists(os.path.join(ROOT, "pages", f))]
    if gone:
        ok = False
        lines.append("\n❌ manifest.js 的 PAGES 登记了不存在的页面（导航会点到 404）：")
        for pid in sorted(gone):
            lines.append("   %s -> pages/%s" % (pid, pages[pid]))

    # ②c pages/ 下每个加载 site.js 的页面都必须在 PAGES 里登记
    registered = set(pages.values())
    unreg = [fn for fn, txt in sorted(htmls.items())
             if script_pos(txt, "site.js") >= 0 and fn not in registered
             and fn not in ALLOW_UNREGISTERED]
    if unreg:
        ok = False
        lines.append("\n❌ 页面加载了 site.js 但没在 manifest.js 的 PAGES 里登记"
                     "（该页 CFG 为 undefined → 逻辑脚本抛错 → 白屏）：")
        for fn in unreg:
            lines.append("   pages/%s" % fn)

    if ok:
        lines.append("✅ 页面接线与 manifest.js 一致（%d 个已登记页面，%d 个页面已接线）"
                     % (len(pages), len(htmls)))
    return ok, lines


def main():
    list_only = "--list" in sys.argv

    ok1, out1 = check_asset_refs()
    if list_only:
        print("\n".join(out1))
        return 0

    ok2, out2 = check_manifest_wiring()

    print("──── 闸门 ① assets/img 引用 ────")
    print("\n".join(out1))
    print("\n──── 闸门 ② 页面接线 ↔ manifest.js ────")
    print("\n".join(out2))
    return 0 if (ok1 and ok2) else 1


if __name__ == "__main__":
    sys.exit(main())
