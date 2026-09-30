#!/bin/bash
# 足球数据站 · 看门狗（兜底「主跑没跑成」）
#
# 为什么需要它：
#   GitHub 官方文档（events-that-trigger-workflows#schedule）明确承认：
#     "If the load is sufficiently high enough, some queued jobs may be dropped."
#   —— 高负载时**排队任务会被直接丢弃**，不是晚跑，是根本不跑。而 run 既然没被创建，
#   就不会留下任何 run 记录与注解，我们事后**无法察觉**。本站的数据链现在只有云端这一条
#   （本地 launchd 已停），所以必须有兜底。
#
# 触发：daily.yml 的第二个 schedule（标称北京 06:00，实际 08:00~09:45）
# 判据：站点 assets/js/meta.js 的 generated 日期是否已是「今天（北京）」
#         是 → 今天已成功更新过 → 跳过（不重复抓取、不产生多余提交）
#         否 → 主跑没跑成（或跑挂了）→ 立即补跑
#
# ⚠️ 补跑时把 GITHUB_EVENT_NAME 置为 watchdog：refresh.sh 只在「= schedule」时做随机
#    错峰等待，改成别的值即可跳过错峰 —— 补跑本来就是迟到的，不该再等。
set -uo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE="${FD_SITE_DIR:-$(cd "$DIR/.." && pwd)}"
META="$SITE/assets/js/meta.js"
TODAY="$(TZ=Asia/Shanghai date +%F)"

gen=""
if [ -f "$META" ]; then
    gen="$(grep -oE '"generated"[[:space:]]*:[[:space:]]*"[0-9]{4}-[0-9]{2}-[0-9]{2}' "$META" \
           | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' | head -1)"
fi

echo "════════ 看门狗 ════════"
echo "  站点 meta.js 的 generated 日期 = ${gen:-<读不到>}"
echo "  今天（北京）                = ${TODAY}"
echo "  站点目录                    = ${SITE}"

# ⚠️ 变量引用一律写 ${NAME}：macOS 自带 bash 3.2 会把 `$var` 紧跟的多字节字符吃进变量名
#    （`$META）` → 报 `META）: unbound variable`），`set -u` 下直接终止脚本。CI 的 bash 5
#    不犯这个错，所以只在本机验证时暴露 —— 必须靠装置跑出来，不能靠读代码。
if [ -z "${gen}" ]; then
    echo "::warning title=看门狗::读不到 meta.js 的 generated 日期（${META}）→ 无法判断，保守起见直接补跑"
elif [ "${gen}" = "${TODAY}" ]; then
    echo "::notice title=看门狗::站点已在 ${gen} 更新过，今天无需补跑"
    exit 0
else
    echo "::warning title=看门狗::站点数据仍是 ${gen}，今天 ${TODAY} 尚未更新 → 立即补跑（跳过错峰）"
fi

GITHUB_EVENT_NAME=watchdog exec bash "${DIR}/refresh.sh"
