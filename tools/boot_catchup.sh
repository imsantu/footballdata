#!/bin/bash
# 开机补跑：登录后等联网 → 再等 5 分钟 → 若今日尚未成功同步则补跑 refresh.sh
# 目的：机器在每天 06:00 关机时漏掉定时同步，开机登录后自动补齐一次。
set -u

SITE="/Users/santu/soccerdata/football-data-site"
AUTO="$SITE/tools"
mkdir -p "$AUTO/logs"
LOG="$AUTO/logs/boot_catchup.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

log "boot-catchup 启动 (pid $$)"

# 0) 路径护栏：站点必须位于 ~/soccerdata，绝不允许落在桌面。
DESKTOP_DIR="${HOME:-/Users/santu}/Desktop"
case "$SITE" in
    "$DESKTOP_DIR"/*|"$DESKTOP_DIR")
        log "[FAIL] 站点路径位于桌面（$SITE），已中止"; exit 1 ;;
esac

# 1) 等联网（最多 30 分钟，每 10s 探一次 github，借 SSH 绕墙配置亦可连通）
NET=0
for i in $(seq 1 180); do
    if curl -sI --max-time 8 https://github.com >/dev/null 2>&1; then
        NET=1; log "联网就绪（约 $((i*10))s 后）"; break
    fi
    sleep 10
done
if [ "$NET" -ne 1 ]; then
    log "ERROR: 30 分钟内未联网，放弃本次补跑"; exit 1
fi

# 2) 联网后再等 5 分钟（让系统/网络完全稳定，也错开开机高峰）
log "联网后等待 300s..."
sleep 300

# 3) 今日已成功同步过则跳过（06:00 任务已跑，或今天已补跑过）
LAST="$AUTO/.lastrun"
if [ -f "$LAST" ]; then
    last_day=$(date -j -f %s "$(cat "$LAST" 2>/dev/null)" '+%Y-%m-%d' 2>/dev/null)
    today_day=$(date '+%Y-%m-%d')
    if [ "$last_day" = "$today_day" ]; then
        log "今日已成功同步（.lastrun=$last_day），无需补跑，退出"
        exit 0
    fi
    log "上次成功同步为 $last_day（非今日），执行补跑"
else
    log "无 .lastrun 记录，执行补跑"
fi

# 4) 复用 refresh.sh（自带防重入锁 + 随机错峰 + git 推送 + 失败通知）
log "调用 refresh.sh ..."
bash "$SITE/tools/refresh.sh"
rc=$?
log "refresh.sh 退出码=$rc"
exit $rc
