#!/bin/bash
# 足球数据站 · 自动更新
#   1. 从 ESPN 隐藏 API（site.api.espn.com）抓取 2026-27 最新赛果（免费、实时，
#      摆脱 openfootball / football-data.co.uk 结果录入滞后；build_2026_27.py 现以 ESPN 为主源）
#   2. 重算三份报告的数据（平局·五大 / 平局·次级 / 进球数）
#   3. 把数据块同步进静态站点（带备份 + 体检，历史赛季绝不改动）
#   4. git 提交并推送到 GitHub
# 由 launchd 每天 06:00 调用（脚本内含 0~3599s 随机错峰，避免整点集中请求数据源）。

set -uo pipefail

WS="/Users/santu/WorkBuddy AI/2026-09-02-02-18-19"
GOALS_WS="/Users/santu/WorkBuddy AI/2026-08-24-11-07-48"
SITE="/Users/santu/soccerdata/football-data-site"
AUTO="$SITE/tools"
PY="/usr/bin/python3"

# ── 防重入 + 随机错峰 ──
# 运行锁：避免 catchup.sh 在下方随机等待期间误判「窗口错过」而重复拉起本任务
REFRESH_LOCK="$AUTO/.refresh.lock"
if [ -e "$REFRESH_LOCK" ]; then
    _pid=$(cat "$REFRESH_LOCK" 2>/dev/null)
    if [ -n "$_pid" ] && kill -0 "$_pid" 2>/dev/null; then
        echo "[SKIP] 已有 refresh 进程在运行 (pid $_pid)，退出"
        exit 0
    fi
    rm -f "$REFRESH_LOCK"
fi
echo $$ > "$REFRESH_LOCK"
trap 'rm -f "$REFRESH_LOCK"' EXIT
# 随机错峰：本任务由 launchd 在每天 06:00 触发，这里再随机等待 0~3599 秒，
# 使实际抓取/同步落在 06:00~07:00 之间任意时刻，避免整点集中打数据源。
echo "════════ 随机错峰等待（0~3599s）════════"
sleep $(( RANDOM % 3600 ))

