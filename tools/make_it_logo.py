#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 assets/img/leaguelogos/it.png —— 意甲联赛 logo（独立「A」字标）。

为什么需要这个脚本
------------------
意甲的官方主标志就是这枚蓝色渐变的「A」字标（**不含 "SERIE A" 字样**）。
联赛冠名（2024-25 起由 TIM 换为 Enilive）只出现在纵向锁定组合里；
电视转播的比分条用的是纯图形标（2026-10-18 用户用直播截图指出）。

站上原来的 `it.png` 是 330×564 的**纵向锁定组合**：
A 标 + "SERIE A" + 意大利国旗条 + Enilive 冠名条，而且是**唯一一张全不透明白底**的
联赛 logo。在 `.league-tab img { width:22px; height:22px; object-fit:contain }`
的方形框里只能渲染成 22×12 的小竖条，深色主题下还会显示成一个白色竖条。

做法（不重绘、不改色）
--------------------
1. 源图 = 站上原 `it.png` 的副本（`tools/.cache/it_seriea_lockup.png`，首次自动从原图复制）；
2. 按「非白像素的连续行」切条带，第一条 = A 标（下面是 SERIE A / 国旗 / Enilive）；
3. 从四角 flood fill 掉外部白底 → 透明（图形像素本身一个都不改）；
4. 裁到 alpha bbox → 居中放进方形画布（四周留白 5%）→ LANCZOS 缩到 128×128。

128 的理由同 `tools/make_en_logo.py`：站上只在 22px 渲染，128 是 5.8 倍。

