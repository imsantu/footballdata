#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用高清队徽套装替换 assets/img/crests/ 里的队徽资源（可复现、带人工复核结论）。

背景
----
站上队徽原本是 64px / 120px 混杂的图（274 张共 3.9MB），在 retina 上偏糊。
`crest-hd-512/` 是从小程序 `weapp/tools/crests-hd/` 导出的 512px 套装（272 张，23.9MB），
文件名与站上 `{slug}.png` **同名同序**，可直接覆盖 —— 所以替换**不需要改任何数据或 shell**。

决策（2026-09-26）
------------------
* 目标尺寸 **128×128**：站上队徽只在 CSS 里以 20px / 24px 渲染（`object-fit: contain`），
  128px 已是 24px 的 5.3 倍，足够任何 retina；再大纯属浪费带宽。
* 格式 **PNG + 256 色调色板**（`quantize(FASTOCTREE, dither=NONE)`）：目视与原色 RGBA
  无差别（对比图放大 2 倍看不出），但平均 5.2KB vs 18KB。
* 结果：246 张替换后总体积 **约 1.3MB**，比替换前的 3.9MB **更小**，同时更清晰。
* **只替换「方形且边长 ≥ 256」的源图**。套装里另有 22 张是站上兜底源（16 张非方形
  64×79 / 120×147 之类 + 6 张 64/120 方形），与站上现有文件**逐字节相同**，跳过。
* **`EXCLUDE` 里的 4 张必须排除**（见下），这是人工逐张复核后的结论。

⚠️ 复核为什么必要：套装里混了错图，且它是给小程序（深色）准备的
------------------------------------------------------------
自动比对（`--audit`）把 274 张按「裁掉留白后 48×48 的逐像素平均色差」排序，
再人工看差异最大的 61 张，查出两类问题：

1. **错图**：`fc-bayern-munchen.png` 是 *FC Bayern München **BASKETBALL***（篮球队徽）。
   相似度复核能过是因为它和足球队徽共用同一个红白圆环版式。