# 0) 路径护栏：站点必须位于 ~/soccerdata，绝不允许落在桌面。
#    历史事故：站点曾放在 ~/Desktop/soccerdata，迁移后 launchd 仍指向旧路径，
#    导致桌面上被反复重建出 soccerdata 目录。这里主动兜底。
DESKTOP_DIR="${HOME:-/Users/santu}/Desktop"
case "$SITE" in
    "$DESKTOP_DIR"/*|"$DESKTOP_DIR")
        echo "[FAIL] 站点路径位于桌面（$SITE），已中止，避免在桌面产生任何内容"
        exit 1 ;;
esac
if [ -e "$DESKTOP_DIR/soccerdata" ]; then
    echo "[WARN] 检测到残留目录 $DESKTOP_DIR/soccerdata，疑似旧路径遗留，请确认后删除"
fi

mkdir -p "$AUTO/logs"
LOG="$AUTO/logs/$(date '+%Y-%m-%d_%H%M%S').log"
exec > >(tee -a "$LOG") 2>&1

notify() {  # notify "标题" "正文"
    osascript -e "display notification \"$2\" with title \"$1\"" >/dev/null 2>&1 || true
}

step() {
    local name="$1"; shift
    echo
    echo "──────── $name ────────"
    "$@"
    local rc=$?
    if [ "$rc" -ne 0 ]; then
        echo "[FAIL] $name（退出码 $rc）"
        echo "=== 本次更新中止，站点未做任何改动 ==="
        echo "日志：$LOG"
        notify "足球数据更新失败" "$name 失败，详见日志"
        exit 1
    fi
    echo "[OK] $name"
}

echo "════════ 足球数据自动更新 $(date '+%F %T') ════════"

# 0) 清掉 football-data 的 /tmp 缓存。
#    build_2026_27.py 的 fetch() 已经自清，这里再兜一层底，防止将来脚本被回滚。
rm -f /tmp/fd_*_2627.csv

# 1) 抓取并重建 2026-27（五大联赛 + 五大次级联赛）
step "抓取 2026-27 最新赛果" "$PY" "$WS/build_2026_27.py"

# 1b) 站点已不再展示「数据源更新时间」，mark_fetch_stamp.py 步骤已移除（其写入的
#     srcUpdated 现在无人读取，保留 mark_fetch_stamp.py 脚本本身以备将来复用）。

# 2) 平局统计 · 五大联赛
step "分析：平局·五大联赛"  "$PY" "$WS/analyze_all.py"
step "出报告：平局·五大联赛" "$PY" "$WS/build_big5.py"

# 3) 平局统计 · 次级联赛
step "分析：平局·次级联赛"  "$PY" "$WS/analyze_champ.py"
step "出报告：平局·次级联赛" "$PY" "$WS/build_champ.py"

# 4) 进球数统计（该页是增量打补丁式更新 2026-27 的进球分布）
step "更新：进球数统计 2026-27" "$PY" "$WS/update_seq23_2627.py"

# 5) 同步数据块到站点
step "同步数据到站点" "$PY" "$AUTO/sync_site.py"

# 5b) 把 monolithic data.js 拆成按季 chunk + 队徽外置 PNG（首屏懒加载提速）。
#     必须在 sync_site.py 之后调用，保证 chunk 始终由校验过的数据派生。
#     Phase 2：big5 / champ / goals 三套数据集全部拆分完毕，统一在此处生成。
step "拆分 draws-big5 按季 chunk + 队徽外置"  "$PY" "$AUTO/gen_draws_big5_chunks.py" draws-big5
step "拆分 draws-champ 按季 chunk + 队徽外置" "$PY" "$AUTO/gen_draws_big5_chunks.py" draws-champ
step "拆分 goals 按季 chunk + 队徽外置"        "$PY" "$AUTO/gen_goals_chunks.py"

# 6) 提交并推送（带锁重试；git add 失败视为锁冲突必须重试，绝不再静默 SKIP）
SUMMARY="$(grep -m1 '^SUMMARY|' "$LOG" | sed 's/^SUMMARY|//')"
echo
echo "──────── git 提交与推送 ────────"
cd "$SITE" || { echo "[FAIL] 站点目录不存在"; exit 1; }

if [ ! -d .git ]; then
    echo "[SKIP] 站点尚未 git init，跳过提交"
else
    pushed=0
    for attempt in 1 2 3; do
        # 刷新「本页更新时间」为本机当前时间（与 pre-commit 钩子 bump_meta.py 双重保险；
        # 钩子未被安装时这里兜底，保证任何一次同步提交都会让页脚「本页更新」前进）
        "$PY" "$AUTO/bump_meta.py" || true
        # 清掉可能的 stale 写锁（WorkBuddy 后台 git 沙箱会反复重建 .git/index.lock，
        # 曾导致整个推送被 git 静默跳过、数据更新卡在本地不上线）
        rm -f .git/index.lock
        if ! git add 'assets/js/*-data.js' 'assets/js/meta.js' \
                     'assets/js/data/draws-big5' 'assets/js/data/draws-champ' 'assets/js/data/goals' \
                     'assets/img/crests' 'assets/img/goals-crests' 'assets/img/leaguelogos'; then
            echo "[WARN] git add 失败（第 $attempt 次，疑似锁冲突），清锁后重试"
            rm -f .git/index.lock; sleep 3; continue
        fi
        if git diff --cached --quiet; then
            echo "[SKIP] 没有需要提交的改动"
            pushed=1; break
        fi
        MSG="chore(data): 同步 2026-27 赛果 $(date '+%F')"
        [ -n "$SUMMARY" ] && MSG="$(printf '%s\n\n%s' "$MSG" "$SUMMARY")"
        if git commit -q -F - <<< "$MSG"; then
            echo "[OK] 已提交：$(git log -1 --format='%h %s')"
            if git remote get-url origin >/dev/null 2>&1; then
                if git push origin HEAD 2>&1; then
                    echo "[OK] 已推送到 origin"
                    notify "足球数据已更新" "${SUMMARY:-数据已同步}"
                    pushed=1; break
                else
                    echo "[WARN] git push 失败（第 $attempt 次），清锁后重试"
                    rm -f .git/index.lock; sleep 3
                fi
            else
                echo "[SKIP] 未配置 origin 远程仓库，仅提交到本地"
                pushed=1; break
            fi
        else
            echo "[WARN] git commit 失败（第 $attempt 次），清锁后重试"
            rm -f .git/index.lock; sleep 3
        fi
    done
    if [ "$pushed" -ne 1 ]; then
        echo "[FAIL] git 提交/推送在重试后仍然失败，站点数据已本地更新但未上线"
        echo "日志：$LOG"
        notify "足球数据推送失败" "本地数据已更新但推送失败，需检查 SSH/仓库/锁冲突"
        exit 1
    fi
fi

echo
# 记录本次成功时间戳，供「错过窗口补跑」机制判断
# 只有整条流水线成功到达此处（前面任意步骤失败都会 exit 1）才写，失败则留空让补跑重试
date +%s > "$AUTO/.lastrun"
echo "[OK] 已记录成功时间戳 → $AUTO/.lastrun"

echo "════════ 完成 $(date '+%F %T') ════════"
echo "日志：$LOG"
