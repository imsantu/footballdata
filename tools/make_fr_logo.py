#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 assets/img/leaguelogos/fr.png —— 法甲联赛 logo（字标 + 冠名，去掉装饰数字）。

为什么需要这个脚本
------------------
法甲官方标识（2024-25 起 "Ligue 1 McDonald's"）是**纵向三段**：
装饰性的数字「1」造型 + "LIGUE 1" 字标 + 麦当劳 M，站上是 330×592。

法甲**没有**像英超狮头、意甲 A 标那样的独立图形主标，所以不能像 `make_en_logo.py`
/ `make_it_logo.py` 那样只留一个图形。但 `.league-tab img` 是 22×22 的方形框，
330×592 的纵向图 contain 后只剩 **12×22**，三段挤在 22px 高里，字高仅 4px。

做法（不重排、不重绘、不改色）
----------------------------
只裁掉顶部那段装饰性数字「1」造型，保留 **"LIGUE 1" 字标 + 麦当劳 M**：
内容 330×286（比例 1.15:1）→ 22px 方框里渲染成 **22×19**，字高 4.2 → 7.5px。
冠名 M 保留（它是黄色，深色主题下本来就可见，也是官方名称的一部分）。

⚠️ 法甲**没有**纯图形主标，所以这张**不是正方形**——这是刻意的，
`--check` 用「宽高比」而不是「正方形」来判定，别照抄 en/it 的判据。

⚠️ 这是**同 URL 换内容**，`tools/bump_sw.py` 的 shell-hash **不覆盖 assets/img/**
→ 换完必须**手工把 sw.js 的 CACHE +1**。

用法
----
    python3 tools/make_fr_logo.py              # 生成 fr.png（源图取缓存/首次从原图复制）
    python3 tools/make_fr_logo.py --check      # 只校验现状（exit 1 = 仍是三段纵向锁定组合）
    python3 tools/make_fr_logo.py --src a.png  # 用指定源图

依赖：Pillow（`/Users/santu/.workbuddy-ai/binaries/python/envs/default/bin/python`）
"""
import argparse
import os
import shutil
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets/img/leaguelogos/fr.png")
CACHE = os.path.join(ROOT, "tools/.cache/fr_ligue1_lockup.png")
TARGET_W = 128
PAD_RATIO = 0.05          # 四周留白 = 内容宽度的 5%
MAX_ASPECT = 1.60         # 宽/高 上限：22px 方框里高度至少 22/1.6 = 13.75px
KEEP_BANDS = 2            # 保留最后 2 段（LIGUE 1 字标 + 麦当劳 M）

LIGHT_BG = (238, 241, 246)
DARK_BG = (15, 17, 23)


def fetch_src(path):
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        print(f"复用缓存 {path}")
        return path
    if not os.path.exists(OUT):
        raise SystemExit(f"既没有缓存 {path}，也没有 {OUT} —— 无法生成")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy2(OUT, path)
    print(f"从站上原图复制源图 → {path}")
    return path


def bands_of(im):
    """按「整行是否含 alpha 像素」切连续条带。

    ⚠️ 先按阈值二值化：LANCZOS 缩放会在边缘留 1~3 的 alpha 振铃，
    不滤掉的话底部会多出一条 **1 行高** 的假条带（实测踩过）。
    """
    w, h = im.size
    a = im.split()[3].point(lambda v: 255 if v > 8 else 0)
    rows = [a.crop((0, y, w, y + 1)).getbbox() is not None for y in range(h)]
    bands, start = [], None
    for y, has in enumerate(rows):
        if has and start is None:
            start = y
        if not has and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, h - 1))
    return bands


def wordmark_only(src_path):
    """裁掉顶部装饰数字，保留 LIGUE 1 字标 + 麦当劳 M，返回加好留白的 RGBA 图。"""
    im = Image.open(src_path).convert("RGBA")
    bands = bands_of(im)
    print(f"条带 {len(bands)} 段：{bands}")
    if len(bands) < KEEP_BANDS + 1:
        raise SystemExit(f"条带不足（{len(bands)} 段）—— 源图可能已经不是「数字 + 字标 + 冠名」结构")

    top = bands[-KEEP_BANDS][0]
    bottom = bands[-1][1]
    mark = im.crop((0, top, im.size[0], bottom + 1))
    mark = mark.crop(mark.split()[3].getbbox())
    mw, mh = mark.size
    print(f"保留最后 {KEEP_BANDS} 段（y={top}..{bottom}）→ 裁到 alpha bbox {mw}x{mh}，比例 {mw / mh:.2f}:1")

    pad = round(mw * PAD_RATIO)
    canvas = Image.new("RGBA", (mw + pad * 2, mh + pad * 2), (0, 0, 0, 0))
    canvas.paste(mark, (pad, pad), mark)
    return canvas


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def report(path):
    im = Image.open(path).convert("RGBA")
    w, h = im.size
    bands = bands_of(im)
    bbox = im.split()[3].getbbox() or (0, 0, 0, 0)
    corners = [im.getpixel(p) for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]]
    corners_transparent = all(c[3] == 0 for c in corners)

    px = [p for p in list(im.getdata()) if p[3] > 200]
    n = len(px) or 1
    rgb = (sum(p[0] for p in px) // n, sum(p[1] for p in px) // n, sum(p[2] for p in px) // n)
    render_h = round(22 * h / w) if w >= h else 22
    print(f"{os.path.relpath(path, ROOT)}: {w}x{h}, {os.path.getsize(path)} bytes, "
          f"比例 {w / h:.2f}:1, 条带 {len(bands)} 段, alpha bbox={bbox}")
    print(f"  22px 方框里渲染为 {min(22, round(22 * w / h))}x{render_h}；"
          f"主色 #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}")
    print(f"  对比度：浅色底 {_contrast(rgb, LIGHT_BG):.2f}:1  深色底 {_contrast(rgb, DARK_BG):.2f}:1")

    ok = True
    if len(bands) != KEEP_BANDS:
        print(f"  ✗ 有 {len(bands)} 段条带（应为 {KEEP_BANDS}）—— 装饰数字没裁掉，仍是纵向锁定组合")
        ok = False
    if w / h > MAX_ASPECT:
        print(f"  ✗ 宽高比 {w / h:.2f} > {MAX_ASPECT} —— 22px 方框里会太扁")
        ok = False
    if not corners_transparent:
        print("  ✗ 四角不透明（深色主题下会显示成方块）")
        ok = False
    if ok:
        print(f"  ✓ 字标形态（{KEEP_BANDS} 段 / 比例 {w / h:.2f} / 透明底）")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="本地源图（默认 tools/.cache/fr_ligue1_lockup.png）")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if report(args.src or OUT) else 1)

    src = args.src or fetch_src(CACHE)
    canvas = wordmark_only(src)
    out_h = round(TARGET_W * canvas.size[1] / canvas.size[0])
    out = canvas.resize((TARGET_W, out_h), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"写出 {os.path.relpath(OUT, ROOT)}")
    report(OUT)
    print("\n⚠️ 记住手工把 sw.js 的 CACHE 版本号 +1（同 URL 换内容，shell-hash 不覆盖图片）")


if __name__ == "__main__":
    main()
