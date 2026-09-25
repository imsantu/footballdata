#!/usr/bin/env python3
"""静态资源引用闸门：数据/逻辑 JS 里引用的 assets/img/** 必须真实存在且已被 git 跟踪。

为什么需要它（2026-09-26 真实事故）：
  渲染黄金快照只能覆盖「用例里那几十个容器 + 那几个赛季」，抓不到**队徽映射**这类
  全量字符串表的变化 —— 涉事球队（CD Leganés / UD Las Palmas）根本不在任何被覆盖的
  赛季里。于是「shell 引用了一个未被 git 跟踪的新文件」这件事，快照门禁完全无感，
  而线上表现是 404 / 错图。

  这次的触发链：本机旧报告（08-24 工作区）给这两支队的 base64 是**城市照片**（120×60）
  而不是队徽；生成器把 ext 取自 MIME，于是写出 cd-leganes.jpg（既有的 cd-leganes.png
  变成孤儿），shell 立刻改指 .jpg —— 该 .jpg 默认未被 git 跟踪，提交时极易漏掉。

用法：
  python3 tools/check_asset_refs.py            # 检查，失败 exit 1
  python3 tools/check_asset_refs.py --list     # 只列引用，不做判定
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 引用形如 "../assets/img/crests/xxx.png"（相对 pages/）或 "assets/img/..."（相对根）
REF_RE = re.compile(r"[\"'(](\.\./)*assets/img/[A-Za-z0-9._/@-]+[\"')]")
SCAN_DIRS = ["assets/js", "pages", "index.html"]


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


def main():
    list_only = "--list" in sys.argv
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

    print("扫描到 %d 个不同的 assets/img 引用" % len(refs))
    if list_only:
        for rel in sorted(refs):
            print("  %s   <- %s" % (rel, ", ".join(sorted(refs[rel])[:2])))
        return 0

    ok = True
    if missing:
        ok = False
        print("\n❌ 引用了**磁盘上不存在**的文件（线上 404）：")
        for rel in missing:
            print("   %s   <- %s" % (rel, ", ".join(sorted(refs[rel]))))
    if untracked:
        ok = False
        print("\n❌ 引用了**未被 git 跟踪**的文件（提交时极易漏掉，线上 404）：")
        for rel in untracked:
            print("   %s   <- %s" % (rel, ", ".join(sorted(refs[rel]))))
    if ok:
        print("\n✅ 全部引用都存在且已被 git 跟踪")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
