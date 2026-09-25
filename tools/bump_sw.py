#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sw.js 的 CACHE 版本号自动递增（替代纯人工步骤）。

为什么需要
----------
sw.js 是**运行时缓存**（fetch 时按需缓存，没有预缓存清单）。CACHE 版本号一变，
activate 阶段就会删掉所有旧 cache，从而强制下次访问重新拉取。

改了外壳文件却忘了 +1 → 用户一直拿旧缓存 →「明明上线了却看不到变化」。
这与之前「页脚时间晚一次」属同一类**静默失效**：不报错，只是不生效。

规则
----
把「会被 SW 缓存、且改了必须让用户立刻拿到新版」的文件算一个合并 sha256，
写进 sw.js 自身的 `// shell-hash: <hash>` 注释行；下次运行发现 hash 变了 → CACHE +1。

  ✅ 纳入（改了必须 +1）
     · sw.js 自身（但先把版本号行与 hash 行规范化，否则会自己触发自己 → 无限递增）
     · *.html（index.html + pages/*.html）
     · assets/css/*.css
     · assets/js/*.js（**不含** data/ 与 meta.js）

  ⛔ 不纳入（各有自己的失效机制，纳入只会造成无意义的频繁 +1）
     · assets/js/data/**  —— 走 stale-while-revalidate，靠数据自身更新
     · assets/js/meta.js  —— 走 network-first，每次访问都拉最新
     · assets/img/**      —— 按 URL 缓存；新图 URL 不同自然 miss
                             （队徽每天可能新增，纳入会天天 +1）

⭐ 基线为什么存在 sw.js 里、而不是 tools/.cache/
------------------------------------------------
`tools/.cache/` 在 .gitignore 里（仅本地）。云端 GHA 每次都是全新 checkout →
外部基线永远读不到 → 每次都走「首次建立基线」→ **永远不会 +1**，自动化形同虚设。
存在 sw.js 里则随提交一起走，云端与本机语义完全一致，且不多一个需要提交的文件。

用法
----
    python3 tools/bump_sw.py            # 需要时 +1（幂等，无变化不动）
    python3 tools/bump_sw.py --check    # 只检查不改（手工提交前自检，需要 +1 时 exit 1）

退出码：0 = 正常/已是最新；1 = --check 模式下发现需要 +1（即有人忘了跑）。
"""
import argparse
import hashlib
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SW = os.path.join(ROOT, "sw.js")

CACHE_RE = re.compile(r"(var\s+CACHE\s*=\s*'fds-shell-v)(\d+)(';)")
# 基线 hash 行（由本脚本维护）。⚠️ 必须**整行**匹配：只替换 hash 值的话，
# 行尾那句说明会被重复累加（实测变成「…sha256）（由 …sha256）」），
# 而规范化又抹不掉多出来的文字 → hash 自我漂移 → 每跑一次都 +1，无限递增。
HASH_LINE_RE = re.compile(r"^[ \t]*//\s*shell-hash:.*$", re.M)
HASH_VAL_RE = re.compile(r"^[ \t]*//\s*shell-hash:\s*([0-9a-f]{16,64})", re.M)
HASH_DOC = "（由 tools/bump_sw.py 维护：外壳文件合并 sha256；改了外壳它就把 CACHE +1）"


def hash_line(h):
    return "// shell-hash: %s%s" % (h, HASH_DOC)


# 规范化占位：保证「改版本号 / 改 hash」不会反过来改变 hash 本身
CACHE_PLACEHOLDER = "var CACHE = 'fds-shell-v@@';"
HASH_PLACEHOLDER = "// shell-hash: @@"


