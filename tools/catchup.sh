#!/bin/bash
# 错过窗口补跑检查器（由 launchd 以 StartInterval 周期调用，唤醒/登录即触发）
# 逻辑：算出「最近一个 每天 06:00」窗口；
#       若该窗口已过去、且上次成功更新早于该窗口，则补跑 refresh.sh；否则零成本跳过。
set -u

SITE="/Users/santu/footballdata/football-data-site"
AUTO="$SITE/tools"
LR="$AUTO/.lastrun"
REFRESH="$AUTO/refresh.sh"

# 若 refresh 正在运行（随机错峰等待中），跳过，避免重复拉起
REFRESH_LOCK="$AUTO/.refresh.lock"
if [ -e "$REFRESH_LOCK" ]; then
    _pid=$(cat "$REFRESH_LOCK" 2>/dev/null)
    if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
        echo "$(date '+%F %T') [catchup] refresh 正在运行（pid $_pid），跳过"
        exit 0
    fi
    rm -f "$REFRESH_LOCK"
fi

# 路径护栏：站点绝不允许落在桌面（历史事故：旧 launchd 路径在桌面重建 soccerdata 目录）
DESKTOP_DIR="${HOME:-/Users/santu}/Desktop"
case "$SITE" in
    "$DESKTOP_DIR"/*|"$DESKTOP_DIR")
        echo "$(date '+%F %T') [catchup][FAIL] 站点路径位于桌面（$SITE），已中止"
        exit 1 ;;
esac

# 上次成功时间戳（epoch 秒），默认 0
LAST=0
if [ -f "$LR" ]; then
    v=$(cat "$LR" 2>/dev/null)
    case "$v" in
        ''|*[!0-9]*) LAST=0 ;;
        *) LAST=$v ;;
    esac
fi

NOW=$(date +%s)

# 找最近一个 <= now 的 每天 06:00
best=""
for ((i=0;i<14;i++)); do
    day_epoch=$(date -v-${i}d -v0H -v0M -v0S +%s)
    wd=$(date -v-${i}d +%w)
    slot=$(( day_epoch + 6*3600 ))
    # 每天 15:00 均为更新窗口（去掉原仅周一/周四的限制，实现「每天都更新」）
    if [ "$slot" -le "$NOW" ]; then
        if [ -z "$best" ] || [ "$slot" -gt "$best" ]; then
            best=$slot
        fi
    fi
done

[ -z "$best" ] && exit 0

if [ "$best" -gt "$LAST" ]; then
    echo "$(date '+%F %T') [catchup] 检测到错过的更新窗口：$(date -r "$best" '+%F %a %T')，上次成功=${LAST} → 启动补跑"
    "$REFRESH"
    rc=$?
    if [ "$rc" -eq 0 ]; then
        date +%s > "$LR"
        echo "$(date '+%F %T') [catchup] 补跑成功，已更新 .lastrun"
    else
        echo "$(date '+%F %T') [catchup] 补跑失败（退出码 $rc），下次间隔再试"
    fi
    exit $rc
else
    # 无需补跑：保持静默，避免污染日志
    exit 0
fi