⚠️ 这是**同 URL 换内容**，`tools/bump_sw.py` 的 shell-hash **不覆盖 assets/img/**
→ 换完必须**手工把 sw.js 的 CACHE +1**，否则老访客永远看到旧图。

用法
----
    python3 tools/make_it_logo.py              # 生成 it.png（源图取缓存/首次从原图复制）
    python3 tools/make_it_logo.py --check      # 只校验现状（exit 1 = 不是独立 A 标）
    python3 tools/make_it_logo.py --src a.png  # 用指定源图（离线/复现时用）

依赖：Pillow（`/Users/santu/.workbuddy-ai/binaries/python/envs/default/bin/python`）
"""
import argparse
import os
import shutil
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets/img/leaguelogos/it.png")
CACHE = os.path.join(ROOT, "tools/.cache/it_seriea_lockup.png")
SIZE = 128
PAD_RATIO = 0.05          # 四周留白 = 画布边长的 5%
WHITE_MIN = 245           # 三通道都 > 此值视为白底
FLOOD_THRESH = 24         # flood fill 容差（吃进抗锯齿的浅色边缘）

LIGHT_BG = (238, 241, 246)   # --bg（浅色主题）
DARK_BG = (15, 17, 23)       # --bg（深色主题）


def fetch_src(path):
    """源图 = 站上原图。首次跑时原图还在，复制一份当缓存（之后原图就被覆盖了）。"""
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        print(f"复用缓存 {path}")
        return path
    if not os.path.exists(OUT):
        raise SystemExit(f"既没有缓存 {path}，也没有 {OUT} —— 无法生成")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    shutil.copy2(OUT, path)
    print(f"从站上原图复制源图 → {path}")
    return path


def _is_white(px, tol=12):
    r, g, b, a = px
    return a > 20 and r > 255 - tol and g > 255 - tol and b > 255 - tol


def a_mark_only(src_path):
    """从锁定组合里裁出独立 A 标，返回方形 RGBA 图（未缩放）。"""
    im = Image.open(src_path).convert("RGBA")
    w, h = im.size
    px = im.load()

    # 按「整行是否含非白像素」切连续条带：第一条 = A 标
    rows = []
    for y in range(h):
        rows.append(any(not _is_white(px[x, y]) for x in range(w)))
    bands, start = [], None
    for y, has in enumerate(rows):
        if has and start is None:
            start = y
        if not has and start is not None:
            bands.append((start, y - 1))
            start = None
    if start is not None:
        bands.append((start, h - 1))
    if len(bands) < 2:
        raise SystemExit(f"条带识别异常（源图可能已不是「A 标 + 文字」结构）：{bands}")

    band = bands[0]
    mark = im.crop((0, band[0], w, band[1] + 1))
    mw, mh = mark.size
    print(f"A 标条带 y={band}（{mw}x{mh}），其余 {len(bands) - 1} 条为文字/冠名")

    # 外部白底 → 透明：从四角 flood fill（只吃连通的外部区域，图形像素不改色）
    fill = (0, 0, 0, 0)
    for corner in [(0, 0), (mw - 1, 0), (0, mh - 1), (mw - 1, mh - 1)]:
        if _is_white(mark.getpixel(corner)):
            ImageDraw.floodfill(mark, corner, fill, thresh=FLOOD_THRESH)

    bbox = mark.split()[3].getbbox()
    if not bbox:
        raise SystemExit("A 标裁剪后为空（去白底把图形一起吃了？）")
    mark = mark.crop(bbox)
    lw, lh = mark.size
    alpha = mark.split()[3]
    transparent = sum(1 for v in alpha.getdata() if v == 0)
    print(f"去白底 → 裁到 bbox {lw}x{lh}，透明像素 {transparent * 100 // (lw * lh)}%")

    side = max(lw, lh)
    pad = round(side * PAD_RATIO)
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(mark, ((canvas_side - lw) // 2, (canvas_side - lh) // 2), mark)
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
    a = im.split()[3]
    w, h = im.size
    bbox = a.getbbox() or (0, 0, 0, 0)
    has_pad = bbox[0] > 0 and bbox[1] > 0 and bbox[2] < w and bbox[3] < h

    # 内容内部不能有整行全透明的断带（锁定组合的 A 标与 SERIE A 之间就有）
    gaps = []
    for y in range(bbox[1] + 1, bbox[3] - 1):
        if a.crop((bbox[0], y, bbox[2], y + 1)).getbbox() is None:
            gaps.append(y)

    corners = [im.getpixel(p) for p in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]]
    corners_transparent = all(c[3] == 0 for c in corners)

    px = [p for p in list(im.getdata()) if p[3] > 200]
    n = len(px) or 1
    rgb = (sum(p[0] for p in px) // n, sum(p[1] for p in px) // n, sum(p[2] for p in px) // n)
    print(f"{os.path.relpath(path, ROOT)}: {w}x{h}, {os.path.getsize(path)} bytes, "
          f"主色 #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}, alpha bbox={bbox}")
    print(f"  对比度：浅色底 {_contrast(rgb, LIGHT_BG):.2f}:1  深色底 {_contrast(rgb, DARK_BG):.2f}:1")

    ok = True
    if w != h:
        print(f"  ✗ 不是正方形（{w}x{h}）—— 纵向锁定组合在 22px 方框里会被压扁")
        ok = False
    if not has_pad:
        print("  ✗ 内容贴边（无留白），可能被裁到")
        ok = False
    if gaps:
        print(f"  ✗ 内容内部有 {len(gaps)} 行全透明断带（y={gaps[:3]}…）—— 仍是「A 标 + 文字」锁定组合")
        ok = False
    if not corners_transparent:
        print("  ✗ 四角不透明 —— 白底没去掉（深色主题下会显示成白方块）")
        ok = False
    if ok:
        print("  ✓ 独立 A 标形态（正方形 / 有留白 / 无断带 / 透明底）")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="本地源图（默认 tools/.cache/it_seriea_lockup.png）")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if report(args.src or OUT) else 1)

    src = args.src or fetch_src(CACHE)
    canvas = a_mark_only(src)
    out = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"写出 {os.path.relpath(OUT, ROOT)}")
    report(OUT)
    print("\n⚠️ 记住手工把 sw.js 的 CACHE 版本号 +1（同 URL 换内容，shell-hash 不覆盖图片）")


if __name__ == "__main__":
    main()
