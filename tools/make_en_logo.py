#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 assets/img/leaguelogos/en.png —— 英超联赛 logo（独立狮头）。

为什么需要这个脚本
------------------
英超自 **2023/24 赛季**起品牌升级：头戴皇冠的狮子图标「从文字标识中解放出来」，
官方主标志就是这枚狮头（**没有 "Premier League" 字样**）。
站上原来的 `en.png` 还是 2016 版横向锁定组合（330×139，狮子 + 两行字），
在 `.league-tab img { width:22px; height:22px; object-fit:contain }` 的方形框里
只能渲染成 22×9，既过时又几乎看不清。

做法（不重绘、不改色）
--------------------
1. 取 ESPN 官方 500×500 锁定组合（同一枚狮子，比站上 330px 源更清晰）；
2. 按「有像素的连续行」切出顶部狮头条带（下方是 Premier / League 两行字）；
3. 裁到 alpha bbox → 居中放进方形画布（四周留白 5%）→ LANCZOS 缩到 128×128。

128 的理由：站上只在 22px（`.league-tab img` / `.lg-logo`）渲染，
128 已是 5.8 倍，足够任何 retina；与 `tools/regen_crests.py` 的队徽口径一致。

⚠️ 这是**同 URL 换内容**，`tools/bump_sw.py` 的 shell-hash **不覆盖 assets/img/**
（它按 URL 缓存，新图 URL 不同自然 miss）。所以换完必须**手工把 sw.js 的 CACHE +1**，
否则老访客永远看到旧图。

用法
----
    python3 tools/make_en_logo.py              # 下载源图 → 生成 en.png
    python3 tools/make_en_logo.py --check      # 只校验现状，不写文件（exit 1 = 不是独立狮头）
    python3 tools/make_en_logo.py --src a.png  # 用本地源图（离线/复现时用）

依赖：Pillow（`/Users/santu/.workbuddy-ai/binaries/python/envs/default/bin/python`）
"""
import argparse
import os
import subprocess
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets/img/leaguelogos/en.png")
CACHE = os.path.join(ROOT, "tools/.cache/en_league_lockup_500.png")
SRC_URL = "https://a.espncdn.com/i/leaguelogos/soccer/500/23.png"
SIZE = 128
PAD_RATIO = 0.05          # 四周留白 = 画布边长的 5%

LIGHT_BG = (238, 241, 246)   # --bg（浅色主题）
DARK_BG = (15, 17, 23)       # --bg（深色主题）


def fetch_src(path):
    if os.path.exists(path) and os.path.getsize(path) > 5000:
        print(f"复用缓存 {path}")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"下载 {SRC_URL}")
    r = subprocess.run(["curl", "-4", "-sSL", "--compressed", "--max-time", "60",
                        "-o", path, SRC_URL], capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(path) or os.path.getsize(path) < 5000:
        raise SystemExit(f"下载失败：{r.stderr.strip()[:200]}")
    return path


def lion_only(src_path):
    """从锁定组合里裁出独立狮头，返回方形 RGBA 图（未缩放）。"""
    im = Image.open(src_path).convert("RGBA")
    w, h = im.size
    alpha = im.split()[3]

    # 按「整行是否含像素」切连续条带：第一条 = 狮头，后面是 Premier / League
    rows = [alpha.crop((0, y, w, y + 1)).getbbox() is not None for y in range(h)]
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
        raise SystemExit(f"条带识别异常（可能源图已不是「狮头+文字」结构）：{bands}")

    band = bands[0]
    lion = im.crop((0, band[0], w, band[1] + 1))
    lion = lion.crop(lion.split()[3].getbbox())
    lw, lh = lion.size
    print(f"狮头条带 y={band} → 裁到 alpha bbox {lw}x{lh}")

    side = max(lw, lh)
    pad = round(side * PAD_RATIO)
    canvas_side = side + pad * 2
    canvas = Image.new("RGBA", (canvas_side, canvas_side), (0, 0, 0, 0))
    canvas.paste(lion, ((canvas_side - lw) // 2, (canvas_side - lh) // 2), lion)
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
    # 独立狮头的判据：正方形；四周有留白；**内容内部没有整行全透明的「断带」**
    # （锁定组合的狮子与 Premier / League 之间就有一条这样的断带）
    bbox = a.getbbox() or (0, 0, 0, 0)
    has_pad = bbox[0] > 0 and bbox[1] > 0 and bbox[2] < w and bbox[3] < h
    gaps = []
    for y in range(bbox[1] + 1, bbox[3] - 1):
        if a.crop((bbox[0], y, bbox[2], y + 1)).getbbox() is None:
            gaps.append(y)
    px = [p for p in im.get_flattened_data() if p[3] > 200]
    n = len(px) or 1
    rgb = (sum(p[0] for p in px) // n, sum(p[1] for p in px) // n, sum(p[2] for p in px) // n)
    print(f"{os.path.relpath(path, ROOT)}: {w}x{h}, {os.path.getsize(path)} bytes, "
          f"主色 #{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}, alpha bbox={bbox}")
    print(f"  对比度：浅色底 {_contrast(rgb, LIGHT_BG):.2f}:1  深色底 {_contrast(rgb, DARK_BG):.2f}:1")
    ok = True
    if w != h:
        print(f"  ✗ 不是正方形（{w}x{h}）—— 横向锁定组合在 22px 方框里会被压扁")
        ok = False
    if not has_pad:
        print("  ✗ 内容贴边（无留白），可能被裁到")
        ok = False
    if gaps:
        print(f"  ✗ 内容内部有 {len(gaps)} 行全透明断带（y={gaps[:3]}…）—— 仍是「狮头+文字」锁定组合")
        ok = False
    if ok:
        print("  ✓ 独立狮头形态（正方形 / 有留白 / 无断带）")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", help="本地源图（默认下载 ESPN 500px 锁定组合）")
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    if args.check:
        sys.exit(0 if report(args.src or OUT) else 1)

    src = args.src or fetch_src(CACHE)
    canvas = lion_only(src)
    out = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.save(OUT, "PNG", optimize=True)
    print(f"写出 {os.path.relpath(OUT, ROOT)}")
    report(OUT)
    print("\n⚠️ 记住手工把 sw.js 的 CACHE 版本号 +1（同 URL 换内容，shell-hash 不覆盖图片）")


if __name__ == "__main__":
    main()