2. **浅色主题下糊掉**：站上浅色主题不是可选项 —— **移动端强制浅色**，桌面端 6:00–18:00
   默认浅色（见 index.html / pages/*.html 的首帧内联脚本）。而套装是透明底 + 浅色 logo，
   在浅灰底（#eef1f6）上会消失。按「裁到内容边界后合成到 #f0f0f0 的亮度标准差」量化，
   274 张里中位降幅只有 −0.9（即绝大多数没问题），**但 3 张严重**：
   尤文（118→21）、维罗纳（92→18）、巴勒莫（88→16）。
   → 这 3 张回退站上原图（原图自带深色底/深色版，两种主题都稳）。

⚠️ 替换后必须手动把 `sw.js` 的 `CACHE` +1
------------------------------------------
`assets/img/**` 被 `tools/bump_sw.py` **故意排除**在自动 hash 之外（新队徽通常是新 URL，
靠 URL 不同自然 miss；纳入会天天 +1）。但**这次是同一个 URL 换内容** —— SW 是 cache-first，
不 +1 的话装了 SW 的用户会一直看到旧图。所以这是一次性人工 +1。
（`bump_sw.py` 会规范化 CACHE 行，人工 +1 不会让它误判为「外壳有变化」。）

用法
----
    python3 tools/regen_crests.py --audit            # 复核报告：色差 + 浅色主题对比度
    python3 tools/regen_crests.py --dry-run          # 只报告会替换哪些
    python3 tools/regen_crests.py                    # 实际替换
    python3 tools/regen_crests.py --include-excluded # 连 EXCLUDE 也一起替换（不推荐）
    python3 tools/regen_crests.py --src /path/to/hd  # 换源目录

回滚：老图都在 git 里 —— `git checkout HEAD -- assets/img/crests`。
"""
import argparse
import os
import statistics
import sys

from PIL import Image, ImageChops

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "assets/img/crests")
DEFAULT_SRC = "/Users/santu/footballdata/crest-hd-512"

SIZE = 128          # 目标边长
COLORS = 256        # 调色板颜色数
MIN_SIDE = 256      # 源图至少这么大方值得替换

# 人工复核后确认不能替换的（原因见模块 docstring）
EXCLUDE = {
    "fc-bayern-munchen.png": "套装里是 BASKETBALL（篮球队徽），错图",
    "juventus-fc.png":       "新图透明底白色 J，浅色主题对比度 118→21",
    "hellas-verona-fc.png":  "新图黄色版，浅色主题对比度 92→18（站上蓝色版更稳）",
    "palermo-fc.png":        "新图大面积白色，浅色主题对比度 88→16",
}

LIGHT_BG = (240, 240, 240)


def _cropped(p):
    im = Image.open(p).convert("RGBA")
    bb = im.getbbox()
    return im.crop(bb) if bb else im


def distance(a, b):
    """裁掉留白后缩到 48×48，逐像素平均色差（0~255）。"""
    def n(p):
        im = _cropped(p)
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg.convert("RGB").resize((48, 48), Image.LANCZOS)
    d = ImageChops.difference(n(a), n(b))
    px = list(d.get_flattened_data())
    return sum(sum(q) for q in px) / (len(px) * 3)


def light_contrast(p):
    """合成到浅色底后的亮度标准差 —— 越低越容易在浅色主题里糊掉。"""
    im = _cropped(p)
    bg = Image.new("RGBA", im.size, LIGHT_BG + (255,))
    bg.alpha_composite(im)
    return statistics.pstdev(list(bg.convert("L").get_flattened_data()))


def audit(src, names, old_dir):
    print("复核：色差 = 裁掉留白后 48×48 逐像素平均色差；浅色对比度 = 合成到 #f0f0f0 的亮度标准差")
    rows = []
    for n in names:
        a = os.path.join(old_dir, n)
        b = os.path.join(src, n)
        if not os.path.exists(a):
            continue
        try:
            rows.append((distance(a, b), light_contrast(a), light_contrast(b), n))
        except Exception as e:                      # noqa: BLE001
            print("  跳过 %s：%s" % (n, e))
    print("\n色差最大的 20 张（最可能换了变体 / 换了队）：")
    for d, co, cn, n in sorted(rows, reverse=True)[:20]:
        print("   %6.1f   %s" % (d, n))
    print("\n浅色主题对比度降幅最大的 10 张（最可能在浅色主题里糊掉）：")
    for d, co, cn, n in sorted(rows, key=lambda r: r[1] - r[2], reverse=True)[:10]:
        print("   %7.1f → %7.1f（降 %5.1f）  %s" % (co, cn, co - cn, n))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--size", type=int, default=SIZE)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--audit", action="store_true", help="只出复核报告，不写文件")
    ap.add_argument("--include-excluded", action="store_true",
                    help="连 EXCLUDE 里的也一起替换（不推荐）")
    ap.add_argument("--old-dir", default="/tmp/fd_old_crests2",
                    help="--audit 用的站上原图目录（缺的会从 git HEAD 取）")
    args = ap.parse_args()

    src = os.path.abspath(args.src)
    if not os.path.isdir(src):
        raise SystemExit("[FAIL] 源目录不存在：%s" % src)
    names = sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))

    if args.audit:
        os.makedirs(args.old_dir, exist_ok=True)
        import subprocess
        for n in names:
            p = os.path.join(args.old_dir, n)
            if os.path.exists(p) and os.path.getsize(p):
                continue
            r = subprocess.run(["git", "show", "HEAD:assets/img/crests/" + n],
                               cwd=ROOT, capture_output=True)
            if r.returncode == 0 and r.stdout:
                open(p, "wb").write(r.stdout)
        audit(src, names, args.old_dir)
        return 0

    replaced, created, skipped, failed = [], [], [], []
    old_total = new_total = 0
    for n in names:
        sp, dp = os.path.join(src, n), os.path.join(DEST, n)
        try:
            with Image.open(sp) as im:
                w, h = im.size
                if w != h or w < MIN_SIDE:
                    skipped.append((n, "源图 %dx%d（非方形或 < %dpx）" % (w, h, MIN_SIDE)))
                    continue
                if n in EXCLUDE and not args.include_excluded:
                    skipped.append((n, "已排除：" + EXCLUDE[n]))
                    continue
                existed = os.path.exists(dp)
                if existed:
                    old_total += os.path.getsize(dp)
                out = im.convert("RGBA").resize((args.size, args.size), Image.LANCZOS)
                out = out.quantize(colors=COLORS, method=Image.FASTOCTREE, dither=Image.NONE)
                if args.dry_run:
                    (replaced if existed else created).append((n, "%dx%d" % (w, h)))
                    continue
                out.save(dp, "PNG", optimize=True)
        except Exception as e:                      # noqa: BLE001
            failed.append((n, str(e)))
            continue
        new_total += os.path.getsize(dp)
        (replaced if existed else created).append((n, "%dx%d" % (w, h)))

    print("源：%s（%d 张 PNG）" % (src, len(names)))
    print("目标：%s  → %d×%d / %d 色调色板 PNG" % (DEST, args.size, args.size, COLORS))
    print("\n覆盖替换 %d 张，新增 %d 张，跳过 %d 张，失败 %d 张"
          % (len(replaced), len(created), len(skipped), len(failed)))
    if not args.dry_run:
        print("体积：替换前 %.1f MB → 替换后 %.1f MB"
              % (old_total / 1048576, new_total / 1048576))
    else:
        print("\n（--dry-run，未写任何文件）")
    if skipped:
        print("\n跳过：")
        for n, why in skipped:
            print("   %-38s %s" % (n, why))
    if failed:
        print("\n❌ 失败：")
        for n, e in failed:
            print("   %-38s %s" % (n, e))

    if not args.dry_run:
        bad = [(n, Image.open(os.path.join(DEST, n)).size)
               for n, _ in replaced + created
               if Image.open(os.path.join(DEST, n)).size != (args.size, args.size)]
        print("\n自检：%s" % ("全部为 %d×%d ✅" % (args.size, args.size) if not bad else "❌ %s" % bad))
        if bad:
            return 1

    print("\n⚠️ 别忘了：手动把 sw.js 的 CACHE +1（同 URL 换内容，cache-first 不 +1 用户看不到新图）")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