def shell_files():
    """返回需要纳入 hash 的文件绝对路径（已排序，保证稳定）。"""
    out = [SW]
    p = os.path.join(ROOT, "index.html")
    if os.path.exists(p):
        out.append(p)
    for sub in ("pages", "assets/css", "assets/js"):
        d = os.path.join(ROOT, sub)
        if not os.path.isdir(d):
            continue
        for dirpath, dirnames, filenames in os.walk(d):
            # data 目录整棵跳过（按季 chunk，走 stale-while-revalidate）
            if os.path.basename(dirpath) == "data":
                dirnames[:] = []
                continue
            dirnames.sort()
            for fn in sorted(filenames):
                if not fn.endswith((".js", ".css", ".html")):
                    continue
                if fn == "meta.js":
                    continue          # network-first，不靠版本号
                out.append(os.path.join(dirpath, fn))
    return sorted(set(out))


def normalize_sw(txt):
    """抹掉版本号与基线 hash（整行），使 sw.js 的自指部分不影响自身 hash。"""
    txt = CACHE_RE.sub(CACHE_PLACEHOLDER, txt)
    txt = HASH_LINE_RE.sub(HASH_PLACEHOLDER, txt)
    return txt


def compute_hash(paths):
    h = hashlib.sha256()
    for p in paths:
        rel = os.path.relpath(p, ROOT)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        if os.path.abspath(p) == os.path.abspath(SW):
            h.update(normalize_sw(open(p, encoding="utf-8").read()).encode("utf-8"))
        else:
            with open(p, "rb") as f:
                h.update(f.read())
        h.update(b"\0")
    return h.hexdigest()


def read_sw():
    return open(SW, encoding="utf-8").read()


def stored_hash(txt):
    m = HASH_VAL_RE.search(txt)
    return m.group(1) if m else None


def write_sw(txt, new_hash, bump):
    """写入新的 hash 行（bump=True 时同时把 CACHE 版本号 +1），返回 (旧版本, 新版本)。"""
    line = hash_line(new_hash)
    if HASH_LINE_RE.search(txt):
        # 用 lambda 替换，避免 line 里的反斜杠被当成转义
        txt = HASH_LINE_RE.sub(lambda m: line, txt, count=1)
    else:
        m = CACHE_RE.search(txt)
        if not m:
            raise SystemExit("[FAIL] 在 sw.js 里找不到 var CACHE = 'fds-shell-vNN';")
        txt = txt[:m.end()] + "\n" + line + txt[m.end():]

    old_n = new_n = None
    if bump:
        m = CACHE_RE.search(txt)
        old_n, new_n = int(m.group(2)), int(m.group(2)) + 1
        txt = txt[:m.start(2)] + str(new_n) + txt[m.end(2):]
    with open(SW, "w", encoding="utf-8") as f:
        f.write(txt)
    return old_n, new_n


def main():
    ap = argparse.ArgumentParser(description="sw.js CACHE 版本号自动递增")
    ap.add_argument("--check", action="store_true",
                    help="只检查：需要 +1 时打印并 exit 1，不修改文件")
    args = ap.parse_args()

    paths = shell_files()
    txt = read_sw()
    cur = compute_hash(paths)
    old = stored_hash(txt)

    if old is None:
        if args.check:
            print("[bump_sw] ⚠️ sw.js 里没有 shell-hash 基线行，需要先跑一次建立基线")
            return 1
        write_sw(txt, cur, bump=False)
        print(f"[bump_sw] 首次建立基线（{len(paths)} 个外壳文件）→ hash {cur[:12]}")
        print("[bump_sw] 本次不改版本号（没有可比对的旧 hash）")
        return 0

    if cur == old:
        print(f"[bump_sw] 外壳文件无变化（{len(paths)} 个），版本号保持")
        return 0

    if args.check:
        print("[bump_sw] ⚠️ 外壳文件已改动但 CACHE 版本号未 +1")
        print(f"          hash {old[:12]} → {cur[:12]}")
        print("          请运行：python3 tools/bump_sw.py")
        return 1

    old_n, new_n = write_sw(txt, cur, bump=True)
    print(f"[bump_sw] 外壳文件有变化（{len(paths)} 个）→ CACHE fds-shell-v{old_n} → v{new_n}")
    print(f"          hash {old[:12]} → {cur[:12]}")
    print("          请提醒用户 Cmd+Shift+R 硬刷新")
    return 0


if __name__ == "__main__":
    sys.exit(main())
