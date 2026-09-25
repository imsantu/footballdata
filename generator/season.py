# -*- coding: utf-8 -*-
"""站点「当前赛季」的唯一来源。

为什么单独一个文件
------------------
赛季码此前散落在 31 个文件、287 处：同步脚本、两个 chunk 拆分器、生成器全家桶、
4 个前端逻辑 JS、refresh.sh。每换一个赛季都要人工逐处对齐，而漏一处**不会报错**，
只会静默出错 —— 例如该隐藏的列没隐藏、chunk 被写到旧赛季名下、页脚时间不前进。
现在改为全部从这里取；前端更进一步，直接从已加载的 shell.js 推导（seasonOrder[0]），
页面里不再出现任何赛季字面量。

换季流程
--------
1. 改本文件的 SEASON / SEASON_LONG / SEASON_TAG；
2. 把抓取脚本按新赛季改名（build_2026_27.py → build_2027_28.py），并更新 refresh.sh
   里的那两处调用路径。
除此之外没有第三处需要动。
"""

# 展示码：chunk 文件名（assets/js/data/<group>/<league>/<SEASON>.js）、日志、前端一致
SEASON = "2026-27"

# 数据源长码：titan007 的 matchResult/{season}/ 路径
SEASON_LONG = "2026-2027"

# 生成器内部标签：build_2026_27.py 写进 data/*.json 的 name 字段（历史沿用，勿改）
SEASON_TAG = "2627"


if __name__ == "__main__":
    # 供 refresh.sh 之类的 shell 取用：SEASON="$("$PY" "$WS/season.py")"
    print(SEASON)
